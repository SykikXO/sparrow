"""
handlers.py
-----------
Contains Telegram Bot command handlers:
- /start: Welcome message
- /grant: Allow Admin to generate OAuth links
- Message Handler: Handles email input (requests) and auth code verification.
"""

import os
import re
import json
import time
from telegram import Update
from telegram.ext import ContextTypes
from google_auth_oauthlib.flow import InstalledAppFlow

from config import ADMIN_CHAT_ID, SCOPES, USERS_DIR

# Temporary storage for OAuth flows: {chat_id: flow_object}
pending_flows = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /start command.
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Welcome! To start using the Gmail Bot, please reply with your email address."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles generic text messages.
    1. Looks for Email Address -> Triggers access request to Admin.
    2. Looks for Auth Code (/code ...) -> Completes authentication.
    """
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    # CASE 1: Check for email address (Requesting Access)
    if re.match(r"[^@]+@[^@]+\.[^@]+", text):
        # Notify Admin
        admin_msg = f"New access request:\nEmail: {text}\nChat ID: {chat_id}\n\nTo approve, send:\n`/grant {chat_id}`"
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode='Markdown')
            await update.message.reply_text("Request sent to developer. Please wait for approval.")
        except Exception as e:
            await update.message.reply_text(f"Error contacting admin: {e}")
        return

    # CASE 2: Check for Auth Code (Finishing Access)
    if chat_id in pending_flows:
        # Allow user to send just the code or "/code <code>"
        if text.startswith("/code"):
             code = text.replace("/code", "").strip()
        else:
             code = text
             
        try:
            flow = pending_flows.pop(chat_id)
            flow.fetch_token(code=code)
            creds = flow.credentials
            
            # Save credentials to users/ directory
            with open(os.path.join(USERS_DIR, f"{chat_id}.json"), 'w') as f:
                f.write(creds.to_json())
            
            # Save startup timestamp to ignore old emails
            with open(os.path.join(USERS_DIR, f"{chat_id}_meta.json"), 'w') as f:
                 json.dump({"start_time": int(time.time())}, f)

            await update.message.reply_text("Setup complete! You will now receive email notifications.")
        except Exception as e:
            await update.message.reply_text(f"Authentication failed: {e}. Please ask admin for a new link.")
        return

    await update.message.reply_text("I didn't understand that. Send your email to request access.")

async def grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /grant <chat_id>.
    Only accessible by ADMIN_CHAT_ID.
    Generates an OAuth link and sends it to the user.
    """
    # Security Check
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return
        
    try:
        target_chat_id = context.args[0]
    except IndexError:
        await update.message.reply_text("Usage: /grant <chat_id>")
        return
        
    # Check for client secrets
    if not os.path.exists('credentials.json'):
        await update.message.reply_text("Error: credentials.json missing on server.")
        return

    # Initialize OAuth Flow
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',
        SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )
    
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    # Store flow object to resume later
    pending_flows[int(target_chat_id)] = flow
    
    msg = f"Access granted! Please authorize the app here:\n{auth_url}\n\nAfter authorizing, copy the code and reply with:\n`/code YOUR_CODE_HERE`"
    
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=msg)
        await update.message.reply_text(f"Invitation sent to {target_chat_id}.")
    except Exception as e:
        await update.message.reply_text(f"Failed to send to user: {e}")
