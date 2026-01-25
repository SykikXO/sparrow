"""
config.example.py
-----------------
Template for configuration.
Copy this file to 'config.py' and fill in your values.
"""

import os
import logging

# --- USER CONFIGURATION ---
# Telegran Bot Token from @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Your Telegram User ID (get from @userinfobot)
ADMIN_CHAT_ID = "YOUR_ADMIN_ID_HERE"
# --------------------------

# OAuth Scopes for Gmail API
# 'gmail.modify' to mark emails as read.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Directory paths
USERS_DIR = 'users'
HISTORY_DIR = 'histories'
CACHE_DB_PATH = 'cache.db'

# Check for new emails every X seconds
POLL_INTERVAL = 60

# Privacy settings per user: {chat_id: bool} - Shared across modules
user_privacy = {}

# Ensure directories exist upon import
os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
