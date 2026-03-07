"""
main.py
-------
Entry point for the Telegram Gmail Bot.
Sets up the Application, registers handlers, starts the JobQueue, and runs the bot.
"""

import subprocess

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from config import BOT_TOKEN, POLL_INTERVAL, ADMIN_CHAT_ID
from handlers import start, stop_command, grant_access, handle_message, status_command, test_command, help_command, privacy_command, list_command, label_command, check_updates_command
from jobs import poll_emails, check_updates, prune_cached_entries
import cache

async def startup_notify(context):
    """Notify admin on successful restart."""
    try:
        version = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip() or "?"
        
        msg = f"› Bot started ({version})"
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)
    except:
        pass

def main():
    print("Building application...")
    cache.init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- HANDLERS ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("privacy", privacy_command))
    application.add_handler(CommandHandler("grant", grant_access))       # Admin only
    application.add_handler(CommandHandler("status", status_command))     # Admin only
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("label", label_command))
    application.add_handler(CommandHandler("checkupdates", check_updates_command))  # Admin only
    application.add_handler(CommandHandler("code", handle_message))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # --- JOBS ---
    # Notify admin on startup (run once after 5s)
    application.job_queue.run_once(startup_notify, when=5)
    # Poll emails every POLL_INTERVAL seconds (startup poll first)
    application.job_queue.run_repeating(poll_emails, interval=POLL_INTERVAL, first=25, name='startup_poll')
    # Check for updates every 5 minutes
    application.job_queue.run_repeating(check_updates, interval=300, first=30)
    # Prune cache every 24 hours (86400 seconds)
    application.job_queue.run_repeating(prune_cached_entries, interval=86400, first=60)

    print("Bot started...")
    application.run_polling()

if __name__ == '__main__':
    main()

