#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

PORT="${1:-5000}"

echo "Starting bot server on http://localhost:$PORT ..."
python3 bot_server.py "$PORT" &
SERVER_PID=$!

sleep 1

echo "Starting cloudflared tunnel ..."
cloudflared tunnel --url "http://localhost:$PORT"
