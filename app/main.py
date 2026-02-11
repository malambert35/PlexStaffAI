from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os, sqlite3, json, httpx
from datetime import datetime
from pathlib import Path
import aiosqlite  # Async DB

app = FastAPI(title="PlexStaffAI v2")
app.mount("/static", StaticFiles(directory="static"), name="static")

OVERSEERR_URL = os.getenv("OVERSEERR_URL", "http://overseerr:5055")
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY")
DB_PATH = Path("/app/data/plexstaffai.db")

@app.on_event("startup")
async def startup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                request_id INTEGER,
                title TEXT,
                username TEXT,
                decision TEXT,
                reason TEXT,
                confidence REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    print("🚀 DB ready")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html><head><title>PlexStaffAI</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/htmx.org@1.9.10"></script></head>
<body class="bg-gray-900 p-8 text-white min-h-screen">
<div class="max-w-6xl mx-auto">
<h1 class="text-5xl font-bold mb-12 bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">
PlexStaffAI v2 - AI Moderation Dashboard ⚡
</h1>
<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
<div hx-get="/stats" hx-trigger="load, every 5s" 
hx-swap="innerHTML" class="bg-gradient-to-br from-indigo-900 to-blue-900 p-8 rounded-3xl border border-indigo-700">
<h3 class="text-xl font-bold mb-4 text-indigo-300">Stats</h3><div id="stats"></div>
</div>
<div class="md:col-span-3">
<button hx-post="/admin/moderate-now" hx-swap="afterend" 
class="bg-emerald-600 hover:bg-emerald-700 px-8 py-4 rounded-2xl font-bold text-xl mb-4">
🔄 Moderate Pending Now
</button>
<div hx-get="/staff/reviews" hx-trigger="load" hx-swap="innerHTML" 
class="bg-gray-800 p-8 rounded-2xl border border-gray-700 space-y-4" id="reviews">
Loading reviews...
</div>
</div>
</div>
<a href="/history" class="bg-purple-600 hover:bg-purple-700 px-8 py-4 rounded-2xl font-bold">
📊 Full History
</a>
</div>
</body></html>
    """

@app.get("/stats")
async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM reviews")
        total = (await cursor.fetchone())[0]
    return {"total_reviews": total, "overseerr": OVERSEERR_URL, "status": "healthy"}

@app.get("/staff/reviews")
async def reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT request_id, title, username, decision, reason, confidence 
            FROM reviews ORDER BY created_at DESC LIMIT 10
        """)
        rows = await cursor.fetchall()
    return [{"request_id": r[0], "title": r[1], "username": r[2], "decision": r[3], 
             "reason": r[4], "confidence": r[5]} for r in rows]

@app.post("/admin/moderate-now")
async def moderate_now():
    print("🔄 Manual moderate triggered")
    return {"status": "triggered", "message": "Check logs"}

@app.post("/webhook/overseerr")
async def webhook(request: Request):
    payload = await request.json()
    req_id = payload.get("request", {}).get("id")
    print(f"⚡ Webhook: Request #{req_id}")
    # Mock save (full IA next)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO reviews (request_id, title, username, decision) VALUES (?, ?, ?, ?)",
                        (req_id, payload.get("subject", "Unknown"), "Webhook", "PENDING"))
        await db.commit()
    return {"status": "moderated", "request_id": req_id}

@app.get("/history")
async def history():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 50")
        rows = await cursor.fetchall()
    return [{"id": r[0], **{k: v for k, v in zip(["request_id", "title", "username", "decision", "reason", "confidence"], r[1:6])}} for r in rows]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
