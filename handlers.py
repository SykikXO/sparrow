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
from googleapiclient.discovery import build
from telegram import Update
from telegram.ext import ContextTypes
from google_auth_oauthlib.flow import InstalledAppFlow
from jobs import check_updates
from config import ADMIN_CHAT_ID, SCOPES, USERS_DIR, HISTORY_DIR, user_privacy

# Temporary storage for OAuth flows: {chat_id: flow_object}
pending_flows = {}

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command."""
    chat_id = update.effective_chat.id
    is_admin = str(chat_id) == str(ADMIN_CHAT_ID)
    
    user_cmds = (
        "*Available Commands*\n"
        "─────────────────\n"
        "/help - Show this message\n"
        "/test - Summarize random email\n"
        "/list - Linked accounts\n"
        "/label <idx> <tag> - Rename account\n"
        "/privacy - Toggle forward protection"
    )
    
    admin_cmds = (
        "\n\n*Admin Commands*\n"
        "─────────────────\n"
        "/grant <id> - Authorize user\n"
        "/status - Device status\n"
        "/checkupdates - Check for updates"
    )
    
    msg = user_cmds + (admin_cmds if is_admin else "")
    await update.message.reply_text(msg, parse_mode='Markdown')

async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /privacy command - toggles forward protection."""
    chat_id = update.effective_chat.id
    
    # Toggle privacy setting
    current = user_privacy.get(chat_id, False)
    user_privacy[chat_id] = not current
    
    if user_privacy[chat_id]:
        msg = "🔒 Privacy ON\n_Messages won't be forwardable_"
    else:
        msg = "🔓 Privacy OFF\n_Messages can be forwarded_"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /start command.
    Checks if the user already has a folder in USERS_DIR.
    """
    chat_id = update.effective_chat.id
    user_dir = os.path.join(USERS_DIR, str(chat_id))
    
    # Check for both directory (new style) and root level .json (legacy)
    is_existing = os.path.isdir(user_dir) or os.path.exists(os.path.join(USERS_DIR, f"{chat_id}.json"))
    
    if is_existing:
        msg = (
            "✨ **Welcome back to Sparrow Mail!**\n\n"
            "Your data has been successfully preserved. I've already resumed monitoring your linked "
            "Gmail accounts. You will receive summaries here as usual.\n\n"
            "Use `/list` to see your connected accounts or `/help` for more commands."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        
        # Trigger immediate poll spree
        from jobs import poll_user_now
        context.job_queue.run_once(poll_user_now, when=0, data=chat_id)
    else:
        await context.bot.send_message(
            chat_id=chat_id,
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
            
            # Temporary service to get actual email
            temp_service = build('gmail', 'v1', credentials=creds)
            profile = temp_service.users().getProfile(userId='me').execute()
            user_email = profile.get('emailAddress', 'unknown')
            
            # Create user directory
            user_dir = os.path.join(USERS_DIR, str(chat_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Save credentials to users/{chat_id}/{email}.json
            with open(os.path.join(user_dir, f"{user_email}.json"), 'w') as f:
                f.write(creds.to_json())
            
            # Save startup timestamp to ignore old emails
            with open(os.path.join(user_dir, f"{user_email}_meta.json"), 'w') as f:
                 json.dump({"start_time": int(time.time())}, f)

            await update.message.reply_text(f"Setup complete for {user_email}! You will now receive email notifications.")
        except Exception as e:
            await update.message.reply_text(f"Authentication failed: {e}. Please ask admin for a new link.")
        return

    await update.message.reply_text("I didn't understand that. Send your email to request access.")

async def check_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /checkupdates command.
    Checks for updates and sends a message to the admin.
    """
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return
    
    try:
        await check_updates()
    except Exception as e:
        await update.message.reply_text(f"Error checking for updates: {e}")


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
    
    # Get all linked emails for this user
    user_dir = os.path.join(USERS_DIR, str(chat_id))
    emails = []
    if os.path.isdir(user_dir):
        emails = [f.replace('.json', '') for f in os.listdir(user_dir) if f.endswith('.json') and '_meta' not in f]
    
    # Fallback/Legacy
    legacy_file = os.path.join(USERS_DIR, f"{chat_id}.json")
    if os.path.exists(legacy_file):
        emails.append(None) # None signifies root file

    if not emails:
        await update.message.reply_text("You haven't connected any Gmail accounts yet. Send your email to get started.")
        return
    
    # If multiple emails, user should specify or we pick first? 
    # For /test, let's just pick the first one or the one they specify if we had that.
    # For now, let's just pick the first linked account.
    selected_email = emails[0]
    
    service = get_gmail_service(chat_id, email=selected_email)
    if not service:
        await update.message.reply_text("Failed to initialize Gmail service. Please try re-authenticating.")
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
        body = get_email_body(payload)
        # Don't remove links, Ollama needs context
        
        # Summarize
        summary = await ollama_summarize(body, subject, sender)
        
        if len(summary) > 4000:
            summary = summary[:4000] + "..."
            
        # Check privacy setting
        is_protected = user_privacy.get(chat_id, False)
        
        await update.message.reply_text(
            summary, 
            parse_mode='Markdown',
            protect_content=is_protected
        )
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /list command - lists linked Gmail accounts."""
    chat_id = update.effective_chat.id
    user_dir = os.path.join(USERS_DIR, str(chat_id))
    
    if not os.path.isdir(user_dir):
        await update.message.reply_text("No accounts linked yet.")
        return

    emails = sorted([f.replace('.json', '') for f in os.listdir(user_dir) if f.endswith('.json') and '_meta' not in f])
    
    if not emails:
        await update.message.reply_text("No accounts linked yet.")
        return

    msg = "🔗 *Linked Accounts*\n───────────────\n"
    for i, email in enumerate(emails, 1):
        meta_path = os.path.join(user_dir, f"{email}_meta.json")
        descriptor = ""
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                    descriptor = meta.get('descriptor', '')
            except:
                pass
        
        prefix = f"{descriptor} " if descriptor else ""
        msg += f"{i}. {prefix}`{email}`\n"
    
    msg += "\nTo add a descriptor: `/label <num> <emoji/text>`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def label_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /label <num/email> <descriptor>."""
    chat_id = update.effective_chat.id
    user_dir = os.path.join(USERS_DIR, str(chat_id))
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/label <number> <descriptor>`\nExample: `/label 1 📧`", parse_mode='Markdown')
        return

    target = context.args[0]
    descriptor = " ".join(context.args[1:])
    
    if not os.path.isdir(user_dir):
        await update.message.reply_text("No accounts linked yet.")
        return

    emails = sorted([f.replace('.json', '') for f in os.listdir(user_dir) if f.endswith('.json') and '_meta' not in f])
    
    selected_email = None
    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(emails):
            selected_email = emails[idx]
    elif target in emails:
        selected_email = target
        
    if not selected_email:
        await update.message.reply_text("Account not found. Use `/list` to see your accounts.")
        return

    # Update metadata
    meta_path = os.path.join(user_dir, f"{selected_email}_meta.json")
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
        except:
            pass
    
    meta['descriptor'] = descriptor
    
    try:
        with open(meta_path, 'w') as f:
            json.dump(meta, f)
        await update.message.reply_text(f"✅ Label updated for `{selected_email}`: {descriptor}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Failed to save label: {e}")
