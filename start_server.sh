#!/bin/bash
cd /home/ubuntu/fixit.ai
source venv/bin/activate
nohup gunicorn fixit_ai.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile logs/access.log --error-logfile logs/error.log &
echo "Server started with PID: $!"
