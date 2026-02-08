#!/bin/bash
set -e

mkdir -p /config /logs

# Cron auto-modération toutes les 15min
echo "*/15 * * * * curl -s http://localhost:5056/staff/moderate >> /logs/auto-moderate.log 2>&1" > /etc/cron.d/plexstaffai
chmod 0644 /etc/cron.d/plexstaffai

cron && echo "✅ Cron started (auto-moderate every 15min)"

# FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
