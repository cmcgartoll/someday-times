#!/usr/bin/env bash
set -euo pipefail

# Run DB migrations (safe to run repeatedly)
flask db upgrade

# Start web server
exec gunicorn -c gunicorn.conf.py app:app