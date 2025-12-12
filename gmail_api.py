"""
gmail_api.py
------------
Functions for interacting with the Google Gmail API.
Includes authentication, fetching messages, parsing content, and modifying labels.
"""

import os
import re
import base64
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import USERS_DIR, SCOPES

def get_gmail_service(chat_id):
    """
    Constructs and returns a Gmail API service instance for the given user (chat_id).
    Handles token refreshing if the token is expired.
    """
    creds_file = os.path.join(USERS_DIR, f"{chat_id}.json")
    if not os.path.exists(creds_file):
        return None
    
    creds = Credentials.from_authorized_user_file(creds_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(creds_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logging.error(f"Failed to refresh token for {chat_id}: {e}")
                return None
        else:
            return None
            
    return build('gmail', 'v1', credentials=creds)

def strip_html_tags(text):
    """Simple regex to strip HTML tags from body text."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def remove_links(text):
    """Removes http/https and www links from the text."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    return text

def get_email_body(payload):
    """
    Recursively extracts the email body from the payload.
    Prioritizes 'text/plain', falls back to 'text/html' (stripped).
    """
    body = ""
    if 'parts' in payload:
        # 1. Look for text/plain
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data')
                if data:
                    text = base64.urlsafe_b64decode(data).decode()
                    if text and text.strip().lower() != "null":
                        return text
        # 2. Look for text/html
        for part in payload['parts']:
            if part['mimeType'] == 'text/html':
                data = part['body'].get('data')
                if data:
                    html = base64.urlsafe_b64decode(data).decode()
                    return strip_html_tags(html)
        # 3. Recurse into nested parts
        for part in payload['parts']:
            if 'parts' in part:
                 res = get_email_body(part)
                 if res and res.strip().lower() != "null": return res
    else:
        # Non-multipart message
        data = payload.get('body', {}).get('data')
        if data:
            content = base64.urlsafe_b64decode(data).decode()
            if payload.get('mimeType') == 'text/html':
                return strip_html_tags(content)
            return content
            
    return body or "(No readable content found)"

def list_messages(service, user_id='me', after_timestamp=None, max_results=10):
    """
    Lists unread messages. 
    If after_timestamp is provided, filters for messages received after that time.
    """
    try:
        query = 'is:unread'
        if after_timestamp:
            query += f' after:{after_timestamp}'
        results = service.users().messages().list(userId=user_id, q=query, maxResults=max_results).execute()
        return results.get('messages', [])
    except Exception as e:
        logging.error(f"Error listing messages: {e}")
        return []

def mark_as_read(service, msg_id, user_id='me'):
    """Removes the UNREAD label from a message."""
    try:
        service.users().messages().modify(userId=user_id, id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
    except Exception as e:
        logging.error(f"Error marking as read {msg_id}: {e}")
