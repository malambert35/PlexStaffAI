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
        resp = requests.get(f"{OVERSEERR_URL}/request?filter=pending&take=10&sort=added", 
                          headers=headers, timeout=10)
        reqs = resp.json().get('results', [])
        results = []
        conn = sqlite3.connect(DB_PATH)
        
        for req in reqs:
            req_id = req.get('id')
            
            # EXTRACTION TITRE ROBUSTE (plusieurs chemins possibles)
            media = req.get('media', {})
            title = (
                media.get('title') or 
                media.get('name') or 
                media.get('originalTitle') or 
                media.get('originalName') or 
                f"TMDB-{media.get('tmdbId', '?')}"
            )
            
            # Contexte additionnel pour IA
            media_type = req.get('type', 'unknown')  # movie/tv
            requested_by = req.get('requestedBy', {}).get('displayName', 'Unknown')
            year = media.get('releaseDate', '')[:4] if media.get('releaseDate') else ''
            
            # LOG DEBUG (vérif extraction)
            print(f"[DEBUG] Request #{req_id}: title='{title}', type={media_type}, year={year}, user={requested_by}")
            
            # IA Decision avec CONTEXTE enrichi
            if client:
                try:
                    prompt = f"""Plex Overseerr request analysis:
- Title: {title}
- Type: {media_type}
- Year: {year or 'unknown'}
- Requested by: {requested_by}

Should staff APPROVE or REJECT? 
Rules: Approve legitimate movies/shows. Reject spam, duplicates, inappropriate content.
Answer: APPROVE or REJECT with brief reason (max 40 words)."""
                    
                    completion = client.chat.completions.create(
                        model="gpt-4o-mini",
                        max_tokens=60,
                        temperature=0.2,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    decision = completion.choices[0].message.content.strip()
                except Exception as e:
                    decision = f"APPROVE - IA error: {str(e)[:30]}"
            else:
                decision = "APPROVE - No OpenAI key (default approve all)"
            
            action = "APPROVED" if "APPROVE" in decision.upper() else "REJECTED"
            reason = decision[:120]
            
            # API OVERSEERR (approve/decline)
            try:
                if action == "APPROVED":
                    patch_resp = requests.post(
                        f"{OVERSEERR_URL}/request/{req_id}/approve",
                        headers=headers,
                        timeout=10
                    )
                    api_status = "✅ Approved" if patch_resp.status_code == 200 else f"⚠️ Error {patch_resp.status_code}"
                else:
                    patch_resp = requests.post(
                        f"{OVERSEERR_URL}/request/{req_id}/decline",
                        headers=headers,
                        timeout=10
                    )
                    api_status = "❌ Declined" if patch_resp.status_code == 200 else f"⚠️ Error {patch_resp.status_code}"
            except Exception as e:
                api_status = f"⚠️ API failed: {str(e)[:40]}"
            
            # Save DB
            full_context = f"{title} ({media_type} {year}) by {requested_by}"
            conn.execute("INSERT INTO decisions (request_id, decision, reason, timestamp) VALUES (?, ?, ?, ?)",
                        (req_id, action, f"{full_context} | {reason} | {api_status}", datetime.datetime.now().isoformat()))
            
            results.append({
                "id": req_id,
                "title": full_context,
                "action": action,
                "reason": reason,
                "api_status": api_status
            })
        
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

@app.get("/debug/overseerr")
async def debug_overseerr():
    """Debug Overseerr API connection et requests"""
    try:
        resp_all = requests.get(f"{OVERSEERR_URL}/request?take=10", headers=headers, timeout=10)
        all_data = resp_all.json()
        
        resp_pending = requests.get(f"{OVERSEERR_URL}/request?filter=pending&take=10", headers=headers, timeout=10)
        pending_data = resp_pending.json()
        
        statuses = {}
        for req in all_data.get('results', []):
            status = req.get('status', 'unknown')
            statuses[status] = statuses.get(status, 0) + 1
        
        return {
            "config": {
                "overseerr_url": OVERSEERR_URL,
                "api_key_configured": bool(headers.get("X-Api-Key")),
                "api_key_length": len(headers.get("X-Api-Key", "")) if headers.get("X-Api-Key") else 0
            },
            "results": {
                "all_requests": all_data.get('pageInfo', {}).get('results', 0),
                "filter_pending": pending_data.get('pageInfo', {}).get('results', 0)
            },
            "status_breakdown": statuses,
            "sample_requests": [
                {
                    "id": r.get('id'),
                    "title": r.get('media', {}).get('title'),
                    "status": r.get('status'),
                    "type": r.get('type')
                } for r in all_data.get('results', [])[:3]
            ]
        }
    except Exception as e:
        return {
            "error": str(e),
            "config": {
                "overseerr_url": OVERSEERR_URL,
                "api_key_set": bool(headers.get("X-Api-Key"))
            }
        }

@app.get("/moderate-html", response_class=HTMLResponse)
async def moderate_html():
    """HTML fragment avec raisons IA complètes"""
    result = await moderate_requests()
    
    if result.get("status") == "error":
        error_msg = result.get('message', 'Erreur inconnue')
        return """
        <div class="bg-red-900/50 p-6 rounded-xl border border-red-700">
            <h3 class="text-xl font-bold text-red-300 mb-2">❌ Erreur Connexion</h3>
            <p class="text-red-200">Impossible de contacter Overseerr</p>
            <p class="text-sm text-red-400 mt-2">Détails: {error}</p>
            <a href="/debug/overseerr" target="_blank" class="text-blue-400 underline text-sm mt-2 block">
                🔍 Voir diagnostic complet
            </a>
        </div>
        """.format(error=error_msg)
    
    results = result.get('results', [])
    count = result.get('count', 0)
    
    if count == 0:
        return """
        <div class="bg-yellow-900/50 p-6 rounded-xl border border-yellow-700">
            <h3 class="text-xl font-bold text-yellow-300 mb-2">⚠️ Queue Vide</h3>
            <p class="text-yellow-200">Aucune request pending dans Overseerr</p>
            <a href="/debug/overseerr" target="_blank" class="text-blue-400 underline text-sm mt-3 block">
                🔍 Voir toutes les requests
            </a>
        </div>
        """
    
    # HTML avec raisons + API status
    html_items = ""
    for r in results:
        action = r.get('action', 'UNKNOWN')
        title = r.get('title', 'N/A')
        req_id = r.get('id', '?')
        reason = r.get('reason', 'No reason')
        api_status = r.get('api_status', '')
        color = "green" if action == "APPROVED" else "red"
        icon = "✅" if action == "APPROVED" else "❌"
        
        html_items += """
        <div class="p-4 bg-gray-700/50 rounded-lg border border-gray-600 hover:bg-gray-700 transition-all duration-200">
            <div class="flex justify-between items-start mb-2">
                <div class="flex-1">
                    <span class="font-bold text-white text-lg">{title}</span>
                    <span class="text-xs text-gray-400 ml-2">#{req_id}</span>
                </div>
                <div class="text-{color}-400 font-black text-2xl">{icon} {action}</div>
            </div>
            <div class="text-sm text-gray-300 italic mb-1 bg-gray-800/50 p-2 rounded">💬 {reason}</div>
            <div class="text-xs text-gray-500 mt-1">{api_status}</div>
        </div>
        """.format(title=title, req_id=req_id, color=color, icon=icon, action=action, reason=reason, api_status=api_status)
    
    return """
    <div class="bg-gray-800/50 backdrop-blur-xl p-8 rounded-3xl border border-gray-700">
        <h3 class="text-2xl font-bold mb-6 flex items-center text-white">
            <span class="w-3 h-3 bg-green-400 rounded-full mr-3 animate-pulse"></span>
            ✅ Modération IA Terminée ({count} requests)
        </h3>
        <div class="space-y-3">{items}</div>
        <div class="mt-6 p-4 bg-blue-900/30 rounded-lg border border-blue-700">
            <p class="text-blue-300 text-sm">💡 Actions appliquées dans Overseerr + enregistrées en DB locale</p>
        </div>
    </div>
    """.format(count=count, items=html_items)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.4",
        "db": os.path.exists(DB_PATH),
        "openai": bool(get_openai_client()),
        "overseerr_configured": bool(headers.get("X-Api-Key"))
    }
