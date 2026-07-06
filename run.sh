#!/bin/bash
#export LOG_LEVEL=DEBUG
export LOG_LEVEL=INFO
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
