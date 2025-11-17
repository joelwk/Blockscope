#!/bin/bash
# Start SSH tunnel for Bitcoin RPC connection
# This will run in the foreground - keep this terminal open!
#
# Set SSH_SERVER environment variable to configure the remote server
# Example: export SSH_SERVER="user@hostname"

SSH_SERVER="${SSH_SERVER:-${FS_SSH_SERVER}}"
LOCAL_PORT="${LOCAL_PORT:-8332}"
REMOTE_PORT="${REMOTE_PORT:-8332}"

if [ -z "$SSH_SERVER" ]; then
    echo "Error: SSH_SERVER not set. Please set it as an environment variable:"
    echo "  export SSH_SERVER=\"user@hostname\""
    echo "  export FS_SSH_SERVER=\"user@hostname\""
    exit 1
fi

echo "Starting SSH tunnel..."
echo "Local port: $LOCAL_PORT -> Remote: $SSH_SERVER:$REMOTE_PORT"
echo ""
echo "Keep this terminal open while using the Bitcoin RPC connection."
echo "Press Ctrl+C to stop the tunnel."
echo ""

ssh -L ${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT} ${SSH_SERVER} -N

