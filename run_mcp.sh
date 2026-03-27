#!/usr/bin/env bash
# run_mcp.sh
# Safely run the MCP code-memory server using the project's virtual environment

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment python not found at $VENV_PYTHON."
    echo "Please ensure you have created the virtual environment and installed dependencies."
    exit 1
fi

# Disable ChromaDB / PostHog telemetry (background thread causes segfault on Python 3.13)
export ANONYMIZED_TELEMETRY=False
export CHROMA_TELEMETRY=False
export POSTHOG_DISABLED=1

exec "$VENV_PYTHON" "$PROJECT_DIR/main.py" --mcp
