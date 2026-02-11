#!/bin/bash
set -e

echo "🚀 PlexStaffAI v2 Starting..."

mkdir -p /app/data /app/logs

cd /app

# Vérif deps
pip list | grep -E "(fastapi|openai)" || echo "⚠️ Some deps missing"

# Test app.main
python -c "
import sys
sys.path.insert(0, '/app')
try:
    from app.main import app
    print('✅ app.main:app loaded')
except ImportError as e:
    print('❌ Import fail:', e)
    sys.exit(1)
"

# Cron
echo "*/15 * * * * curl -s http://localhost:5056/admin/moderate-now >> /app/logs/cron.log 2>&1" > /etc/cron.d/plexstaffai
chmod 0644 /etc/cron.d/plexstaffai
crond -f -L /app/logs/cron.log &

# FastAPI
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
