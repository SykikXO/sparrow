# Sparrow

Sparrow is a self-hosted Gmail summarizer for Telegram. It was created to solve a personal problem: receiving too many emails that don't need immediate full-text reading but require a quick scan for action items.

## Technology Stack
- **Language:** Python 3.10+
- **Telegram Bot API:** `python-telegram-bot`
- **Email Interface:** Google Gmail API (OAuth2)
- **Summarization:** Ollama (running `qwen2.5:3b-instruct` or similar)
- **Model Management:** Custom `Modelfile` for optimized Telegram formatting

## Core Logic
The bot polls linked Gmail accounts periodically. When a new email is detected:
1. The full body is extracted via Gmail API.
2. It's passed to a local Ollama instance with a specific system prompt.
3. A concise summary (Sender, Headline, Action Item) is sent to the user's Telegram chat.
4. The message is marked as read in Gmail to prevent duplicate summaries.

## Getting Started
1. **Prerequisites:**
   - Linux environment (tested on Termux and standard distros)
   - Ollama installed and running
   - Google Cloud Project with Gmail API enabled
2. **Setup:**
   - Clone the repository
   - Copy `config.example.py` to `config.py` and add your `BOT_TOKEN`
   - Place `credentials.json` from Google Cloud in the root directory
   - Run `pip install -r requirements.txt`
3. **Running:**
   - `./run.sh` will handle dependencies, model creation, and bot execution.

## Commands
- `/start`: Welcome and migration detection.
- `/help`: List available commands.
- `/list`: See all linked accounts.
- `/privacy`: Toggle content protection.
- `/status`: Check bot and system health (Admin only).
