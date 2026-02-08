#!/bin/bash
set -e

mkdir -p /config /logs

# Cron curl (30min)
echo "*/30 * * * * curl -s localhost:5056/staff/moderate -o /logs/moderate.\$(date +%%s).log" > /etc/cron.d/plexstaffai
chmod 0644 /etc/cron.d/plexstaffai

cron && echo "Cron started"

# FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
