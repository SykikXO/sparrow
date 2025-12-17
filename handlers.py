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

import subprocess
import random
from gmail_api import get_gmail_service, get_email_body, remove_links
from ollama_integration import ollama_summarize

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /status command.
    Returns battery, CPU temp, and version info.
    """
    # Admin only
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return
    
    try:
        # Git version
        version = "unknown"
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
        except:
            pass
        
        # Battery (Android)
        battery = "—"
        try:
            result = subprocess.run(
                ["termux-battery-status"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                pct = data.get('percentage', '?')
                status = data.get('status', '').lower()
                icon = "⚡" if status == "charging" else "○"
                battery = f"{pct}% {icon}"
        except:
            try:
                with open('/sys/class/power_supply/battery/capacity', 'r') as f:
                    battery = f"{f.read().strip()}%"
            except:
                pass
        
        # CPU Temperature
        cpu_temp = "—"
        temp_paths = [
            '/sys/class/thermal/thermal_zone3/temp',
            '/sys/devices/virtual/thermal/thermal_zone3/temp'
        ]
        for path in temp_paths:
            try:
                with open(path, 'r') as f:
                    temp = int(f.read().strip()) / 1000
                    cpu_temp = f"{temp:.0f}°"
                    break
            except:
                continue
        
        msg = (
            f"▪︎ status\n"
            f"─────────\n"
            f"› version  {version}\n"
            f"› battery  {battery}\n"
            f"› cpu      {cpu_temp}\n"
            f"› bot      running"
        )
        await update.message.reply_text(msg)
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /test command.
    Picks a random email from last 20 and summarizes it.
    """
    chat_id = update.effective_chat.id
    
    # Get Gmail service for requesting user
    service = get_gmail_service(str(chat_id))
    if not service:
        await update.message.reply_text("You haven't connected your Gmail yet. Send your email to get started.")
        return
    
    try:
        await update.message.reply_text("🔍 Fetching random email...")
        
        # Get last 20 emails (any, not just unread)
        results = service.users().messages().list(userId='me', maxResults=20).execute()
        messages = results.get('messages', [])
        
        if not messages:
            await update.message.reply_text("No emails found.")
            return
        
        # Pick random one
        msg = random.choice(messages)
        message_detail = service.users().messages().get(userId='me', id=msg['id']).execute()
        payload = message_detail.get('payload', {})
        headers = payload.get('headers', [])
        
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        
        body = get_email_body(payload)
        clean_body = remove_links(body)
        
        # Summarize
        summary = await ollama_summarize(clean_body, subject, sender)
        
        if len(summary) > 4000:
            summary = summary[:4000] + "..."
        
        await update.message.reply_text(summary)
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
