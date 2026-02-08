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

app = FastAPI(title="PlexStaffAI", version="1.5")
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
        c.execute('''CREATE TABLE IF NOT EXISTS decisions 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      request_id INTEGER, decision TEXT, reason TEXT, timestamp TEXT)''')
        conn.commit()
        conn.close()
        print("✅ DB v1.5 ready")
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
            
            # EXTRACTION TITRE ROBUSTE
            media = req.get('media', {})
            title = (
                media.get('title') or 
                media.get('name') or 
                media.get('originalTitle') or 
                media.get('originalName') or 
                f"TMDB-{media.get('tmdbId', '?')}"
            )
            
            # Contexte additionnel
            media_type = req.get('type', 'unknown')
            requested_by = req.get('requestedBy', {}).get('displayName', 'Unknown')
            year = media.get('releaseDate', '')[:4] if media.get('releaseDate') else ''
            
            print(f"[AUTO-MODERATE] #{req_id}: {title} ({media_type} {year}) by {requested_by}")
            
            # IA Decision avec CONTEXTE
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
            
            # API OVERSEERR
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
        approved = conn.execute("SELECT COUNT(*) FROM decisions WHERE decision='APPROVED'").fetchone()[0]
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
    """Debug Overseerr API"""
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
                "api_key_configured": bool(headers.get("X-Api-Key"))
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
                    "status": r.get('status')
                } for r in all_data.get('results', [])[:3]
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/moderate-html", response_class=HTMLResponse)
async def moderate_html():
    """HTML fragment modération"""
    result = await moderate_requests()
    
    if result.get("status") == "error":
        error_msg = result.get('message', 'Erreur inconnue')
        return """
        <div class="bg-red-900/50 p-6 rounded-xl border border-red-700">
            <h3 class="text-xl font-bold text-red-300 mb-2">❌ Erreur</h3>
            <p class="text-red-200">{error}</p>
            <a href="/debug/overseerr" target="_blank" class="text-blue-400 underline text-sm mt-2 block">Debug</a>
        </div>
        """.format(error=error_msg)
    
    results = result.get('results', [])
    count = result.get('count', 0)
    
    if count == 0:
        return """
        <div class="bg-yellow-900/50 p-6 rounded-xl border border-yellow-700">
            <h3 class="text-xl font-bold text-yellow-300 mb-2">⚠️ Queue Vide</h3>
            <p class="text-yellow-200">Aucune request pending</p>
        </div>
        """
    
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
        <div class="p-4 bg-gray-700/50 rounded-lg border border-gray-600 hover:bg-gray-700 transition">
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
            ✅ Modération IA ({count} requests)
        </h3>
        <div class="space-y-3">{items}</div>
        <div class="mt-6 p-4 bg-blue-900/30 rounded-lg border border-blue-700">
            <p class="text-blue-300 text-sm">💡 Actions appliquées + enregistrées en DB</p>
        </div>
    </div>
    """.format(count=count, items=html_items)

@app.get("/history", response_class=HTMLResponse)
async def history_page():
    """Historique complet persistant"""
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM decisions WHERE decision='APPROVED'").fetchone()[0]
        rejected = total - approved
        
        rows = conn.execute("""
            SELECT id, request_id, decision, reason, timestamp 
            FROM decisions 
            ORDER BY id DESC 
            LIMIT 100
        """).fetchall()
        conn.close()
        
        html_rows = ""
        for row in rows:
            db_id, req_id, decision, reason, timestamp = row
            color = "text-green-400" if decision == "APPROVED" else "text-red-400"
            icon = "✅" if decision == "APPROVED" else "❌"
            time_short = timestamp[:16].replace('T', ' ')
            
            html_rows += """
            <tr class="border-b border-gray-700 hover:bg-gray-800/50 transition">
                <td class="p-3 text-gray-400 text-sm">#{db_id}</td>
                <td class="p-3 text-white font-semibold">{req_id}</td>
                <td class="p-3 {color} font-bold">{icon} {decision}</td>
                <td class="p-3 text-gray-300 text-sm italic max-w-md truncate">{reason}</td>
                <td class="p-3 text-gray-500 text-xs">{time}</td>
            </tr>
            """.format(db_id=db_id, req_id=req_id, color=color, icon=icon, decision=decision, reason=reason, time=time_short)
        
        return """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Historique PlexStaffAI</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-900 text-white">
            <div class="max-w-7xl mx-auto p-8">
                <div class="flex justify-between items-center mb-8">
                    <h1 class="text-5xl font-black bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
                        📜 Historique Modération
                    </h1>
                    <a href="/" class="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-xl font-bold transition shadow-xl">
                        ← Dashboard
                    </a>
                </div>
                
                <div class="grid grid-cols-3 gap-6 mb-8">
                    <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
                        <h3 class="text-gray-400 mb-2">Total</h3>
                        <div class="text-4xl font-bold text-white">{total}</div>
                    </div>
                    <div class="bg-green-900/30 p-6 rounded-xl border border-green-700">
                        <h3 class="text-green-400 mb-2">✅ Approved</h3>
                        <div class="text-4xl font-bold text-green-400">{approved}</div>
                    </div>
                    <div class="bg-red-900/30 p-6 rounded-xl border border-red-700">
                        <h3 class="text-red-400 mb-2">❌ Rejected</h3>
                        <div class="text-4xl font-bold text-red-400">{rejected}</div>
                    </div>
                </div>
                
                <div class="bg-gray-800 rounded-2xl overflow-hidden border border-gray-700 shadow-2xl">
                    <table class="w-full">
                        <thead class="bg-gray-900">
                            <tr>
                                <th class="p-4 text-left text-gray-400 font-semibold">ID</th>
                                <th class="p-4 text-left text-gray-400 font-semibold">Request</th>
                                <th class="p-4 text-left text-gray-400 font-semibold">Décision</th>
                                <th class="p-4 text-left text-gray-400 font-semibold">Raison IA</th>
                                <th class="p-4 text-left text-gray-400 font-semibold">Date</th>
                            </tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
                
                <div class="text-center mt-6 text-gray-500 text-sm">
                    100 dernières • DB: /config/staffai.db (persistant)
                </div>
            </div>
        </body>
        </html>
        """.format(total=total, approved=approved, rejected=rejected, rows=html_rows)
    except Exception as e:
        return f"<h1>Erreur DB: {e}</h1>"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.5",
        "db": os.path.exists(DB_PATH),
        "openai": bool(get_openai_client()),
        "overseerr_configured": bool(headers.get("X-Api-Key"))
    }
