from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="PlexStaffAI v2")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html>
<head><title>PlexStaffAI</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 p-8 text-white">
<h1 class="text-4xl mb-8">PlexStaffAI v2 - Webhook Ready ⚡</h1>
<div id="stats" hx-get="/stats" hx-trigger="load"></div>
<button hx-post="/admin/moderate-now" hx-swap="afterend">Moderate Now</button>
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
</body>
</html>
    """

@app.get("/stats")
async def stats():
    return {"status": "OK", "port": 5056, "overseerr": os.getenv("OVERSEERR_URL")}

@app.post("/webhook/overseerr")
async def webhook(request: Request):
    payload = await request.json()
    print("Webhook:", payload)
    return {"status": "received", "request_id": payload.get("request", {}).get("id")}

@app.get("/admin/moderate-now")
async def moderate():
    return {"mock": "Moderation triggered - check logs"}

print("🚀 PlexStaffAI MINIMAL v2 - Replace your main.py")
