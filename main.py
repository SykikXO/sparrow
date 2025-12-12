"""
main.py
-------
Entry point for the Telegram Gmail Bot.
Sets up the Application, registers handlers, starts the JobQueue, and runs the bot.
"""

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from config import BOT_TOKEN, POLL_INTERVAL, ADMIN_CHAT_ID
from handlers import start, grant_access, handle_message
from jobs import poll_emails, check_updates

def main():

    print("Building application...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- HANDLERS ---
    # /start
    application.add_handler(CommandHandler("start", start))
    # /grant <id> (Admin only)
    application.add_handler(CommandHandler("grant", grant_access))
    # /code <code>, or just text for Email/Code
    application.add_handler(CommandHandler("code", handle_message))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # --- JOBS ---
    job_queue = application.job_queue
    
    # Poll emails every 60s
    job_queue.run_repeating(poll_emails, interval=POLL_INTERVAL, first=100)
    
    # Check for updates every 300s (5m)
    job_queue.run_repeating(check_updates, interval=300, first=20) 

    print("Bot started...")
    application.run_polling()

if __name__ == '__main__':
    main()
