#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

#export LOG_LEVEL=DEBUG
export LOG_LEVEL=INFO
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
