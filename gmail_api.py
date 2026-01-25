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

def strip_html_tags(text):
    """
    Strips HTML tags but preserves links by extracting URLs from anchor tags.
    """
    # Extract URLs from anchors first
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', text, re.IGNORECASE)
    
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, ' ', text)
    
    # Append unique links at the end if they exist
    if links:
        # Filter out tracking/unsubscribe links
        good_links = [l for l in links if not any(x in l.lower() for x in 
            ['unsubscribe', 'mailto:', 'tel:', 'track', 'click', 'open.', 'list-'])]
        unique_links = list(dict.fromkeys(good_links))[:3]  # Top 3 unique
        if unique_links:
            text += "\n\nLinks:\n" + "\n".join(unique_links)
    
    return text

def remove_links(text):
    """Removes http/https and www links from the text."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
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
                        return remove_double_whitespace(text)
        # 2. Look for text/html
        for part in payload['parts']:
            if part['mimeType'] == 'text/html':
                data = part['body'].get('data')
                if data:
                    html = base64.urlsafe_b64decode(data).decode()
                    return remove_double_whitespace(strip_html_tags(html))
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
                return remove_double_whitespace(strip_html_tags(content))
            return remove_double_whitespace(content)
            
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
