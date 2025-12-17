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

def _sync_summarize(body, subject, sender):
    """
    Synchronous call to Ollama. Called via executor to avoid blocking.
    """
    try:
        # Structured prompt that works better with the Modelfile's system instructions
        prompt = f"""EMAIL TO SUMMARIZE:

From: {sender}
Subject: {subject}

{body[:3000]}"""  # Limit body to avoid context overflow

        response = ollama.chat(model='sum', messages=[
            {'role': 'user', 'content': prompt}
        ])
        
        summary = response['message']['content'].strip()
        
        # Strip thinking tags from qwen3 thinking model output
        # e.g., <think>reasoning...</think>actual response
        summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
        
        # Add header for context
        return f"📧 {subject}\n\n{summary}"
        
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