#!/bin/bash
set -e

mkdir -p /config /logs

# Cron système natif (30min moderate)
echo "*/30 * * * * curl -s localhost:5056/staff/moderate >> /logs/cron.log 2>&1" > /etc/cron.d/plexstaffai
chmod 0644 /etc/cron.d/plexstaffai
service cron start

# DB init
python -c "
import sqlite3
conn = sqlite3.connect('/config/staffai.db')
conn.execute('CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, data TEXT)')
conn.commit()
print('DB OK')
"

# FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
