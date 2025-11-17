#!/bin/bash
# High-level launcher for Blockscope
# Manages venv activation, SSH tunnel, and fee monitoring execution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="venv"
TUNNEL_SCRIPT="start_tunnel_bg.sh"
STOP_TUNNEL_SCRIPT="stop_tunnel.sh"
CONFIG_FILE="config.yaml"

# Cleanup function to ensure tunnel is stopped
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ -f "$STOP_TUNNEL_SCRIPT" ]; then
        bash "$STOP_TUNNEL_SCRIPT" || true
    fi
}

# Set up trap to cleanup on exit
trap cleanup EXIT INT TERM

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Run ./setup_venv.sh first."
    exit 1
fi

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Warning: config.yaml not found. Using defaults."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Start SSH tunnel
echo "Starting SSH tunnel..."
if [ -f "$TUNNEL_SCRIPT" ]; then
    bash "$TUNNEL_SCRIPT"
    # Wait for tunnel to be ready (check if port is listening)
    echo "Waiting for tunnel to establish..."
    MAX_WAIT=10
    WAIT_COUNT=0
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        if command -v nc >/dev/null 2>&1; then
            if nc -z 127.0.0.1 8332 >/dev/null 2>&1; then
                echo "Tunnel is ready!"
                break
            fi
        elif command -v timeout >/dev/null 2>&1 && timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/8332" 2>/dev/null; then
            echo "Tunnel is ready!"
            break
        fi
        sleep 1
        WAIT_COUNT=$((WAIT_COUNT + 1))
    done
    
    if [ $WAIT_COUNT -eq $MAX_WAIT ]; then
        echo "Warning: Could not verify tunnel is ready. Proceeding anyway..."
    fi
else
    echo "Warning: $TUNNEL_SCRIPT not found. Assuming tunnel is already running."
    echo "If you see connection errors, ensure the SSH tunnel is active."
fi

# Run Blockscope with all passed arguments
echo "Starting Blockscope..."
echo "Press Ctrl+C to stop."
echo ""

# Check if event watcher mode is requested
if [[ "$*" == *"--watch-events"* ]]; then
    echo "Running in Event Monitoring mode..."
fi

# Pass all arguments to feesentinel (--config will be handled if not already specified)                                                                         
if [[ "$*" != *"--config"* ]]; then
    python -m feesentinel --config "$CONFIG_FILE" "$@"
else
    python -m feesentinel "$@"
fi

