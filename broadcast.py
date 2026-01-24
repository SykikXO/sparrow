import asyncio
import os
import logging
from telegram import Bot
from telegram.constants import ParseMode
from config import BOT_TOKEN, USERS_DIR

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def broadcast_notification():
    """Sends a notification to all users about the bot migration."""
    bot = Bot(token=BOT_TOKEN)
    
    # Message to send
    message = input("Enter message to broadcast: ")

    if not os.path.exists(USERS_DIR):
        logging.error(f"Users directory '{USERS_DIR}' not found.")
        return

    # Get all chat IDs from the users directory
    chat_ids = []
    
    # 1. Root level .json files (Legacy)
    for filename in os.listdir(USERS_DIR):
        if filename.endswith('.json') and '_meta' not in filename:
            chat_id = filename.replace('.json', '')
            if chat_id.isdigit():
                chat_ids.append(chat_id)

    # 2. Subdirectories (New system)
    for chat_id in os.listdir(USERS_DIR):
        user_dir = os.path.join(USERS_DIR, chat_id)
        if os.path.isdir(user_dir) and chat_id.isdigit():
            if chat_id not in chat_ids:
                chat_ids.append(chat_id)

    if not chat_ids:
        logging.info("No users found to notify.")
        return

    logging.info(f"Starting broadcast to {len(chat_ids)} users...")

    success_count = 0
    fail_count = 0

    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logging.info(f"Successfully notified user {chat_id}")
            success_count += 1
            # Small delay to avoid flooding
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Failed to notify user {chat_id}: {e}")
            fail_count += 1

    logging.info(f"Broadcast complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    asyncio.run(broadcast_notification())
