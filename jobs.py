
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

from config import USERS_DIR, ADMIN_CHAT_ID, user_privacy
from gmail_api import get_gmail_service, list_messages, get_email_body, remove_links, mark_as_read
from history import load_history, save_history
from ollama_integration import ollama_summarize

async def poll_emails(context: ContextTypes.DEFAULT_TYPE):
    """
    Job that runs every POLL_INTERVAL.
    Iterates over all registered users and their linked email accounts.
    """
    if not os.path.exists(USERS_DIR):
        return
        
    # 1. Process Legacy/Root Level Credentials (for users who haven't migrated)
    for filename in os.listdir(USERS_DIR):
        if filename.endswith('.json') and '_meta' not in filename:
            path = os.path.join(USERS_DIR, filename)
            if os.path.isfile(path):
                chat_id = filename.replace('.json', '')
                await process_user_account(context, chat_id, None)

    # 2. Process Multi-Account Subdirectories
    for chat_id in os.listdir(USERS_DIR):
        user_dir = os.path.join(USERS_DIR, chat_id)
        if os.path.isdir(user_dir):
            for filename in os.listdir(user_dir):
                if filename.endswith('.json') and '_meta' not in filename:
                    email = filename.replace('.json', '')
                    await process_user_account(context, chat_id, email)

async def process_user_account(context, chat_id, email):
    """Polls a single Gmail account and sends notifications."""
    # Load user's start timestamp (to ignore old emails)
    if email:
        meta_path = os.path.join(USERS_DIR, str(chat_id), f"{email}_meta.json")
    else:
        meta_path = os.path.join(USERS_DIR, f"{chat_id}_meta.json")
        
    start_ts = 0
    descriptor = ""
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            try:
                meta = json.load(f)
                start_ts = meta.get("start_time", 0)
                descriptor = meta.get("descriptor", "")
            except:
                pass
    
    # Get Gmail Service
    service = get_gmail_service(chat_id, email=email)
    if not service:
        return
        
    history = load_history(chat_id, email=email)
    
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
                
                # Append email address or descriptor to subject if multi-account
                if email:
                    prefix = descriptor if descriptor else email
                    subject = f"[{prefix}] {subject}"
                
                body = get_email_body(payload)
                
                # Use async summarization with full body (keep links for context)
                summary = await ollama_summarize(body, subject, sender)
                
                # Prepend descriptor if available
                if email:
                    prefix = descriptor if descriptor else email
                    summary = f"[{prefix}]\n{summary}"
                
                # Telegram limit (4096 chars)
                if len(summary) > 4000:
                    summary = summary[:4000] + "..."
                
                # Check privacy setting (cast chat_id to int for dict lookup)
                is_protected = user_privacy.get(int(chat_id), False)
                
                # Send with Markdown formatting and Privacy setting
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=summary, 
                    parse_mode='Markdown',
                    protect_content=is_protected
                )
                
                # Mark as Read and Update History
                mark_as_read(service, msg['id'])
                history.append(msg['id'])
                new_ids = True
                
            except Exception as e:
                logging.error(f"Error processing message {msg['id']} for {chat_id} ({email}): {e}")
                # Still add to history to prevent infinite retry loop
                history.append(msg['id'])
                new_ids = True
            
            # Yield to event loop
            await asyncio.sleep(0)
    
    # Save History if updated
    if new_ids:
        if len(history) > 20: # Increased a bit
            history = history[-20:]
        save_history(chat_id, history, email=email)


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


async def prune_cached_entries(context: ContextTypes.DEFAULT_TYPE):
    """
    Job that runs periodically to prune cache entries older than 1 year.
    """
    import cache
    cache.prune_old_cache(days=365)


async def poll_user_now(context: ContextTypes.DEFAULT_TYPE):
    """
    Triggers an immediate poll for a specific user ID.
    Used for 'welcome back' summaries.
    """
    chat_id = str(context.job.data)
    
    # 1. Process Legacy
    path = os.path.join(USERS_DIR, f"{chat_id}.json")
    if os.path.isfile(path):
        await process_user_account(context, chat_id, None)
        
    # 2. Process Multi-Account
    user_dir = os.path.join(USERS_DIR, chat_id)
    if os.path.isdir(user_dir):
        for filename in os.listdir(user_dir):
            if filename.endswith('.json') and '_meta' not in filename:
                email = filename.replace('.json', '')
                await process_user_account(context, chat_id, email)

