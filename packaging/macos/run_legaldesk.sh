#!/bin/bash
# Quick start script for running LegalDesk on macOS without building an installer

set -e

echo "=== LegalDesk macOS Quick Start ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "WARNING: This script is designed for macOS."
    echo "Continuing anyway, but some features may not work correctly."
fi

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Install dependencies if needed
echo "Checking dependencies..."
pip3 install -q -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || true

# Set data directory
export LEGALDESK_DATA_DIR="$HOME/Library/Application Support/LegalDesk"
mkdir -p "$LEGALDESK_DATA_DIR/logs"

echo "Starting LegalDesk server..."
echo "Data directory: $LEGALDESK_DATA_DIR"
echo ""

# Run the launcher
python3 "$PROJECT_ROOT/desktop/launcher.py" --host 127.0.0.1 --port 8000

echo ""
echo "LegalDesk has been stopped."
