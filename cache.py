"""
cache.py
--------
SQLite3-based caching for email summaries.
"""

import sqlite3
import hashlib
import time
import logging
from config import CACHE_DB_PATH

def init_db():
    """Initializes the SQLite database and creates the message_cache table."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_cache (
                fingerprint TEXT PRIMARY KEY,
                summary TEXT,
                timestamp INTEGER
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("Cache database initialized.")
    except Exception as e:
        logging.error(f"Failed to initialize cache database: {e}")

def generate_fingerprint(sender, subject, body):
    """
    Generates a SHA-256 fingerprint for an email.
    Fingerprint is based on sender, subject, and body content.
    """
    data = f"{sender}|{subject}|{body}".encode('utf-8', errors='ignore')
    return hashlib.sha256(data).hexdigest()

def get_cached_summary(fingerprint):
    """Retrieves a summary from the cache if it exists."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT summary FROM message_cache WHERE fingerprint = ?", (fingerprint,))
        row = cursor.fetchone()
        conn.close()
        if row:
            logging.info(f"Cache hit for {fingerprint[:8]}...")
            return row[0]
    except Exception as e:
        logging.error(f"Error reading from cache: {e}")
    return None

def set_cached_summary(fingerprint, summary):
    """Stores a summary in the cache with the current timestamp."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO message_cache (fingerprint, summary, timestamp) VALUES (?, ?, ?)",
            (fingerprint, summary, int(time.time()))
        )
        conn.commit()
        conn.close()
        logging.info(f"Cache update for {fingerprint[:8]}...")
    except Exception as e:
        logging.error(f"Error writing to cache: {e}")

def prune_old_cache(days=365):
    """Deletes entries older than the specified number of days."""
    try:
        cutoff = int(time.time()) - (days * 24 * 60 * 60)
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM message_cache WHERE timestamp < ?", (cutoff,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted_count > 0:
            logging.info(f"Pruned {deleted_count} old entries from cache.")
    except Exception as e:
        logging.error(f"Error pruning cache: {e}")
