from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import json

# ✨ IMPORTS CORRIGÉS - Utilise chemin absolu depuis app/
from app.config_loader import ConfigManager, SmartModerator, ModerationDecision
from app.ml_feedback import FeedbackDatabase, EnhancedModerator

app = FastAPI(title="PlexStaffAI", version="1.6.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OVERSEERR_API_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055")
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY")

# ✨ NOUVEAU: Charger config personnalisée + ML
config = ConfigManager("/config/config.yaml")
feedback_db = FeedbackDatabase("/config/feedback.db")
moderator = EnhancedModerator(config, feedback_db)

# Database
DB_PATH = "/config/moderation.db"

def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Decisions table (historique)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            decision TEXT,
            reason TEXT,
            confidence REAL DEFAULT 1.0,
            rule_matched TEXT DEFAULT 'legacy',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ✨ NOUVEAU: Pending reviews table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER UNIQUE,
            request_data JSON,
            ai_decision TEXT,
            ai_reason TEXT,
            ai_confidence REAL,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard"""
    with open("static/index.html", "r") as f:
        return f.read()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.6.0",
        "openai": "configured" if OPENAI_API_KEY else "missing",
        "overseerr": "configured" if OVERSEERR_API_URL else "missing",
        "ml_enabled": config.get("machine_learning.enabled", True)
    }


def get_overseerr_requests():
    """Fetch pending requests from Overseerr"""
    try:
        response = httpx.get(
            f"{OVERSEERR_API_URL}/api/v1/request",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            params={"take": 50, "skip": 0, "filter": "pending"},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"Error fetching Overseerr requests: {e}")
        return []


def approve_overseerr_request(request_id: int):
    """Approve request in Overseerr"""
    try:
        response = httpx.post(
            f"{OVERSEERR_API_URL}/api/v1/request/{request_id}/approve",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error approving request {request_id}: {e}")
        return False


def decline_overseerr_request(request_id: int):
    """Decline request in Overseerr"""
    try:
        response = httpx.post(
            f"{OVERSEERR_API_URL}/api/v1/request/{request_id}/decline",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error declining request {request_id}: {e}")
        return False


def moderate_request(request_id: int, request_data: dict) -> dict:
    """Moderate request with smart rules + ML"""
    
    # Extract metadata from Overseerr
    media = request_data.get('media', {})
    title = (
        media.get('title') or 
        media.get('name') or 
        media.get('originalTitle') or 
        media.get('originalName') or 
        f"TMDB-{media.get('tmdbId', 'unknown')}"
    )
    
    media_type = media.get('mediaType', 'unknown')
    year = media.get('releaseDate', '')[:4] if media.get('releaseDate') else ''
    requested_by = request_data.get('requestedBy', {}).get('displayName', 'unknown')
    user_id = str(request_data.get('requestedBy', {}).get('id', 'unknown'))
    
    # ✨ Enrichir data pour modération intelligente
    enriched_data = {
        'title': title,
        'media_type': media_type,
        'year': year,
        'requested_by': requested_by,
        'user_id': user_id,
        'rating': media.get('voteAverage', 0),
        'popularity': media.get('popularity', 0),
        'genres': [g.get('name', '') for g in media.get('genres', [])],
        'episode_count': sum(s.get('episodeCount', 0) for s in media.get('seasons', [])),
        'season_count': len(media.get('seasons', [])),
        'awards': [],  # TODO: Fetch from TMDB if available
    }
    
    # Calculer user_age_days depuis Overseerr
    user_created = request_data.get('requestedBy', {}).get('createdAt', '')
    if user_created:
        try:
            created_date = datetime.fromisoformat(user_created.replace('Z', '+00:00'))
            enriched_data['user_age_days'] = (datetime.now(created_date.tzinfo) - created_date).days
        except:
            enriched_data['user_age_days'] = 999
    
    # ✨ NOUVELLE LOGIQUE: Config rules + ML
    decision_result = moderator.moderate_with_learning(enriched_data)
    
    decision = decision_result['decision']
    reason = decision_result['reason']
    confidence = decision_result.get('confidence', 1.0)
    rule_matched = decision_result.get('rule_matched', 'none')
    
    # ✨ GESTION NEEDS_REVIEW
    if decision == ModerationDecision.NEEDS_REVIEW:
        save_for_review(request_id, enriched_data, decision_result)
        return {
            'decision': 'NEEDS_REVIEW',
            'reason': reason,
            'confidence': confidence,
            'action': 'pending_staff_review'
        }
    
    # Actions Overseerr (APPROVE/REJECT)
    if decision == ModerationDecision.APPROVED:
        approve_overseerr_request(request_id)
    elif decision == ModerationDecision.REJECTED:
        decline_overseerr_request(request_id)
    
    # Save to database
    save_decision(request_id, decision, reason, confidence, rule_matched)
    
    return {
        'request_id': request_id,
        'decision': decision,
        'reason': reason,
        'confidence': confidence,
        'rule_matched': rule_matched
    }


def save_for_review(request_id: int, request_data: dict, decision_result: dict):
    """Save request for staff review"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO pending_reviews 
        (request_id, request_data, ai_decision, ai_reason, ai_confidence)
        VALUES (?, ?, ?, ?, ?)
    """, (
        request_id,
        json.dumps(request_data),
        decision_result['decision'],
        decision_result['reason'],
        decision_result.get('confidence', 0.5)
    ))
    
    conn.commit()
    conn.close()


def save_decision(request_id: int, decision: str, reason: str, 
                 confidence: float, rule_matched: str):
    """Save decision to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO decisions 
        (request_id, decision, reason, confidence, rule_matched)
        VALUES (?, ?, ?, ?, ?)
    """, (request_id, decision, reason, confidence, rule_matched))
    conn.commit()
    conn.close()


@app.get("/staff/moderate")
@app.post("/staff/moderate")
async def manual_moderate():
    """Manually trigger moderation"""
    requests = get_overseerr_requests()
    
    if not requests:
        return {"message": "No pending requests", "moderated": 0}
    
    results = []
    for req in requests:
        result = moderate_request(req['id'], req)
        results.append(result)
    
    return {
        "message": f"Moderated {len(results)} requests",
        "results": results
    }


@app.get("/staff/report")
async def moderation_report():
    """Get moderation statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total stats
    cursor.execute("SELECT decision, COUNT(*) FROM decisions GROUP BY decision")
    stats = dict(cursor.fetchall())
    
    # Last 24h
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute(
        "SELECT decision, COUNT(*) FROM decisions WHERE timestamp > ? GROUP BY decision",
        (yesterday,)
    )
    last_24h = dict(cursor.fetchall())
    
    conn.close()
    
    total = sum(stats.values())
    approved = stats.get('APPROVED', 0)
    
    return {
        "total_decisions": total,
        "approved": approved,
        "rejected": stats.get('REJECTED', 0),
        "needs_review": stats.get('NEEDS_REVIEW', 0),
        "approval_rate": round(approved / total * 100, 1) if total > 0 else 0,
        "last_24h": last_24h
    }


