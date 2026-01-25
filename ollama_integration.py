"""
ollama_integration.py
---------------------
Integrates with local Ollama instance to summarize emails.
"""
import re
import ollama
import logging
import asyncio
from functools import partial
import cache

def _sync_summarize(body, subject, sender):
    """
    Synchronous call to Ollama. Called via executor to avoid blocking.
    Now includes caching logic.
    """
    try:
        # 1. Generate Fingerprint
        fingerprint = cache.generate_fingerprint(sender, subject, body)
        
        # 2. Check Cache
        cached = cache.get_cached_summary(fingerprint)
        if cached:
            return cached

        # 3. If missing, summarize with Ollama
        # Structured prompt that works better with the Modelfile's system instructions
        prompt = f"""EMAIL TO SUMMARIZE:

From: {sender}
Subject: {subject}

{body[:3000]}"""  # Limit body to avoid context overflow

        response = ollama.chat(model='sum', messages=[
            {'role': 'user', 'content': prompt}
        ])
        
        summary = response['message']['content'].strip()
        
        # 4. Store in Cache
        cache.set_cached_summary(fingerprint, summary)
        
        return summary
        
    except Exception as e:
        logging.error(f"Ollama summarization failed: {e}")
        # Fallback to raw email if Ollama fails
        return f"📧 New Email\nFrom: {sender}\nSubject: {subject}\n\n{body[:500]}..."

async def ollama_summarize(body, subject, sender):
    """
    Async wrapper for Ollama summarization.
    Runs the blocking ollama call in a thread pool to avoid freezing the bot.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,  # Default executor
        partial(_sync_summarize, body, subject, sender)
    )