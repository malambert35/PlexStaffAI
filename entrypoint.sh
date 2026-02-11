#!/bin/bash
set -e

echo "🚀 PlexStaffAI v2 - Webhook Overseerr Only ⚡"

# Dirs
mkdir -p /app/data /app/logs /config

cd /app

# Test final
python -c "
import sys
sys.path.insert(0, '/app')
from app.main import app
print('✅ app.main:app → READY')
print('Routes:', len(app.routes))
"

# Uvicorn PROD (debug → info après test)
exec uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info --workers 1
