from fastapi import FastAPI, HTTPException
import requests, os, sqlite3, datetime, json
from openai import OpenAI

app = FastAPI(title="PlexStaffAI")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "") + "/api/v1"
headers = {"X-Api-Key": os.getenv("OVERSEERR_API_KEY")}
DB_PATH = "/config/staffai.db"

def init_db():
    sqlite3.connect(DB_PATH).execute('CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, data TEXT)')
init_db()

@app.get("/")
def root():
    return {"PlexStaffAI": "Running", "ui": "/docs", "moderate": "/staff/moderate"}

@app.get("/staff/moderate")
def moderate():
    try:
        resp = requests.get(OVERSEERR_URL + "/request?pending=true&take=3", headers=headers)
        reqs = resp.json()['results']
        results = []
        for req in reqs:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Approve or reject Plex request '{req['media']['title']}'? Say APPROVE or REJECT ONLY."}]
            )
            decision = completion.choices[0].message.content.strip()
            # Log (mock approve pour test)
            sqlite3.connect(DB_PATH).execute("INSERT INTO decisions (data) VALUES (?)", (json.dumps(req),))
            results.append({"id": req['id'], "decision": decision})
        return {"success": True, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "test_mode": True}

@app.get("/staff/report")
def report():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    return {"total_decisions": count}
