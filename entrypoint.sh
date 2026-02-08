#!/bin/bash
set -e

# Init
mkdir -p /config /logs
cp -n /app/config.json.example /config/config.json || true

# DB init via main.py
python -c "from app.main import init_db; init_db()"

# Cron: moderate every 30min
(crontab -l 2>/dev/null; echo "*/30 * * * * cd /app && python app/jobs.py") | crontab -

# Logs cron
service cron start

# FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --reload --log-level info
