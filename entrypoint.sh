#!/bin/bash
set -e

echo "🚀 PlexStaffAI v2 Starting..."

# Dirs
mkdir -p /app/data /app/logs

# Test import AVANT uvicorn
cd /app
python -c "import sys; print('Python path:', sys.path)"
python -c "
try:
    import main
    print('✅ main.py OK')
    print('App:', hasattr(main, 'app'))
except ImportError as e:
    print('❌ Import ERROR:', e)
    sys.exit(1)
"
# Uvicorn - TEST LES DEUX
echo "🔄 Trying uvicorn main:app..."
uvicorn main:app --host 0.0.0.0 --port 5056 --log-level info || {
    echo "🔄 Trying uvicorn app.main:app..."
    uvicorn app.main:app --host 0.0.0.0 --port 5056 --log-level info
}
