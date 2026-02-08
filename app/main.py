from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import requests
import os
import sqlite3
import json
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel

app = FastAPI(title="PlexStaffAI", version="1.0")
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055") + "/api/v1"
headers = {"X-Api-Key": os.getenv("OVERSEERR_API_KEY")}
DB_PATH = "/config/staffai.db"
PORT = int(os.getenv("PORT", 5056))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS decisions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  request_id INTEGER, decision TEXT, reason TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

prompt_mod = PromptTemplate.from_template(
    """Analyse cette requête Plex Overseerr: Titre: {title}. Description/commentaire: {desc}. 
    Décide: 'approve' si légitime/qualité bonne, 'reject' si spam/abuse/duplicata. 
    Réponds UNIQUEMENT 'approve:raison_courte' ou 'reject:raison_courte'."""
)
chain_mod = prompt_mod | llm | StrOutputParser()

@app.get("/")
def root():
    return {"message": "PlexStaffAI running", "ui": f"http://localhost:{PORT}/docs"}

@app.get("/staff/moderate")
def moderate_requests():
    try:
        resp = requests.get(f"{OVERSEERR_URL}/request?pending=true&take=10", headers=headers, timeout=10)
        reqs = resp.json().get('results', [])
        results = []
        for req in reqs:
            decision_raw = chain_mod.invoke({
                "title": req['media'].get('title', ''), 
                "desc": req.get('requestComment', '')
            })
            if 'approve:' in decision_raw:
                action, reason = decision_raw.split(':', 1)
                requests.patch(f"{OVERSEERR_URL}/request/{req['id']}", 
                             headers=headers, json={"approved": True})
            else:
                action, reason = 'reject', decision_raw
                requests.patch(f"{OVERSEERR_URL}/request/{req['id']}", 
                             headers=headers, json={"autoApproved": False, "denyReason": reason})
            
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO decisions (request_id, decision, reason, timestamp) VALUES (?, ?, ?, ?)",
                         (req['id'], action.strip(), reason.strip(), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            results.append({"id": req['id'], "action": action.strip(), "reason": reason.strip()})
        return {"status": "success", "moderated": len(results), "details": results}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/staff/report")
def staff_report():
    conn = sqlite3.connect(DB_PATH)
    recent = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT 10").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    conn.close()
    prompt_rep = PromptTemplate.from_template(
        "Génère rapport staff: {recent}. Stats: {total} décisions. Alertes/anomalies/insights?")
    chain_rep = prompt_rep | llm | StrOutputParser()
    report = chain_rep.invoke({"recent": str(recent), "total": total})
    return {"report": report, "stats": {"total_decisions": total, "recent": recent}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
