#!/bin/bash
echo "Starting Bot Wrapper..."

while true; do
  echo "Checking for updates..."
  git pull
  
  echo "Starting Bot..."
  # Use the python from the virtual environment
  ./venv/bin/python main.py
  
  EXIT_CODE=$?
  echo "Bot stopped with exit code $EXIT_CODE."
  
  if [ $EXIT_CODE -ne 0 ]; then
     echo "Bot crashed or stopped. Restarting in 5 seconds..."
     sleep 5
  else
     echo "Bot exited normally. Restarting immediately..."
     sleep 1
  fi
done
