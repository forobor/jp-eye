#!/bin/zsh
# Start the Japanese study brain on http://127.0.0.1:8765
cd "$(dirname "$0")"
exec .venv/bin/python -m uvicorn brain.server:app --host 127.0.0.1 --port "${JP_PORT:-8765}"
