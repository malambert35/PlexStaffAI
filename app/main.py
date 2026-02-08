from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import requests
import os
import sqlite3
import datetime
import json
from openai import OpenAI

app = FastAPI(title="PlexStaffAI", version="1.1")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055") + "/api/v1"
headers = {"X-Api-Key": os.getenv("OVERSEERR_API_KEY")}
DB_PATH = "/config/staffai.db"

# Static UI
app.mount("/static", StaticFiles(directory="static"), name="static")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS decisions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  request_id INTEGER, decision TEXT, reason TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()
init_db()

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("static/index.html", "r") as f:
            return f.read()
    except:
        return "<h1>PlexStaffAI 🖥️ Créez static/index.html pour UI</h1>"

@app.get("/staff/moderate")
async def moderate_requests():
    try:
        resp = requests.get(f"{OVERSEERR_URL}/request?pending=true&take=5", headers=headers, timeout=10)
        reqs = resp.json().get('results', [])
        results = []
        conn = sqlite3.connect(DB_PATH)
        
        for req in reqs:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user", 
                    "content": f"Requête Plex Overseerr: {req['media'].get('title', 'N/A')}. Commentaire: {req.get('requestComment', '')}. Réponds SEULEMENT 'APPROVE' ou 'REJECT'."
                }]
            )
            decision = completion.choices[0].message.content.strip().upper()
            
            # Mock API call (active tes clés pour réel)
            if 'APPROVE' in decision:
                action = "APPROVED"
                # requests.patch(...)  # Décommente prod
            else:
                action = "REJECTED"
            
            reason = decision
            conn.execute("INSERT INTO decisions (request_id, decision, reason, timestamp) VALUES (?, ?, ?, ?)",
                        (req.get('id'), action, reason, datetime.datetime.now().isoformat()))
            
            results.append({
                "id": req.get('id'), 
                "title": req['media'].get('title'), 
                "action": action,
                "reason": reason
            })
        
        conn.commit()
        conn.close()
        return {"status": "success", "moderated": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/staff/report")
async def staff_report():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    recent = conn.execute("""
        SELECT request_id, decision, reason, timestamp 
        FROM decisions ORDER BY timestamp DESC LIMIT 10
    """).fetchall()
    conn.close()
    
    # IA insights
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Insights staff Plex (total: {total}, recent: {recent[-3:]}): anomalies/alertes?"
            }]
        )
        insights = completion.choices[0].message.content
    except:
        insights = "OpenAI OK - Ajoute ta clé"
    
    return {
        "total_decisions": total,
        "recent": recent,
        "insights": insights,
        "cron_status": "Actif (30min)"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.1", "db_path": DB_PATH}
