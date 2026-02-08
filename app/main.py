from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import requests
import os
import sqlite3
import datetime
import json
from openai import OpenAI
import httpx  # Fix conflit

app = FastAPI(title="PlexStaffAI", version="1.2")
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055") + "/api/v1"
headers = {"X-Api-Key": os.getenv("OVERSEERR_API_KEY")}
DB_PATH = "/config/staffai.db"
_client = None

# Lazy OpenAI init (no startup crash)
def get_openai_client():
    global _client
    if _client is None and os.getenv("OPENAI_API_KEY"):
        _client = OpenAI(api_key=os.getenv("OPENSE_API_KEY"), http_client=httpx.Client(proxies=None))
    return _client

# Static UI
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS decisions 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      request_id INTEGER, decision TEXT, reason TEXT, timestamp TEXT)''')
        conn.commit()
        conn.close()
        print("✅ DB initialized")
    except Exception as e:
        print(f"DB error: {e}")

init_db()

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("static/index.html") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <h1>🛠️ PlexStaffAI Setup</h1>
        <p>Créez <code>static/index.html</code> pour dashboard.</p>
        <p><a href="/docs">API Docs →</a></p>
        """

@app.get("/staff/moderate")
async def moderate_requests():
    try:
        client = get_openai_client()
        resp = requests.get(f"{OVERSEERR_URL}/request?pending=true&take=5", headers=headers, timeout=10)
        reqs = resp.json().get('results', [])
        results = []
        conn = sqlite3.connect(DB_PATH)
        
        for req in reqs:
            if client:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": f"Titre: {req['media'].get('title', 'N/A')}. Comment? {req.get('requestComment', '')}. APPROVE ou REJECT SEUL."
                    }],
                    temperature=0.1
                )
                decision = completion.choices[0].message.content.strip().upper()
            else:
                decision = "MOCK_APPROVE"  # Graceful fallback
            
            action = "APPROVED" if "APPROVE" in decision else "REJECTED"
            reason = decision[:50]
            
            conn.execute("INSERT INTO decisions (request_id, decision, reason, timestamp) VALUES (?, ?, ?, ?)",
                        (req.get('id'), action, reason, datetime.datetime.now().isoformat()))
            
            results.append({
                "id": req.get('id'),
                "title": req['media'].get('title', 'N/A'),
                "action": action,
                "reason": reason
            })
        
        conn.commit()
        conn.close()
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e), "openai_key": bool(os.getenv("OPENAI_API_KEY"))}

@app.get("/staff/report")
async def staff_report():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM decisions WHERE decision='APPROVED'").fetchone()[0]
    recent = conn.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    
    return {
        "total": total,
        "approved_pct": round((approved/total*100) if total else 0, 1),
        "recent": recent,
        "openai_ready": bool(get_openai_client())
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "db_ok": os.path.exists(DB_PATH)}
