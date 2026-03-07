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

def get_gmail_service(chat_id_or_path, email=None):
    """
    Constructs and returns a Gmail API service instance.
    Accepts:
    1. chat_id and email: looks up credentials in users/{chat_id}/{email}.json
    2. full path: uses provided path
    3. chat_id only: (legacy/fallback) looks up users/{chat_id}.json
    """
    if email:
        creds_file = os.path.join(USERS_DIR, str(chat_id_or_path), f"{email}.json")
    elif chat_id_or_path.endswith('.json'):
        creds_file = chat_id_or_path
    else:
        creds_file = os.path.join(USERS_DIR, f"{chat_id_or_path}.json")

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
                logging.error(f"Failed to refresh token for {creds_file}: {e}")
                return None
        else:
            return None
            
    return build('gmail', 'v1', credentials=creds)

def get_user_email(service):
    """Fetches the email address of the authenticated user."""
    try:
        profile = service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress')
    except Exception as e:
        logging.error(f"Error fetching user profile: {e}")
        return None

def clean_html_css(text):
    """
    Removes inline CSS, <style> blocks, <script> blocks, HTML tags, 
    and truncates long links to keep the text clean for the LLM.
    """
    if not text:
        return text
        
    # 1. Remove <style>...</style> and <script>...</script> completely (including contents)
    text = re.sub(r'(?is)<style.*?>.*?</style>', ' ', text)
    text = re.sub(r'(?is)<script.*?>.*?</script>', ' ', text)
    text = re.sub(r'(?is)<!--.*?-->', ' ', text)
    
    # 2. Strip all remaining HTML tags
    text = re.sub(r'(?is)<.*?>', ' ', text)
    
    # 3. Strip raw URLs, mailto links, and URL parameters entirely to prevent LLM bloat
    text = re.sub(r'(?i)https?://[^\s<>"]+|www\.[^\s<>"]+|mailto:[^\s<>"]+|\?[^\s<>"]+', ' ', text)
    
    # Strip residual url-encoded characters like %20 that get orphaned from link removal
    text = re.sub(r'(?:%[0-9A-Fa-f]{2})+', ' ', text)
    
    # Remove orphaned Markdown empty parentheses that are left behind
    text = re.sub(r'\(\s*\)', ' ', text)
    
    # 4. Clean up weird CSS artifacts like "body { ... }" that didn't have tags
    # Remove everything between { and } aggressively 
    text = re.sub(r'(?s)\{.*?\}', ' ', text)
    
    # Remove CSS selectors and keywords that get orphaned when {} are removed
    css_keywords = r'(?i)\b(@media|@import|body|img|table|span|td|th|tr|div|a|p|h[1-6]|ul|li|html|font-family|font-size|color|background|margin|padding|border|display|width|height|max-width|min-width)\b[^a-z0-9]'
    text = re.sub(css_keywords, ' ', text)
    text = re.sub(r'\*[\[class\].a-zA-Z0-9_\-]+', ' ', text)  # remove *[class].ib_t and similar
    text = re.sub(r'\.[a-zA-Z0-9_\-]+', ' ', text) # remove .em_main_table and similar
    
    # Clean up weird html entities that might have survived
    text = text.replace('&nbsp;', ' ').replace('&#039;', "'").replace('&#064;', '@').replace('&#183;', '·').replace('&#xa9;', '©').replace('&amp;', '&').replace('1zwnj000', '')
    
    # 6. Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def remove_double_whitespace(text):
    """Removes double whitespace from the text."""
    return ' '.join(text.split())

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
                        return clean_html_css(text)
        # 2. Look for text/html
        for part in payload['parts']:
            if part['mimeType'] == 'text/html':
                data = part['body'].get('data')
                if data:
                    html = base64.urlsafe_b64decode(data).decode()
                    return clean_html_css(html)
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
                return clean_html_css(content)
            return content
            
    return body or "(No readable content found)"

def list_messages(service, user_id='me', after_timestamp=None, max_results=10, unread_only=True):
    """
    Lists messages. 
    If unread_only is True, filters for unread messages.
    If after_timestamp is provided, filters for messages received after that time.
    """
    try:
        query = 'is:unread' if unread_only else ''
        if after_timestamp:
            if query:
                query += f' after:{after_timestamp}'
            else:
                query = f'after:{after_timestamp}'
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
