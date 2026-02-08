from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import requests
import os
import sqlite3
import datetime
import json
from openai import OpenAI
import httpx

app = FastAPI(title="PlexStaffAI", version="1.4")
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055") + "/api/v1"
headers = {"X-Api-Key": os.getenv("OVERSEERR_API_KEY")}
DB_PATH = "/config/staffai.db"
_client = None

# Lazy OpenAI (no crash startup)
def get_openai_client():
    global _client
    if _client is None and os.getenv("OPENAI_API_KEY"):
        try:
            _client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                http_client=httpx.Client(proxies=None, timeout=30.0)
            )
            return _client
        except Exception as e:
            print(f"OpenAI init error: {e}")
    return _client

# Static dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    """Safe DB recreate"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS decisions')
        c.execute('''CREATE TABLE decisions 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      request_id INTEGER, decision TEXT, reason TEXT, timestamp TEXT)''')
        conn.commit()
        conn.close()
        print("✅ DB v1.4 ready")
    except Exception as e:
        print(f"DB error: {e}")

init_db()

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("static/index.html", "r") as f:
            return f.read()
    except:
        return "<h1>🚀 PlexStaffAI <br> Créez <code>static/index.html</code></h1>"

@app.get("/staff/moderate")
async def moderate_requests():
    try:
        client = get_openai_client()
        resp = requests.get(f"{OVERSEERR_URL}/request?pending=true&take=5", 
                          headers=headers, timeout=10)
        reqs = resp.json().get('results', [])
        results = []
        conn = sqlite3.connect(DB_PATH)
        
        for req in reqs:
            title = req['media'].get('title', 'N/A')
            if client:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=20,
                    temperature=0.1,
                    messages=[{
                        "role": "user",
                        "content": f"Plex request: {title}. APPROVE or REJECT ONLY."
                    }]
                )
                decision = completion.choices[0].message.content.strip().upper()
            else:
                decision = "MOCK_APPROVE"
            
            action = "APPROVED" if "APPROVE" in decision else "REJECTED"
            reason = decision[:50]
            
            conn.execute("INSERT INTO decisions (request_id, decision, reason, timestamp) VALUES (?, ?, ?, ?)",
                        (req.get('id'), action, reason, datetime.datetime.now().isoformat()))
            results.append({"id": req.get('id'), "title": title, "action": action})
        
        conn.commit()
        conn.close()
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/staff/report")
async def staff_report():
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM decisions WHERE decision LIKE '%APPROVED%'").fetchone()[0]
        pct = round((approved/total*100) if total else 0)
        last_time = conn.execute("SELECT timestamp FROM decisions ORDER BY id DESC LIMIT 1").fetchone()
        last_run = last_time[0][:16] if last_time else "--"
        recent_count = conn.execute("SELECT COUNT(*) FROM decisions WHERE timestamp > datetime('now', '-1 day')").fetchone()[0]
        conn.close()
        return {
            "total": total, "approved": approved, "pct": pct,
            "last_run": last_run, "recent_24h": recent_count
        }
    except Exception as e:
        return {"error": str(e), "total": 0, "last_run": "--"}

@app.get("/stats", response_class=HTMLResponse)
async def stats_fragment():
    report = await staff_report()
    total = report.get('total', 0)
    last_run = report.get('last_run', '--')
    pct = report.get('pct', 0)
    recent = report.get('recent_24h', 0)
    
    html = """
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 p-8 rounded-2xl shadow-2xl border border-gray-700">
            <h3 class="text-lg font-semibold text-gray-400 mb-4">📊 Total</h3>
            <div class="text-4xl font-black text-green-400">{total}</div>
        </div>
        <div class="bg-gradient-to-br from-indigo-900 to-purple-900 p-8 rounded-2xl shadow-2xl">
            <h3 class="text-lg font-semibold text-gray-300 mb-2">⏰ Dernier</h3>
            <div class="text-2xl font-bold text-indigo-300">{last_run}</div>
            <div class="text-sm text-indigo-400">{pct}% OK</div>
        </div>
        <div class="bg-gradient-to-br from-emerald-900 to-teal-900 p-8 rounded-2xl shadow-2xl">
            <h3 class="text-lg font-semibold text-gray-300 mb-4">🔥 24h</h3>
            <div class="text-3xl font-bold text-emerald-400">{recent}</div>
        </div>
    </div>
    """.format(total=total, last_run=last_run, pct=pct, recent=recent)
    return html

@app.get("/health")
async def health():
    return {"status": "healthy", "db": os.path.exists(DB_PATH), "openai": bool(get_openai_client())}
