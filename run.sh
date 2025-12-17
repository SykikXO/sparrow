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
    
    # Only install deps if requirements.txt changed
    REQ_HASH=$(md5sum requirements.txt | cut -d' ' -f1)
    CACHED_REQ=""
    [ -f .req_hash ] && CACHED_REQ=$(cat .req_hash)
    
    if [ "$REQ_HASH" != "$CACHED_REQ" ]; then
      echo "Requirements changed. Installing dependencies..."
      venv/bin/python -m pip install --upgrade pip -q
      venv/bin/python -m pip install -r requirements.txt -q
      echo "$REQ_HASH" > .req_hash
    fi
    
    # Rebuild Ollama model if Modelfile changed
    if [ -f Modelfile ]; then
      MODEL_HASH=$(md5sum Modelfile | awk '{print $1}')
      CACHED_MODEL=""
      [ -f .modelfile_hash ] && CACHED_MODEL=$(cat .modelfile_hash)
      
      if [ "$MODEL_HASH" != "$CACHED_MODEL" ]; then
        echo "Modelfile changed. Rebuilding Ollama model..."
        echo "Current Hash: $MODEL_HASH"
        echo "Cached Hash: $CACHED_MODEL"
        
        if ollama create sum -f Modelfile; then
            echo "✅ Ollama model rebuilt successfully."
            echo "$MODEL_HASH" > .modelfile_hash
        else
            echo "❌ FAILED to rebuild Ollama model. Will retry next loop."
        fi
      fi
    fi
    
    echo "Starting bot..."
    # Run in foreground with tee for dual output (terminal + file)
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
