#!/bin/bash
REPO_DIR="$(realpath .)"
cd "$REPO_DIR" || exit 1

restart_bot() {
  echo "Restarting bot..."
  pkill -f "venv/bin/python.*main\.py" 2>/dev/null
  sleep 2
  exec ./run.sh "$@"
}

while true; do
  # Check if bot is running
  if ! pgrep -f "venv/bin/python.*main\.py" > /dev/null; then
    echo "Bot not running. Starting..."
    if [ ! -d "venv" ]; then
      echo "Creating virtual environment..."
      python3 -m venv venv --without-pip || true
    fi
    
    if ! venv/bin/python -m pip --version > /dev/null 2>&1; then
      echo "pip not found in venv. Installing via get-pip.py..."
      curl -sS https://bootstrap.pypa.io/get-pip.py | venv/bin/python
    fi
    venv/bin/python -m pip install -r requirements.txt -q
    ollama create sum -f Modelfile
    venv/bin/python -u main.py 2>&1 | tee -a bot.log &
    BOT_PID=$!
    
    # Trim log to last 1000 lines periodically
    (while kill -0 $BOT_PID 2>/dev/null; do
      sleep 60
      if [ -f bot.log ] && [ $(wc -l < bot.log) -gt 1000 ]; then
        tail -1000 bot.log > bot.log.tmp && mv bot.log.tmp bot.log
      fi
    done) &
  fi
  
  sleep 10
done
