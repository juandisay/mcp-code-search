#!/bin/bash

# MCP Indexer Wrapper with venv detection
# Usage: ./bin/mcp-index.sh /path/to/project

# Get the script directory and resolve project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

# Detect Virtual Environment
if [ -d ".venv" ]; then
    VENV_PATH=".venv"
elif [ -d "venv" ]; then
    VENV_PATH="venv"
else
    echo "Error: Virtual environment (.venv or venv) not found in $PROJECT_ROOT"
    echo "Please create one using: python3.12 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate and Run
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

# Pass all arguments to main.py
python main.py --index "$@"
