#!/bin/bash
set -e

mkdir -p /config /logs

# Preserve a user-managed config volume while providing a usable first-run
# configuration. Without this, the image's bundled config.yaml is hidden by
# the /config bind mount and the service silently falls back to defaults.
if [ ! -f /config/config.yaml ]; then
    cp /app/config.yaml /config/config.yaml
    echo "Created /config/config.yaml from the bundled defaults"
fi

# Cron auto-modération toutes les 15min
echo "*/1 * * * * curl -s http://localhost:5056/staff/moderate >> /logs/auto-moderate.log 2>&1" > /etc/cron.d/plexstaffai
chmod 0644 /etc/cron.d/plexstaffai

cron && echo "✅ Cron started (auto-moderate every 1min)"

# FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
