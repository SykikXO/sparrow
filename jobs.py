"""
jobs.py
-------
Background recurring tasks:
- poll_emails: Checks Gmail for new messages for all users.
- check_updates: Checks Git for code updates and restarts if needed.
"""

import os
import json
import logging
import asyncio
from telegram.ext import ContextTypes

from config import USERS_DIR, ADMIN_CHAT_ID
from gmail_api import get_gmail_service, list_messages, get_email_body, remove_links, mark_as_read
from history import load_history, save_history

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
                    clean_body = remove_links(body)
                    
                    # Construct Notification
                    notification = f"📧 *New Email*\n*From:* {sender}\n*Subject:* {subject}\n\n{clean_body}"
                    
                    # Telegram limit (4096 chars)
                    if len(notification) > 4000:
                        notification = notification[:4000] + "..."
                        
                    await context.bot.send_message(chat_id=chat_id, text=notification, parse_mode='Markdown')
                    
                    # Mark as Read and Update History
                    mark_as_read(service, msg['id'])
                    history.append(msg['id'])
                    new_ids = True
                    
                except Exception as e:
                    logging.error(f"Error processing message {msg['id']} for {chat_id}: {e}")
        
        # Save History if updated
        if new_ids:
            if len(history) > 10:
                history = history[-10:]
            save_history(chat_id, history)

async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    """
    Job that checks for Git updates periodically.
    If updates are found, it pulls and exits (triggering restart by run.sh).
    """
    try:
        # 1. Fetch changes
        process = await asyncio.create_subprocess_shell(
            "git fetch && git status -uno",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode()
        
        # 2. Check status
        if "Your branch is behind" in output:
            logging.info("Update detected. Pulling...")
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="Update detected! Pulling changes and restarting...")
            
            # 3. Pull
            await asyncio.create_subprocess_shell("git pull")
            
            # 4. Restart (Exit process)
            import sys
            sys.exit(0)
            
    except Exception as e:
        logging.error(f"Auto-update check failed: {e}")
