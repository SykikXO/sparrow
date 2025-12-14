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
        # User might send: "/code ...", "...", or "http://localhost/?code=..."
        clean_text = text.replace("/code", "").strip()
        
        # Extract code parameter from URL if present
        if 'code=' in clean_text:
             try:
                 # Poor man's URL parse
                 clean_text = clean_text.split('code=')[1].split('&')[0]
             except:
                 pass
                 
        code = clean_text
             
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
    Generates an OAuth link (localhost) and asks user to paste the code/URL.
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
    # We use 'http://localhost' to satisfy Google, even though we can't catch it automatically cross-device.
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',
        SCOPES,
        redirect_uri='http://localhost'
    )
    
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    # Store flow object to resume later
    pending_flows[int(target_chat_id)] = flow
    
    msg = (
        f"🔗 **Link Access**\n\n"
        f"1. Click here: [Authorize Gmail]({auth_url})\n"
        f"2. Login and approve permissions.\n"
        f"3. Chrome will show an error: **'This site can't be reached'** (localhost). \n"
        f"   ✅ **This is normal!** Do not panic.\n"
        f"4. **Copy the URL** from the address bar of that error page.\n"
        f"5. Paste it here in the chat."
    )
    
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=msg, parse_mode='Markdown')
        await update.message.reply_text(f"Invitation sent to {target_chat_id}.")
    except Exception as e:
        await update.message.reply_text(f"Failed to send to user: {e}")