@app.get("/history")
async def decision_history():
    """Get last 100 decisions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT request_id, decision, reason, confidence, rule_matched, timestamp 
        FROM decisions 
        ORDER BY timestamp DESC 
        LIMIT 100
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    decisions = []
    for row in rows:
        decisions.append({
            'request_id': row[0],
            'decision': row[1],
            'reason': row[2],
            'confidence': row[3],
            'rule_matched': row[4],
            'timestamp': row[5]
        })
    
    return {"decisions": decisions}


# ============================================
# ✨ NOUVEAUX ENDPOINTS v1.6
# ============================================

@app.get("/review-dashboard", response_class=HTMLResponse)
async def review_dashboard():
    """Dashboard staff pour gérer NEEDS_REVIEW"""
    with open("static/review_dashboard.html", "r") as f:
        return f.read()


@app.get("/staff/reviews")
async def get_pending_reviews():
    """Get pending review requests"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT request_id, request_data, ai_reason, ai_confidence, created_at
        FROM pending_reviews
        WHERE status = 'pending'
        ORDER BY created_at DESC
        LIMIT 50
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    reviews = []
    for row in rows:
        reviews.append({
            'request_id': row[0],
            'request_data': json.loads(row[1]),
            'ai_reason': row[2],
            'ai_confidence': row[3],
            'created_at': row[4]
        })
    
    return JSONResponse(content={'reviews': reviews})


@app.post("/staff/review/approve/{request_id}")
async def approve_review(request_id: int, request: Request):
    """Staff approve a NEEDS_REVIEW request"""
    body = await request.json() if request.headers.get('content-type') == 'application/json' else {}
    staff_username = body.get('staff', 'admin')
    
    # Get request data
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_data, ai_decision FROM pending_reviews WHERE request_id = ?",
        (request_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(404, "Review not found")
    
    request_data = json.loads(row[0])
    ai_decision = row[1]
    
    # Record human feedback for ML
    moderator.record_human_decision(
        request_id=request_id,
        request_data=request_data,
        ai_decision=ai_decision,
        human_decision='APPROVED',
        human_reason=body.get('reason', 'Staff approved'),
        staff_username=staff_username
    )
    
    # Approve in Overseerr
    approve_overseerr_request(request_id)
    
    # Update status
    cursor.execute(
        "UPDATE pending_reviews SET status = 'approved' WHERE request_id = ?",
        (request_id,)
    )
    conn.commit()
    conn.close()
    
    # Save to decisions
    save_decision(request_id, 'APPROVED', 'Staff approved', 1.0, 'human_review')
    
    return {'status': 'approved', 'request_id': request_id}


@app.post("/staff/review/reject/{request_id}")
async def reject_review(request_id: int, request: Request):
    """Staff reject a NEEDS_REVIEW request"""
    body = await request.json()
    staff_username = body.get('staff', 'admin')
    reason = body.get('reason', 'Staff rejected')
    
    # Get request data
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_data, ai_decision FROM pending_reviews WHERE request_id = ?",
        (request_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(404, "Review not found")
    
    request_data = json.loads(row[0])
    ai_decision = row[1]
    
    # Record feedback
    moderator.record_human_decision(
        request_id=request_id,
        request_data=request_data,
        ai_decision=ai_decision,
        human_decision='REJECTED',
        human_reason=reason,
        staff_username=staff_username
    )
    
    # Reject in Overseerr
    decline_overseerr_request(request_id)
    
    # Update status
    cursor.execute(
        "UPDATE pending_reviews SET status = 'rejected' WHERE request_id = ?",
        (request_id,)
    )
    conn.commit()
    conn.close()
    
    # Save
    save_decision(request_id, 'REJECTED', reason, 1.0, 'human_review')
    
    return {'status': 'rejected', 'request_id': request_id}


@app.get("/staff/pending-count")
async def pending_count():
    """Count pending reviews"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pending_reviews WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return {'count': count}


@app.get("/staff/ml-stats")
async def ml_stats():
    """ML system statistics"""
    feedback_count = feedback_db.get_feedback_count(unlearned_only=False)
    unlearned = feedback_db.get_feedback_count(unlearned_only=True)
    
    return {
        'total_feedback': feedback_count,
        'unlearned': unlearned,
        'patterns_learned': feedback_count - unlearned,
        'learning_threshold': 100
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
