#!/bin/bash
REPO_DIR="$(realpath .)"
cd "$REPO_DIR" || exit 1

restart_all() {
  echo "Update detected! Killing Python and restarting..."
  pkill -f "venv/bin/python.*main\.py" 2>/dev/null
  sleep 2
  exec ./run.sh "$@"  # Simple, works from repo root
}

while true; do
  echo "Checking for updates..."
  git fetch origin 2>/dev/null || { sleep 10; continue; }
  
  if [ "$(git rev-parse HEAD)" != "$(git rev-parse @{u})" ]; then
    git pull origin "$(git branch --show-current)"
    restart_all
  fi
  
  if ! pgrep -f "venv/bin/python.*main\.py" > /dev/null; then
    echo "Setting up Python environment..."
    venv/bin/python -m pip install --upgrade pip
    venv/bin/python -m pip install -r requirements.txt
    echo "Starting bot..."
    venv/bin/python main.py & disown
  fi
  
  sleep 10
done
