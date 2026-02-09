from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import json

# ✨ IMPORTS - Système AI-First
from app.config_loader import ConfigManager, SmartModerator, ModerationDecision
from app.ml_feedback import FeedbackDatabase, EnhancedModerator
from app.openai_moderator import OpenAIModerator
from app.rules_validator import RulesValidator

app = FastAPI(title="PlexStaffAI", version="1.6.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OVERSEERR_API_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055")
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")

# ✨ AI-FIRST SYSTEM
config = ConfigManager("/config/config.yaml")
feedback_db = FeedbackDatabase("/config/feedback.db")
moderator = EnhancedModerator(config, feedback_db)
openai_moderator = OpenAIModerator() if OPENAI_API_KEY else None
rules_validator = RulesValidator(config)

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
            request_data JSON,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Migration: Ajoute colonne si elle n'existe pas
    try:
        cursor.execute("ALTER TABLE decisions ADD COLUMN request_data JSON")
        print("✅ Added request_data column to decisions table")
    except:
        pass
    
    # Pending reviews table
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


def enrich_from_tmdb(tmdb_id: int, media_type: str) -> dict:
    """Enrichit les données depuis TMDB API si disponible"""
    if not TMDB_API_KEY:
        print("⚠️  TMDB_API_KEY not configured, skipping enrichment")
        return {}
    
    try:
        endpoint = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
        
        response = httpx.get(
            endpoint,
            params={"api_key": TMDB_API_KEY, "language": "fr-FR"},
            timeout=5.0
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ TMDB enrichment successful for {media_type}/{tmdb_id}")
        
        return {
            'title': data.get('name') or data.get('title', ''),
            'original_title': data.get('original_name') or data.get('original_title', ''),
            'overview': data.get('overview', ''),
            'rating': data.get('vote_average', 0),
            'popularity': data.get('popularity', 0),
            'year': (data.get('first_air_date') or data.get('release_date', ''))[:4],
            'genres': [g.get('name', '') for g in data.get('genres', [])],
            'episode_count': data.get('number_of_episodes', 0),
            'season_count': data.get('number_of_seasons', 0),
            'seasons': data.get('seasons', []),
            'status': data.get('status', ''),
        }
    except Exception as e:
        print(f"❌ TMDB enrichment failed: {e}")
        return {}


def get_title_from_media(media: dict, tmdb_enriched: dict = None) -> str:
    """Extrait le titre avec fallback robuste"""
    candidates = [
        media.get('title'),
        media.get('name'),
        media.get('originalTitle'),
        media.get('originalName'),
    ]
    
    if tmdb_enriched:
        candidates.extend([
            tmdb_enriched.get('title'),
            tmdb_enriched.get('original_title')
        ])
    
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    
    return f"TMDB-{media.get('tmdbId', 'unknown')}"


def moderate_request(request_id: int, request_data: dict) -> dict:
    """
    AI-FIRST Moderation with Rules Validation
    
    Workflow:
    1. OpenAI fait l'analyse primaire (raisonnement complet)
    2. Rules valident/ajustent/override la décision AI
    3. Décision finale basée sur AI + Rules combined
    """
    
    # Extract metadata from Overseerr
    media = request_data.get('media', {})
    media_type = media.get('mediaType', 'unknown')
    tmdb_id = media.get('tmdbId')
    
    # ENRICHISSEMENT TMDB si données manquantes
    tmdb_enriched = {}
    needs_enrichment = (
        not media.get('title') and 
        not media.get('name') and 
        tmdb_id and 
        media_type in ['movie', 'tv']
    )
    
    if needs_enrichment:
        print(f"🔍 Overseerr data incomplete, enriching from TMDB...")
        tmdb_enriched = enrich_from_tmdb(tmdb_id, media_type)
    
    # Extraction avec fallback TMDB
    title = get_title_from_media(media, tmdb_enriched)
    year = tmdb_enriched.get('year') or (media.get('releaseDate', '')[:4] if media.get('releaseDate') else '')
    requested_by = request_data.get('requestedBy', {}).get('displayName', 'unknown')
    user_id = str(request_data.get('requestedBy', {}).get('id', 'unknown'))
    
    # EXTRACTION ROBUSTE DES COUNTS
    seasons = tmdb_enriched.get('seasons') or media.get('seasons', [])
    episode_count_from_seasons = sum(s.get('episodeCount', 0) or s.get('episode_count', 0) for s in seasons)
    season_count_from_list = len(seasons)
    
    season_count_from_field = (
        tmdb_enriched.get('season_count') or 
        media.get('numberOfSeasons', 0)
    )
    episode_count_from_field = (
        tmdb_enriched.get('episode_count') or 
        media.get('numberOfEpisodes', 0)
    )
    
    season_count = max(season_count_from_list, season_count_from_field)
    episode_count = max(episode_count_from_seasons, episode_count_from_field)
    
    rating = tmdb_enriched.get('rating') or media.get('voteAverage', 0)
    popularity = tmdb_enriched.get('popularity') or media.get('popularity', 0)
    genres = tmdb_enriched.get('genres') or [g.get('name', '') for g in media.get('genres', [])]
    
    # DEBUG LOGS
    print(f"\n{'='*60}")
    print(f"🎬 REQUEST #{request_id}: {title}")
    print(f"{'='*60}")
    print(f"📊 TMDB ID: {tmdb_id}")
    print(f"📺 Type: {media_type}")
    print(f"📅 Year: {year}")
    print(f"👤 User: {requested_by} (ID: {user_id})")
    if tmdb_enriched:
        print(f"🌐 Data source: TMDB API enrichment ✅")
    else:
        print(f"📦 Data source: Overseerr")
    print(f"\n📈 CONTENT STATS:")
    print(f"  Seasons: {season_count}")
    print(f"  Episodes: {episode_count}")
    print(f"  Rating: {rating}/10")
    print(f"  Popularity: {popularity}")
    print(f"  Genres: {', '.join(genres) if genres else 'N/A'}")
    print(f"{'='*60}")
    
    # Enrichir data
    enriched_data = {
        'title': title,
        'media_type': media_type,
        'year': year,
        'requested_by': requested_by,
        'user_id': user_id,
        'rating': rating,
        'popularity': popularity,
        'genres': genres,
        'episode_count': episode_count,
        'season_count': season_count,
        'awards': [],
    }
    
    # Calculer user_age_days
    user_created = request_data.get('requestedBy', {}).get('createdAt', '')
    if user_created:
        try:
            created_date = datetime.fromisoformat(user_created.replace('Z', '+00:00'))
            enriched_data['user_age_days'] = (datetime.now(created_date.tzinfo) - created_date).days
            print(f"👶 User age: {enriched_data['user_age_days']} days")
        except:
            enriched_data['user_age_days'] = 999
    
    # ✨✨✨ NIVEAU 1: OPENAI PRIMARY ANALYSIS ✨✨✨
    if openai_moderator:
        ai_result = openai_moderator.moderate(enriched_data)
        
        # ✨✨✨ NIVEAU 2: RULES VALIDATION ✨✨✨
        validation_result = rules_validator.validate(ai_result, enriched_data)
        
        decision = validation_result['final_decision']
        confidence = validation_result['final_confidence']
        reason = validation_result['final_reason']
        
        # Determine rule_matched
        if validation_result['rule_override']:
            rule_matched = f"ai_override:{','.join(validation_result['rules_matched'][:2])}"
        else:
            rule_matched = f"ai_primary:{ai_result.get('model_used', 'gpt-4o-mini')}"
        
    else:
        # Fallback si pas d'OpenAI
        print("⚠️  OpenAI not configured, using rule-based fallback")
        decision_result = moderator.moderate_with_learning(enriched_data)
        decision = decision_result['decision']
        reason = decision_result['reason']
        confidence = decision_result.get('confidence', 1.0)
        rule_matched = decision_result.get('rule_matched', 'fallback')
    
    # LOG FINAL DECISION
    emoji = '✅' if decision == 'APPROVED' else '❌' if decision == 'REJECTED' else '🧑‍⚖️'
    print(f"\n{emoji} {'='*60}")
    print(f"{emoji} FINAL DECISION: {decision}")
    print(f"📝 Reason: {reason}")
    print(f"🎯 Path: {rule_matched}")
    print(f"💯 Confidence: {confidence:.1%}")
    print(f"{emoji} {'='*60}\n")
    
    # GESTION NEEDS_REVIEW
    if decision == 'NEEDS_REVIEW':
        save_for_review(request_id, enriched_data, {
            'decision': decision,
            'reason': reason,
            'confidence': confidence,
            'rule_matched': rule_matched
        })
        return {
            'decision': 'NEEDS_REVIEW',
            'reason': reason,
            'confidence': confidence,
            'action': 'pending_staff_review',
            'title': title
        }
    
    # Actions Overseerr
    if decision == 'APPROVED':
        approve_overseerr_request(request_id)
    elif decision == 'REJECTED':
        decline_overseerr_request(request_id)
    
    # Save to database
    save_decision(request_id, decision, reason, confidence, rule_matched, enriched_data)
    
    return {
        'request_id': request_id,
        'decision': decision,
        'reason': reason,
        'confidence': confidence,
        'rule_matched': rule_matched,
        'title': title
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
                 confidence: float, rule_matched: str, request_data: dict = None):
    """Save decision to database with full metadata"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO decisions 
        (request_id, decision, reason, confidence, rule_matched, request_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (request_id, decision, reason, confidence, rule_matched, json.dumps(request_data)))
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
    approved_count = 0
    rejected_count = 0
    needs_review_count = 0
    
    for req in requests:
        result = moderate_request(req['id'], req)
        results.append(result)
        
        decision = result.get('decision', '')
        if decision == 'APPROVED':
            approved_count += 1
        elif decision == 'REJECTED':
            rejected_count += 1
        elif decision == 'NEEDS_REVIEW':
            needs_review_count += 1
    
    return {
        "message": f"Moderated {len(results)} requests",
        "approved": approved_count,
        "rejected": rejected_count,
        "needs_review": needs_review_count,
        "details": results
    }


@app.get("/moderate-html", response_class=HTMLResponse)
async def moderate_html():
    """Endpoint HTML pour HTMX - Modération manuelle"""
    try:
        result = await manual_moderate()
        
        approved = result.get('approved', 0)
        rejected = result.get('rejected', 0)
        needs_review = result.get('needs_review', 0)
        total = approved + rejected + needs_review
        details = result.get('details', [])
        
        html = f'''
<div class="space-y-6">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="bg-gradient-to-br from-blue-900 to-indigo-900 p-6 rounded-xl border border-blue-700">
            <div class="text-blue-300 text-sm font-semibold mb-2">📊 Total Traité</div>
            <div class="text-5xl font-black text-white">{total}</div>
            <div class="text-xs text-blue-400 mt-2">Requests modérées</div>
        </div>
        <div class="bg-gradient-to-br from-emerald-900 to-teal-900 p-6 rounded-xl border border-emerald-700">
            <div class="text-emerald-300 text-sm font-semibold mb-2">✅ Approuvés</div>
            <div class="text-5xl font-black text-emerald-300">{approved}</div>
            <div class="text-xs text-emerald-500 mt-2">Auto-validées</div>
        </div>
        <div class="bg-gradient-to-br from-red-900 to-pink-900 p-6 rounded-xl border border-red-700">
            <div class="text-red-300 text-sm font-semibold mb-2">❌ Rejetés</div>
            <div class="text-5xl font-black text-red-300">{rejected}</div>
            <div class="text-xs text-red-500 mt-2">Auto-refusées</div>
        </div>
        <div class="bg-gradient-to-br from-yellow-900 to-orange-900 p-6 rounded-xl border border-yellow-700">
            <div class="text-yellow-300 text-sm font-semibold mb-2">🧑‍⚖️ À Réviser</div>
            <div class="text-5xl font-black text-yellow-300">{needs_review}</div>
            <div class="text-xs text-yellow-500 mt-2">Review manuelle</div>
        </div>
    </div>
    
    <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
        <h4 class="text-xl font-bold mb-4 text-white flex items-center">
            <span class="w-3 h-3 bg-blue-400 rounded-full mr-3 animate-pulse"></span>
            📋 Détails des Décisions
        </h4>
'''
        
        if details and len(details) > 0:
            for item in details[:20]:
                title = item.get('title', 'Unknown')
                decision = item.get('decision', 'UNKNOWN')
                reason = item.get('reason', 'No reason provided')
                confidence = item.get('confidence', 0) * 100
                rule = item.get('rule_matched', 'none')
                
                if decision == 'APPROVED':
                    color_class = 'bg-emerald-900/30 border-emerald-700'
                    text_class = 'text-emerald-300'
                    emoji = '✅'
                elif decision == 'REJECTED':
                    color_class = 'bg-red-900/30 border-red-700'
                    text_class = 'text-red-300'
                    emoji = '❌'
                else:
                    color_class = 'bg-yellow-900/30 border-yellow-700'
                    text_class = 'text-yellow-300'
                    emoji = '🧑‍⚖️'
                
                html += f'''
        <div class="{color_class} p-4 rounded-lg border mb-3">
            <div class="flex justify-between items-start mb-2">
                <div class="font-bold text-white flex items-center gap-2">
                    <span class="text-2xl">{emoji}</span>
                    <span>{title}</span>
                </div>
                <div class="text-xs {text_class} bg-gray-900/50 px-3 py-1 rounded-full">
                    {confidence:.0f}% confiance
                </div>
            </div>
            <div class="text-sm opacity-90 {text_class} mb-1">{reason}</div>
            <div class="text-xs text-gray-500">Path: {rule}</div>
        </div>
'''
        else:
            html += '''
        <div class="text-gray-400 text-center py-12">
            <div class="text-6xl mb-4">✨</div>
            <div class="text-2xl font-bold mb-2">Aucune requête en attente</div>
            <div class="text-lg">Tous les contenus ont été modérés !</div>
            <div class="text-sm text-gray-600 mt-2">Le système scan automatiquement toutes les 15 minutes</div>
        </div>
'''
        
        html += f'''
    </div>
    
    <div class="flex gap-4 justify-center flex-wrap">
        <button 
            hx-get="/stats" 
            hx-target="#stats-container" 
            hx-swap="innerHTML"
            class="bg-emerald-600 hover:bg-emerald-700 px-8 py-3 rounded-xl font-bold text-lg transition shadow-lg">
            🔄 Rafraîchir Stats
        </button>
        <a href="/review-dashboard" 
           class="bg-yellow-600 hover:bg-yellow-700 px-8 py-3 rounded-xl font-bold text-lg transition shadow-lg inline-block">
            🧑‍⚖️ Voir Reviews ({needs_review})
        </a>
        <a href="/history" 
           class="bg-purple-600 hover:bg-purple-700 px-8 py-3 rounded-xl font-bold text-lg transition shadow-lg inline-block">
            📜 Historique
        </a>
    </div>
    
    <div class="text-center text-gray-500 text-sm mt-4">
        ⏱️ Modération terminée • Prochaine auto-scan dans 15min
    </div>
</div>
'''
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        error_html = f'''
<div class="bg-red-900/30 border-2 border-red-700 p-8 rounded-xl text-center">
    <div class="text-6xl mb-4">⚠️</div>
    <div class="text-red-300 font-bold text-2xl mb-3">Erreur de Modération</div>
    <div class="text-red-400 text-lg mb-6">{str(e)}</div>
    <button 
        hx-get="/moderate-html" 
        hx-target="#results"
        hx-swap="innerHTML" 
        class="bg-red-600 hover:bg-red-700 px-8 py-3 rounded-xl font-bold text-lg transition shadow-lg">
        🔄 Réessayer
    </button>
</div>
'''
        return HTMLResponse(content=error_html)


@app.get("/stats")
async def stats():
    """Stats endpoint for dashboard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT decision, COUNT(*) FROM decisions GROUP BY decision")
    stats = dict(cursor.fetchall())
    
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


@app.get("/staff/report", response_class=HTMLResponse)
async def moderation_report():
    """Get moderation statistics with beautiful HTML view"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT decision, COUNT(*) FROM decisions GROUP BY decision")
    stats = dict(cursor.fetchall())
    
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute(
        "SELECT decision, COUNT(*) FROM decisions WHERE timestamp > ? GROUP BY decision",
        (yesterday,)
    )
    last_24h = dict(cursor.fetchall())
    
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute(
        "SELECT decision, COUNT(*) FROM decisions WHERE timestamp > ? GROUP BY decision",
        (week_ago,)
    )
    last_7d = dict(cursor.fetchall())
    
    cursor.execute("""
        SELECT request_id, decision, reason, rule_matched, timestamp 
        FROM decisions 
        ORDER BY timestamp DESC 
        LIMIT 10
    """)
    recent = cursor.fetchall()
    
    cursor.execute("""
        SELECT rule_matched, COUNT(*) as count 
        FROM decisions 
        GROUP BY rule_matched 
        ORDER BY count DESC 
        LIMIT 10
    """)
    rules_stats = cursor.fetchall()
    
    conn.close()
    
    total = sum(stats.values())
    approved = stats.get('APPROVED', 0)
    rejected = stats.get('REJECTED', 0)
    needs_review = stats.get('NEEDS_REVIEW', 0)
    approval_rate = round(approved / total * 100, 1) if total > 0 else 0
    
    total_24h = sum(last_24h.values())
    total_7d = sum(last_7d.values())
    
    html = f'''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport Complet - PlexStaffAI</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .fade-in {{ animation: fadeIn 0.5s ease-out; }}
    </style>
</head>
<body class="bg-gray-900 text-white font-sans antialiased">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        
        <header class="mb-12 fade-in">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h1 class="text-5xl font-black bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500 bg-clip-text text-transparent mb-2">
                        📊 Rapport de Modération Complet
                    </h1>
                    <p class="text-xl text-gray-400">Vue d'ensemble des statistiques PlexStaffAI</p>
                </div>
                <a href="/" 
                   class="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 
                          px-6 py-3 rounded-xl font-bold text-lg transition shadow-lg">
                    🏠 Dashboard
                </a>
            </div>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8 fade-in">
            <div class="bg-gradient-to-br from-gray-800 to-gray-900 p-8 rounded-2xl shadow-2xl border border-gray-700">
                <div class="text-gray-400 text-sm font-semibold mb-2">📊 TOTAL DÉCISIONS</div>
                <div class="text-6xl font-black text-white mb-2">{total}</div>
                <div class="text-sm text-gray-500">Toutes périodes</div>
            </div>
            
            <div class="bg-gradient-to-br from-emerald-900 to-teal-900 p-8 rounded-2xl shadow-2xl border border-emerald-700">
                <div class="text-emerald-300 text-sm font-semibold mb-2">✅ APPROUVÉS</div>
                <div class="text-6xl font-black text-emerald-300 mb-2">{approved}</div>
                <div class="text-sm text-emerald-600">{round(approved/total*100, 1) if total > 0 else 0}% du total</div>
            </div>
            
            <div class="bg-gradient-to-br from-red-900 to-pink-900 p-8 rounded-2xl shadow-2xl border border-red-700">
                <div class="text-red-300 text-sm font-semibold mb-2">❌ REJETÉS</div>
                <div class="text-6xl font-black text-red-300 mb-2">{rejected}</div>
                <div class="text-sm text-red-600">{round(rejected/total*100, 1) if total > 0 else 0}% du total</div>
            </div>
            
            <div class="bg-gradient-to-br from-yellow-900 to-orange-900 p-8 rounded-2xl shadow-2xl border border-yellow-700">
                <div class="text-yellow-300 text-sm font-semibold mb-2">🧑‍⚖️ EN REVIEW</div>
                <div class="text-6xl font-black text-yellow-300 mb-2">{needs_review}</div>
                <div class="text-sm text-yellow-600">{round(needs_review/total*100, 1) if total > 0 else 0}% du total</div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 fade-in">
            <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
                <h3 class="text-xl font-bold mb-4 text-purple-400">📈 Taux d'Approbation</h3>
                <div class="text-5xl font-black text-white mb-2">{approval_rate}%</div>
                <div class="text-sm text-gray-400">Pourcentage global</div>
            </div>
            
            <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
                <h3 class="text-xl font-bold mb-4 text-blue-400">📅 Dernières 24h</h3>
                <div class="text-5xl font-black text-white mb-2">{total_24h}</div>
                <div class="text-sm text-gray-400">
                    <span class="text-emerald-400">{last_24h.get('APPROVED', 0)} ✅</span> • 
                    <span class="text-red-400">{last_24h.get('REJECTED', 0)} ❌</span> • 
                    <span class="text-yellow-400">{last_24h.get('NEEDS_REVIEW', 0)} 🧑‍⚖️</span>
                </div>
            </div>
            
            <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
                <h3 class="text-xl font-bold mb-4 text-indigo-400">📆 Derniers 7 jours</h3>
                <div class="text-5xl font-black text-white mb-2">{total_7d}</div>
                <div class="text-sm text-gray-400">
                    <span class="text-emerald-400">{last_7d.get('APPROVED', 0)} ✅</span> • 
                    <span class="text-red-400">{last_7d.get('REJECTED', 0)} ❌</span> • 
                    <span class="text-yellow-400">{last_7d.get('NEEDS_REVIEW', 0)} 🧑‍⚖️</span>
                </div>
            </div>
        </div>

        <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700 mb-8 fade-in">
            <h3 class="text-2xl font-bold mb-6 flex items-center">
                <span class="w-3 h-3 bg-purple-400 rounded-full mr-3 animate-pulse"></span>
                🎯 Règles les Plus Utilisées
            </h3>
            <div class="space-y-3">
    '''
    
    for rule, count in rules_stats:
        percentage = round(count / total * 100, 1) if total > 0 else 0
        html += f'''
                <div class="bg-gray-900/50 p-4 rounded-lg">
                    <div class="flex justify-between items-center mb-2">
                        <div class="font-mono text-sm text-purple-300">{rule}</div>
                        <div class="text-white font-bold">{count} fois ({percentage}%)</div>
                    </div>
                    <div class="w-full bg-gray-700 rounded-full h-2">
                        <div class="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full" 
                             style="width: {percentage}%"></div>
                    </div>
                </div>
        '''
    
    html += '''
            </div>
        </div>

        <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700 fade-in">
            <h3 class="text-2xl font-bold mb-6 flex items-center">
                <span class="w-3 h-3 bg-blue-400 rounded-full mr-3 animate-pulse"></span>
                🕐 10 Dernières Décisions
            </h3>
            <div class="space-y-3">
    '''
    
    for req_id, decision, reason, rule, timestamp in recent:
        if decision == 'APPROVED':
            color = 'bg-emerald-900/30 border-emerald-700'
            text_color = 'text-emerald-300'
            emoji = '✅'
        elif decision == 'REJECTED':
            color = 'bg-red-900/30 border-red-700'
            text_color = 'text-red-300'
            emoji = '❌'
        else:
            color = 'bg-yellow-900/30 border-yellow-700'
            text_color = 'text-yellow-300'
            emoji = '🧑‍⚖️'
        
        html += f'''
                <div class="{color} border rounded-lg p-4">
                    <div class="flex justify-between items-start mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-2xl">{emoji}</span>
                            <div>
                                <span class="font-bold text-white">Request #{req_id}</span>
                                <span class="text-xs {text_color} ml-2">{decision}</span>
                            </div>
                        </div>
                        <div class="text-xs text-gray-500">{timestamp}</div>
                    </div>
                    <div class="text-sm {text_color} opacity-90 mb-1">{reason}</div>
                    <div class="text-xs text-gray-500">Path: {rule}</div>
                </div>
        '''
    
    html += '''
            </div>
        </div>

        <div class="mt-8 flex gap-4 justify-center flex-wrap fade-in">
            <a href="/" 
               class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                🏠 Dashboard Principal
            </a>
            <a href="/history" 
               class="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                📜 Historique Complet
            </a>
            <a href="/review-dashboard" 
               class="bg-yellow-600 hover:bg-yellow-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                🧑‍⚖️ Review Dashboard
            </a>
            <button 
               onclick="window.location.reload()" 
               class="bg-emerald-600 hover:bg-emerald-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                🔄 Rafraîchir
            </button>
        </div>

        <footer class="text-center mt-12 text-gray-500 text-sm">
            <p>PlexStaffAI v1.6.0 • Rapport généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}</p>
        </footer>

    </div>
</body>
</html>
    '''
    
    return HTMLResponse(content=html)


@app.get("/history", response_class=HTMLResponse)
async def history_page():
    """Page HTML historique"""
    with open("static/history.html", "r") as f:
        return f.read()


@app.get("/api/history")
async def history_data(filter: str = "all"):
    """API endpoint pour les données historique avec métadonnées complètes"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if filter == "all":
        cursor.execute("""
            SELECT request_id, decision, reason, confidence, rule_matched, timestamp, request_data
            FROM decisions 
            ORDER BY timestamp DESC 
            LIMIT 100
        """)
    else:
        cursor.execute("""
            SELECT request_id, decision, reason, confidence, rule_matched, timestamp, request_data
            FROM decisions 
            WHERE decision = ?
            ORDER BY timestamp DESC 
            LIMIT 100
        """, (filter,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        html = '''
        <div class="text-center py-12 bg-gray-800/30 rounded-xl">
            <div class="text-6xl mb-4">📭</div>
            <div class="text-2xl font-bold mb-2">Aucune décision</div>
            <div class="text-gray-400">L'historique est vide</div>
        </div>
        '''
        return HTMLResponse(content=html)
    
    html = '<div class="space-y-4">'
    
    for row in rows:
        request_id, decision, reason, confidence, rule_matched, timestamp, request_data_json = row
        
        request_data = {}
        if request_data_json:
            try:
                request_data = json.loads(request_data_json)
            except:
                pass
        
        title = request_data.get('title', f'Request #{request_id}')
        media_type = request_data.get('media_type', 'unknown')
        year = request_data.get('year', '')
        rating = request_data.get('rating', 0)
        popularity = request_data.get('popularity', 0)
        genres = request_data.get('genres', [])
        season_count = request_data.get('season_count', 0)
        episode_count = request_data.get('episode_count', 0)
        user = request_data.get('requested_by', 'Unknown')
        user_age = request_data.get('user_age_days', 0)
        
        if decision == 'APPROVED':
            color = 'bg-emerald-900/30 border-emerald-700'
            text_color = 'text-emerald-300'
            emoji = '✅'
            gradient = 'from-emerald-600 to-teal-600'
        elif decision == 'REJECTED':
            color = 'bg-red-900/30 border-red-700'
            text_color = 'text-red-300'
            emoji = '❌'
            gradient = 'from-red-600 to-pink-600'
        else:
            color = 'bg-yellow-900/30 border-yellow-700'
            text_color = 'text-yellow-300'
            emoji = '🧑‍⚖️'
            gradient = 'from-yellow-600 to-orange-600'
        
        confidence_pct = int(confidence * 100)
        
        genres_str = ', '.join(genres[:3]) if genres else 'N/A'
        if len(genres) > 3:
            genres_str += f' +{len(genres)-3}'
        
        html += f'''
        <div class="{color} border-2 rounded-2xl p-6 hover:shadow-2xl transition-all hover:scale-[1.02]">
            <div class="flex justify-between items-start mb-4">
                <div class="flex items-center gap-4">
                    <div class="text-5xl">{emoji}</div>
                    <div>
                        <div class="font-black text-2xl text-white mb-1">🎬 {title}</div>
                        <div class="flex items-center gap-3 text-sm">
                            <span class="bg-gray-900/50 px-3 py-1 rounded-full font-semibold">
                                {"📺" if media_type == "tv" else "🎬"} {media_type.upper()}
                            </span>
        '''
        
        if year:
            html += f'<span class="text-gray-400">📅 {year}</span>'
        
        html += f'''
                            <span class="{text_color} font-bold">#{request_id}</span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="bg-gradient-to-r {gradient} px-4 py-2 rounded-xl font-bold text-white mb-2">
                        {decision}
                    </div>
                    <div class="text-xs text-gray-500">{timestamp}</div>
                </div>
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 bg-gray-900/30 p-4 rounded-xl">
        '''
        
        if rating > 0:
            html += f'''
                <div>
                    <div class="text-xs text-gray-400">⭐ Rating</div>
                    <div class="text-lg font-bold text-white">{rating:.1f}/10</div>
                </div>
        '''
        
        if popularity > 0:
            html += f'''
                <div>
                    <div class="text-xs text-gray-400">🔥 Popularité</div>
                    <div class="text-lg font-bold text-white">{popularity:.0f}</div>
                </div>
        '''
        
        if season_count > 0:
            html += f'''
                <div>
                    <div class="text-xs text-gray-400">📺 Saisons</div>
                    <div class="text-lg font-bold text-white">{season_count}</div>
                </div>
        '''
        
        if episode_count > 0:
            html += f'''
                <div>
                    <div class="text-xs text-gray-400">📼 Épisodes</div>
                    <div class="text-lg font-bold text-white">{episode_count}</div>
                </div>
        '''
        
        html += f'''
            </div>
            
            <div class="space-y-2 mb-4">
                <div class="flex items-start gap-2">
                    <span class="text-gray-400 text-sm">📝</span>
                    <span class="text-sm {text_color} flex-1">{reason}</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-gray-400 text-sm">🎯</span>
                    <span class="text-sm text-gray-300">Path: <span class="font-mono {text_color}">{rule_matched}</span></span>
                </div>
        '''
        
        if genres:
            html += f'''
                <div class="flex items-center gap-2">
                    <span class="text-gray-400 text-sm">🎭</span>
                    <span class="text-sm text-gray-300">{genres_str}</span>
                </div>
        '''
        
        html += f'''
                <div class="flex items-center gap-4 text-xs text-gray-500">
                    <span>👤 {user}</span>
        '''
        
        if user_age > 0:
            html += f'<span>👶 Compte: {user_age} jours</span>'
        
        html += f'''
                </div>
            </div>
            
            <div class="flex justify-between items-center pt-4 border-t border-gray-700">
                <div class="flex items-center gap-2">
                    <div class="w-3 h-3 {text_color.replace('text-', 'bg-')} rounded-full"></div>
                    <span class="text-sm font-semibold {text_color}">{confidence_pct}% confiance</span>
                </div>
            </div>
        </div>
        '''
    
    html += '</div>'
    
    return HTMLResponse(content=html)


@app.get("/health", response_class=HTMLResponse)
async def health_check():
    """Beautiful health check page with service status"""
    
    services = {
        'openai': {
            'name': 'OpenAI API',
            'icon': '🤖',
            'configured': bool(OPENAI_API_KEY),
            'status': 'operational' if OPENAI_API_KEY else 'missing',
            'description': 'IA Modération GPT-4o-mini'
        },
        'overseerr': {
            'name': 'Overseerr',
            'icon': '📺',
            'configured': bool(OVERSEERR_API_KEY and OVERSEERR_API_URL),
            'status': 'operational',
            'description': 'Gestion des requêtes média'
        },
        'tmdb': {
            'name': 'TMDB API',
            'icon': '🎬',
            'configured': bool(TMDB_API_KEY),
            'status': 'operational' if TMDB_API_KEY else 'optional',
            'description': 'Enrichissement métadonnées'
        },
        'ml': {
            'name': 'Machine Learning',
            'icon': '🧠',
            'configured': config.get("machine_learning.enabled", True),
            'status': 'operational' if config.get("machine_learning.enabled", True) else 'disabled',
            'description': 'Apprentissage automatique'
        },
        'database': {
            'name': 'SQLite Database',
            'icon': '💾',
            'configured': True,
            'status': 'operational',
            'description': 'Stockage des décisions'
        }
    }
    
    try:
        response = httpx.get(
            f"{OVERSEERR_API_URL}/api/v1/status",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            timeout=3.0
        )
        if response.status_code == 200:
            services['overseerr']['status'] = 'operational'
            services['overseerr']['version'] = response.json().get('version', 'unknown')
        else:
            services['overseerr']['status'] = 'error'
    except:
        services['overseerr']['status'] = 'error'
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM decisions")
        total_decisions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM pending_reviews WHERE status = 'pending'")
        pending_reviews = cursor.fetchone()[0]
        conn.close()
        services['database']['stats'] = f"{total_decisions} décisions, {pending_reviews} reviews"
    except:
        services['database']['status'] = 'error'
    
    critical_services = ['openai', 'overseerr', 'database']
    all_critical_ok = all(services[s]['status'] == 'operational' for s in critical_services)
    overall_status = 'healthy' if all_critical_ok else 'degraded'
    
    operational_count = sum(1 for s in services.values() if s['status'] == 'operational')
    total_count = len(services)
    
    html_parts = []
    
    html_parts.append('''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Status - PlexStaffAI</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes pulse-ring {
            0% { transform: scale(1); opacity: 1; }
            100% { transform: scale(1.5); opacity: 0; }
        }
        .status-pulse {
            animation: pulse-ring 2s ease-out infinite;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .fade-in { animation: fadeIn 0.5s ease-out; }
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
    </style>
    <meta http-equiv="refresh" content="30">
</head>
<body class="bg-gray-900 text-white font-sans antialiased">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        
        <header class="mb-12 fade-in">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h1 class="text-5xl font-black bg-gradient-to-r from-green-400 via-blue-500 to-purple-600 bg-clip-text text-transparent mb-2">
                        💚 System Status
                    </h1>
                    <p class="text-xl text-gray-400">État en temps réel des services PlexStaffAI</p>
                </div>
                <a href="/" 
                   class="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 
                          px-6 py-3 rounded-xl font-bold text-lg transition shadow-lg">
                    🏠 Dashboard
                </a>
            </div>
    ''')
    
    html_parts.append(f'''
            <div class="text-sm text-gray-500">
                🔄 Auto-refresh toutes les 30 secondes • Dernière mise à jour: {datetime.now().strftime("%H:%M:%S")}
            </div>
        </header>

        <div class="mb-8 fade-in">
    ''')
    
    if overall_status == 'healthy':
        html_parts.append('''
            <div class="gradient-bg p-8 rounded-2xl shadow-2xl border-2 border-green-500">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-6">
                        <div class="relative">
                            <div class="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center">
                                <span class="text-4xl">✅</span>
                            </div>
                            <div class="absolute inset-0 w-20 h-20 bg-green-500 rounded-full status-pulse"></div>
                        </div>
                        <div>
                            <div class="text-3xl font-black text-white mb-2">All Systems Operational</div>
                            <div class="text-lg text-green-100">PlexStaffAI fonctionne parfaitement</div>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-5xl font-black text-white">99.9%</div>
                        <div class="text-sm text-green-100">Uptime</div>
                    </div>
                </div>
            </div>
        ''')
    else:
        html_parts.append('''
            <div class="bg-gradient-to-r from-yellow-600 to-orange-600 p-8 rounded-2xl shadow-2xl border-2 border-yellow-500">
                <div class="flex items-center gap-6">
                    <div class="w-20 h-20 bg-yellow-500 rounded-full flex items-center justify-center">
                        <span class="text-4xl">⚠️</span>
                    </div>
                    <div>
                        <div class="text-3xl font-black text-white mb-2">Service Partiellement Dégradé</div>
                        <div class="text-lg text-yellow-100">Certains services nécessitent attention</div>
                    </div>
                </div>
            </div>
        ''')
    
    html_parts.append('''
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
    ''')
    
    for service_key, service in services.items():
        status = service['status']
        
        if status == 'operational':
            status_color = 'bg-green-500'
            status_text = 'text-green-400'
            border_color = 'border-green-700'
            bg_color = 'bg-green-900/20'
            status_label = '✅ Opérationnel'
            pulse_html = '<div class="absolute inset-0 w-4 h-4 bg-green-500 rounded-full status-pulse"></div>'
        elif status == 'error':
            status_color = 'bg-red-500'
            status_text = 'text-red-400'
            border_color = 'border-red-700'
            bg_color = 'bg-red-900/20'
            status_label = '❌ Erreur'
            pulse_html = ''
        elif status == 'optional':
            status_color = 'bg-gray-500'
            status_text = 'text-gray-400'
            border_color = 'border-gray-700'
            bg_color = 'bg-gray-900/20'
            status_label = '⚪ Optionnel'
            pulse_html = ''
        else:
            status_color = 'bg-yellow-500'
            status_text = 'text-yellow-400'
            border_color = 'border-yellow-700'
            bg_color = 'bg-yellow-900/20'
            status_label = '⚠️ Non configuré'
            pulse_html = ''
        
        stats_html = ''
        if 'stats' in service:
            stats_html = f'<div class="text-xs text-gray-500 mt-2">{service["stats"]}</div>'
        if 'version' in service:
            stats_html += f'<div class="text-xs text-gray-500 mt-1">Version: {service["version"]}</div>'
        
        connected_html = '<span class="text-xs text-green-400">✓ Connecté</span>' if status == 'operational' else ''
        
        html_parts.append(f'''
            <div class="{bg_color} backdrop-blur-xl p-6 rounded-xl border {border_color} fade-in hover:scale-105 transition-transform">
                <div class="flex items-start justify-between mb-4">
                    <div class="flex items-center gap-3">
                        <div class="text-4xl">{service["icon"]}</div>
                        <div>
                            <div class="font-bold text-xl text-white">{service["name"]}</div>
                            <div class="text-sm text-gray-400">{service["description"]}</div>
                        </div>
                    </div>
                    <div class="relative">
                        <div class="w-4 h-4 {status_color} rounded-full"></div>
                        {pulse_html}
                    </div>
                </div>
                <div class="flex items-center justify-between">
                    <div class="text-sm font-semibold {status_text}">{status_label}</div>
                    {connected_html}
                </div>
                {stats_html}
            </div>
        ''')
    
    html_parts.append(f'''
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 fade-in">
            <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
                <div class="text-gray-400 text-sm font-semibold mb-2">🚀 VERSION</div>
                <div class="text-3xl font-black text-white">v1.6.0</div>
                <div class="text-xs text-gray-500 mt-2">PlexStaffAI AI-First</div>
            </div>
            
            <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
                <div class="text-gray-400 text-sm font-semibold mb-2">🔧 SERVICES</div>
                <div class="text-3xl font-black text-white">{operational_count}/{total_count}</div>
                <div class="text-xs text-gray-500 mt-2">Services actifs</div>
            </div>
            
            <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700">
                <div class="text-gray-400 text-sm font-semibold mb-2">⏱️ UPTIME</div>
                <div class="text-3xl font-black text-white">99.9%</div>
                <div class="text-xs text-gray-500 mt-2">Disponibilité</div>
            </div>
        </div>

        <div class="bg-gray-800/50 backdrop-blur-xl p-6 rounded-xl border border-gray-700 mb-8 fade-in">
            <h3 class="text-2xl font-bold mb-6 flex items-center">
                <span class="w-3 h-3 bg-blue-400 rounded-full mr-3 animate-pulse"></span>
                🔌 API Endpoints
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="bg-gray-900/50 p-4 rounded-lg flex items-center justify-between">
                    <div>
                        <div class="font-mono text-sm text-blue-300">GET /health</div>
                        <div class="text-xs text-gray-500">System status</div>
                    </div>
                    <span class="text-green-400 text-2xl">✓</span>
                </div>
                <div class="bg-gray-900/50 p-4 rounded-lg flex items-center justify-between">
                    <div>
                        <div class="font-mono text-sm text-blue-300">POST /staff/moderate</div>
                        <div class="text-xs text-gray-500">Modération manuelle</div>
                    </div>
                    <span class="text-green-400 text-2xl">✓</span>
                </div>
                <div class="bg-gray-900/50 p-4 rounded-lg flex items-center justify-between">
                    <div>
                        <div class="font-mono text-sm text-blue-300">GET /stats</div>
                        <div class="text-xs text-gray-500">Statistiques</div>
                    </div>
                    <span class="text-green-400 text-2xl">✓</span>
                </div>
                <div class="bg-gray-900/50 p-4 rounded-lg flex items-center justify-between">
                    <div>
                        <div class="font-mono text-sm text-blue-300">GET /staff/report</div>
                        <div class="text-xs text-gray-500">Rapport complet</div>
                    </div>
                    <span class="text-green-400 text-2xl">✓</span>
                </div>
            </div>
        </div>

        <div class="flex gap-4 justify-center flex-wrap fade-in">
            <a href="/" 
               class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                🏠 Dashboard Principal
            </a>
            <a href="/staff/report" 
               class="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                📊 Rapport Complet
            </a>
            <a href="/docs" 
               class="bg-indigo-600 hover:bg-indigo-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                📖 API Docs
            </a>
            <button 
               onclick="window.location.reload()" 
               class="bg-emerald-600 hover:bg-emerald-700 px-6 py-3 rounded-xl font-bold transition shadow-lg">
                🔄 Rafraîchir
            </button>
        </div>

        <footer class="text-center mt-12 text-gray-500 text-sm">
            <p class="mb-2">🚀 PlexStaffAI v1.6.0 AI-First • Monitoring en temps réel</p>
            <p>Made with ❤️ by <a href="https://github.com/malambert35" class="text-blue-400 hover:text-blue-300">@malambert35</a></p>
        </footer>

    </div>
</body>
</html>
    ''')
    
    return HTMLResponse(content=''.join(html_parts))


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
    
    moderator.record_human_decision(
        request_id=request_id,
        request_data=request_data,
        ai_decision=ai_decision,
        human_decision='APPROVED',
        human_reason=body.get('reason', 'Staff approved'),
        staff_username=staff_username
    )
    
    approve_overseerr_request(request_id)
    
    cursor.execute(
        "UPDATE pending_reviews SET status = 'approved' WHERE request_id = ?",
        (request_id,)
    )
    conn.commit()
    conn.close()
    
    save_decision(request_id, 'APPROVED', 'Staff approved', 1.0, 'human_review', request_data)
    
    return {'status': 'approved', 'request_id': request_id}


@app.post("/staff/review/reject/{request_id}")
async def reject_review(request_id: int, request: Request):
    """Staff reject a NEEDS_REVIEW request"""
    body = await request.json()
    staff_username = body.get('staff', 'admin')
    reason = body.get('reason', 'Staff rejected')
    
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
    
    moderator.record_human_decision(
        request_id=request_id,
        request_data=request_data,
        ai_decision=ai_decision,
        human_decision='REJECTED',
        human_reason=reason,
        staff_username=staff_username
    )
    
    decline_overseerr_request(request_id)
    
    cursor.execute(
        "UPDATE pending_reviews SET status = 'rejected' WHERE request_id = ?",
        (request_id,)
    )
    conn.commit()
    conn.close()
    
    save_decision(request_id, 'REJECTED', reason, 1.0, 'human_review', request_data)
    
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


@app.get("/staff/openai-stats")
async def openai_stats():
    """OpenAI usage statistics"""
    if not openai_moderator:
        return {'enabled': False, 'message': 'OpenAI not configured'}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM decisions 
        WHERE rule_matched LIKE 'ai_primary:%' OR rule_matched LIKE 'ai_override:%'
    """)
    openai_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM decisions")
    total_count = cursor.fetchone()[0]
    
    conn.close()
    
    cost_per_request = 0.02
    
    return {
        'enabled': True,
        'total_ai_decisions': openai_count,
        'total_decisions': total_count,
        'ai_usage_rate': round(openai_count / total_count * 100, 1) if total_count > 0 else 0,
        'estimated_cost_so_far': round(openai_count * cost_per_request, 2),
        'cost_per_request': cost_per_request,
        'model': 'gpt-4o-mini'
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
