#!/bin/sh
set -e


echo "Starting application..."
exec /app/.venv/bin/python -m uvicorn --port 8080 --host 0.0.0.0 main:app
