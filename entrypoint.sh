#!/bin/bash
set -e

echo "🚀 PlexStaffAI v2 - /app/main.py"

# Dirs
mkdir -p /app/data /app/logs /config

# Test import
cd /app
python -c "
import sys
sys.path.insert(0, '/app')
try:
    from app import main
    print('✅ app.main:app OK')
except ImportError as e:
    print('❌ ERROR:', e)
    import os; print('Files:', os.listdir('.'))
    sys.exit(1)
"

# Cron (15min → OK, webhook principal)
echo "*/15 * * * * curl -s -f http://localhost:5056/admin/moderate-now >> /app/logs/cron.log 2>&1" > /etc/cron.d/plexstaffai
chmod 0644 /etc/cron.d/plexstaffai
crond -f -L /app/logs/cron.log &

# Uvicorn app.main:app
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
