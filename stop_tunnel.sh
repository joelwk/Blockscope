#!/bin/bash
# Stop SSH tunnel for Bitcoin RPC connection

PID_FILE=".tunnel.pid"
LOCAL_PORT=8332

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping SSH tunnel (PID: $PID)..."
        kill "$PID"
        rm "$PID_FILE"
        echo "SSH tunnel stopped"
    else
        echo "SSH tunnel process not found, cleaning up PID file"
        rm "$PID_FILE"
    fi
else
    # Try to find and kill any SSH tunnel on this port
    PID=$(lsof -ti:${LOCAL_PORT} 2>/dev/null | head -1)
    if [ -n "$PID" ]; then
        echo "Found SSH tunnel process (PID: $PID), stopping..."
        kill "$PID"
        echo "SSH tunnel stopped"
    else
        echo "No SSH tunnel found running"
    fi
fi

