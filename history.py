"""
history.py
----------
Handles loading and saving of email processing history.
This ensures we don't notify the user about the same email twice.
"""

import os
import json
from config import HISTORY_DIR

def load_history(chat_id):
    """
    Loads the list of processed email IDs for a specific user.
    Returns an empty list if no history exists.
    """
    path = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else list(data)
        except:
            return []
    return []

def save_history(chat_id, history):
    """
    Saves the list of processed email IDs.
    """
    path = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    with open(path, 'w') as f:
        json.dump(history, f)
