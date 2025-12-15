#!/bin/bash
REPO_DIR="$(realpath .)"
cd "$REPO_DIR" || exit 1

python_running=false

# Function to kill Python and restart everything
restart_all() {
  echo "Update detected! Killing Python and restarting..."
  if $python_running; then
    pkill -f "venv/bin/python main.py"
    sleep 1
  fi
  exec "$0" "$@"  # Relaunch this script fresh
}

# Main update checker loop (every 10 seconds)
while true; do
  echo "Checking for updates..."
  git fetch origin
  
  if [ "$(git rev-parse HEAD)" != "$(git rev-parse @{u})" ]; then
    git pull origin "$(git branch --show-current)"
    restart_all
  fi
  
  # Start Python if not already running
  
  if !$python_running; then
    echo "Setting up Python environment..."
    venv/bin/python -m pip install --upgrade pip
    venv/bin/python -m pip install -r requirements.txt
    echo "Starting bot..."
    venv/bin/python main.py & disown
    python_running=true
  fi
  
  sleep 10
done
