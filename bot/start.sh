#!/bin/bash
cd /home/hermes-workspace/Alikhan-migration/bot
pkill -f "python3 main.py" || true
nohup python3 main.py > /tmp/alikhan.log 2>&1 &
echo $! > /tmp/alikhan.pid
echo "Alikhan started, PID: $(cat /tmp/alikhan.pid)"
echo "Logs: tail -f /tmp/alikhan.log"