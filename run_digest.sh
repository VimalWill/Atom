#!/bin/bash
# Runner script - triggered on login/wake
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Small delay to ensure network is up
sleep 10

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Activate virtual environment and run
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/agent.py" "$@"
