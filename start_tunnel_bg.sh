#!/bin/bash
# Start SSH tunnel in background for Bitcoin RPC connection
#
# Set SSH_SERVER environment variable to configure the remote server
# Example: export SSH_SERVER="user@hostname"

SSH_SERVER="${SSH_SERVER:-${FS_SSH_SERVER}}"
LOCAL_PORT="${LOCAL_PORT:-8332}"
REMOTE_PORT="${REMOTE_PORT:-8332}"
PID_FILE=".tunnel.pid"

if [ -z "$SSH_SERVER" ]; then
    echo "Error: SSH_SERVER not set. Please set it as an environment variable:"
    echo "  export SSH_SERVER=\"user@hostname\""
    echo "  export FS_SSH_SERVER=\"user@hostname\""
    exit 1
fi

# Check if tunnel is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "SSH tunnel is already running (PID: $OLD_PID)"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

echo "Starting SSH tunnel in background..."
ssh -f -N -L ${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT} ${SSH_SERVER}

# Get the PID of the SSH process
SSH_PID=$(ps aux | grep "ssh -f -N -L ${LOCAL_PORT}" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$SSH_PID" ]; then
    echo "$SSH_PID" > "$PID_FILE"
    echo "SSH tunnel started in background (PID: $SSH_PID)"
    echo "To stop: ./stop_tunnel.sh"
else
    echo "Failed to start SSH tunnel"
    exit 1
fi

