#!/bin/bash
# Convenience wrapper for running Event Monitoring mode
# Automatically adds --watch-events flag to run_fee_sentinel.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Call run_fee_sentinel.sh with --watch-events flag and pass through all arguments
exec "$SCRIPT_DIR/run_fee_sentinel.sh" --watch-events "$@"

