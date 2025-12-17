
"""
jobs.py
-------
Background recurring tasks:
- poll_emails: Checks Gmail for new messages for all users.
"""

import os
import json
import logging
import asyncio
from telegram.ext import ContextTypes

from config import USERS_DIR, ADMIN_CHAT_ID
from gmail_api import get_gmail_service, list_messages, get_email_body, remove_links, mark_as_read
from history import load_history, save_history
from ollama_integration import ollama_summarize

async def poll_emails(context: ContextTypes.DEFAULT_TYPE):
    """
    Job that runs every POLL_INTERVAL.
    Iterates over all registered users, checks for new emails, and sends notifications.
    """
    if not os.path.exists(USERS_DIR):
        return
        
    # Loop through all user credential files
    for filename in os.listdir(USERS_DIR):
        if not filename.endswith('.json') or '_meta' in filename:
            continue
            
        chat_id = filename.replace('.json', '')
        
        # Load user's start timestamp (to ignore old emails)
        meta_path = os.path.join(USERS_DIR, f"{chat_id}_meta.json")
        start_ts = 0
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                start_ts = json.load(f).get("start_time", 0)
        
        # Get Gmail Service
        service = get_gmail_service(chat_id)
        if not service:
            continue
            
        history = load_history(chat_id)
        
        # Fetch Messages
        messages = list_messages(service, after_timestamp=start_ts)
        new_ids = False
        
        for msg in messages:
            if msg['id'] not in history:
                try:
                    # Get Full Detail
                    message_detail = service.users().messages().get(userId='me', id=msg['id']).execute()
                    payload = message_detail.get('payload', {})
                    headers = payload.get('headers', [])
                    
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                    
                    body = get_email_body(payload)
                    
                    # Use async summarization with full body (keep links for context)
                    summary = await ollama_summarize(body, subject, sender)
                    
                    # Telegram limit (4096 chars)
                    if len(summary) > 4000:
                        summary = summary[:4000] + "..."
                    
                    # Send without parse_mode to avoid Markdown errors from Ollama
                    await context.bot.send_message(chat_id=chat_id, text=summary)
                    
                    # Mark as Read and Update History
                    mark_as_read(service, msg['id'])
                    history.append(msg['id'])
                    new_ids = True
                    
                except Exception as e:
                    logging.error(f"Error processing message {msg['id']} for {chat_id}: {e}")
                    # Still add to history to prevent infinite retry loop
                    history.append(msg['id'])
                    new_ids = True
                
                # Yield to event loop so user commands stay responsive
                await asyncio.sleep(0)
        
        # Save History if updated
        if new_ids:
            if len(history) > 10:
                history = history[-10:]
            save_history(chat_id, history)


async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    """
    Job that checks for Git updates periodically.
    Sends notification before restart.
    """
    import sys
    
    try:
        process = await asyncio.create_subprocess_shell(
            "git fetch && git status -uno",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        output = stdout.decode()
        
        if "Your branch is behind" in output:
            # Get new version
            proc2 = await asyncio.create_subprocess_shell(
                "git rev-parse --short @{u}",
                stdout=asyncio.subprocess.PIPE
            )
            out2, _ = await proc2.communicate()
            new_version = out2.decode().strip()
            
            # Notify admin
            msg = f"○ Update available ({new_version})\n○ Restarting..."
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)
            
            # Pull and exit (run.sh will restart)
            await asyncio.create_subprocess_shell("git pull")
            await asyncio.sleep(2)
            sys.exit(0)
            
    except Exception as e:
        logging.error(f"Update check failed: {e}")

