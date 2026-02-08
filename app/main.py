from fastapi import FastAPI, HTTPException
import requests
import os
import sqlite3
from datetime import datetime
from openai import OpenAI
import json

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055") + "/api/v1"
headers = {"X-Api-Key": os.getenv("OVERSEERR_API_KEY")}
DB_PATH = "/config/staffai.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS decisions 
                 (id INTEGER PRIMARY KEY, request_id INT, decision TEXT, reason TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()
init_db()

@app.get("/")
def root():
    return {"message": "PlexStaffAI v1.0 - UI: /docs"}

@app.get("/staff/moderate")
def moderate_requests():
    try:
        resp = requests.get(f"{OVERSEERR_URL}/request?pending=true&take=5", headers=headers)
        reqs = resp.json()['results']
        results = []
        for req in reqs:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Requête Plex: {req['media']['title']}. Commentaire: {req.get('requestComment', '')}. Réponds 'approve' ou 'reject' UNIQUEMENT."}]
            )
            decision = response.choices[0].message.content.strip().lower()
            
            if 'approve' in decision:
                requests.patch(f"{OVERSEERR_URL}/request/{req['id']}", headers=headers, json={"approved": True})
                action = "approved"
            else:
                requests.patch(f"{OVERSEERR_URL}/request/{req['id']}", headers=headers, json={"autoApproved": False})
                action = "rejected"
            
            # Log DB
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO decisions VALUES (NULL, ?, ?, ?, ?)", 
                        (req['id'], action, decision, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            results.append({"id": req['id'], "action": action})
        return {"moderated": len(results), "results": results}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/staff/report")
def report():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    recent = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 5").fetchall()
    conn.close()
    return {"total_decisions": count, "recent": recent}
