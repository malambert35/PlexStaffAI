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
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")  # ✨ NOUVEAU: Enrichissement TMDB

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
        "tmdb": "configured" if TMDB_API_KEY else "missing",
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


# ✨ NOUVEAU: Enrichissement TMDB
def enrich_from_tmdb(tmdb_id: int, media_type: str) -> dict:
    """Enrichit les données depuis TMDB API si disponible"""
    if not TMDB_API_KEY:
        print("⚠️  TMDB_API_KEY not configured, skipping enrichment")
        return {}
    
    try:
        # Endpoint TMDB selon type
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
    
    # Ajoute les données TMDB si disponibles
    if tmdb_enriched:
        candidates.extend([
            tmdb_enriched.get('title'),
            tmdb_enriched.get('original_title')
        ])
    
    # Retourne le premier non-vide
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    
    # Fallback TMDB ID
    return f"TMDB-{media.get('tmdbId', 'unknown')}"


def moderate_request(request_id: int, request_data: dict) -> dict:
    """Moderate request with smart rules + ML"""
    
    # Extract metadata from Overseerr
    media = request_data.get('media', {})
    media_type = media.get('mediaType', 'unknown')
    tmdb_id = media.get('tmdbId')
    
    # ✨ ENRICHISSEMENT TMDB si données manquantes
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
    
    # ✨ EXTRACTION ROBUSTE DES COUNTS avec données TMDB
    # Méthode 1: Depuis seasons[] (liste détaillée)
    seasons = tmdb_enriched.get('seasons') or media.get('seasons', [])
    episode_count_from_seasons = sum(s.get('episodeCount', 0) or s.get('episode_count', 0) for s in seasons)
    season_count_from_list = len(seasons)
    
    # Méthode 2: Depuis numberOfSeasons/numberOfEpisodes
    season_count_from_field = (
        tmdb_enriched.get('season_count') or 
        media.get('numberOfSeasons', 0)
    )
    episode_count_from_field = (
        tmdb_enriched.get('episode_count') or 
        media.get('numberOfEpisodes', 0)
    )
    
    # Utilise la valeur la plus élevée (la plus fiable)
    season_count = max(season_count_from_list, season_count_from_field)
    episode_count = max(episode_count_from_seasons, episode_count_from_field)
    
    # Rating et popularity avec fallback TMDB
    rating = tmdb_enriched.get('rating') or media.get('voteAverage', 0)
    popularity = tmdb_enriched.get('popularity') or media.get('popularity', 0)
    genres = tmdb_enriched.get('genres') or [g.get('name', '') for g in media.get('genres', [])]
    
    # ✨ DEBUG LOGS
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
    print(f"  Seasons: {season_count} (list={season_count_from_list}, field={season_count_from_field})")
    print(f"  Episodes: {episode_count} (list={episode_count_from_seasons}, field={episode_count_from_field})")
    print(f"  Rating: {rating}/10")
    print(f"  Popularity: {popularity}")
    print(f"  Genres: {', '.join(genres) if genres else 'N/A'}")
    print(f"{'='*60}")
    
    # ✨ Enrichir data pour modération intelligente
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
    
    # Calculer user_age_days depuis Overseerr
    user_created = request_data.get('requestedBy', {}).get('createdAt', '')
    if user_created:
        try:
            created_date = datetime.fromisoformat(user_created.replace('Z', '+00:00'))
            enriched_data['user_age_days'] = (datetime.now(created_date.tzinfo) - created_date).days
            print(f"👶 User age: {enriched_data['user_age_days']} days")
        except:
            enriched_data['user_age_days'] = 999
    
    # ✨ NOUVELLE LOGIQUE: Config rules + ML
    decision_result = moderator.moderate_with_learning(enriched_data)
    
    decision = decision_result['decision']
    reason = decision_result['reason']
    confidence = decision_result.get('confidence', 1.0)
    rule_matched = decision_result.get('rule_matched', 'none')
    
    # ✨ LOG DECISION
    emoji = '✅' if decision == 'APPROVED' else '❌' if decision == 'REJECTED' else '🧑‍⚖️'
    print(f"\n{emoji} DECISION: {decision}")
    print(f"📝 Reason: {reason}")
    print(f"🎯 Rule: {rule_matched}")
    print(f"💯 Confidence: {confidence:.1%}")
    print(f"{'='*60}\n")
    
    # ✨ GESTION NEEDS_REVIEW
    if decision == ModerationDecision.NEEDS_REVIEW:
        save_for_review(request_id, enriched_data, decision_result)
        return {
            'decision': 'NEEDS_REVIEW',
            'reason': reason,
            'confidence': confidence,
            'action': 'pending_staff_review',
            'title': title
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
    approved_count = 0
    rejected_count = 0
    needs_review_count = 0
    
    for req in requests:
        result = moderate_request(req['id'], req)
        results.append(result)
        
        # Count decisions
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


# ✨ NOUVEAU: Endpoint HTML pour HTMX
@app.get("/moderate-html", response_class=HTMLResponse)
async def moderate_html():
    """Endpoint HTML pour HTMX - Modération manuelle"""
    try:
        # Lance la modération
        result = await manual_moderate()
        
        # Parse résultat
        approved = result.get('approved', 0)
        rejected = result.get('rejected', 0)
        needs_review = result.get('needs_review', 0)
        total = approved + rejected + needs_review
        details = result.get('details', [])
        
        # Génère HTML - UTILISE TRIPLES APOSTROPHES
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
        
        # Ajoute les détails
        if details and len(details) > 0:
            for item in details[:20]:
                title = item.get('title', 'Unknown')
                decision = item.get('decision', 'UNKNOWN')
                reason = item.get('reason', 'No reason provided')
                confidence = item.get('confidence', 0) * 100
                rule = item.get('rule_matched', 'none')
                
                # Couleur selon décision
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
            <div class="text-xs text-gray-500">Règle: {rule}</div>
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
        
        # Ferme le HTML
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
    """Stats endpoint for dashboard (compatibility with v1.5)"""
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


@app.get("/history", response_class=HTMLResponse)
async def history_page():
    """Page HTML historique"""
    with open("static/history.html", "r") as f:
        return f.read()


@app.get("/api/history")
async def history_data(filter: str = "all"):
    """API endpoint pour les données historique (JSON ou HTML)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Query avec filtre optionnel
    if filter == "all":
        cursor.execute("""
            SELECT request_id, decision, reason, confidence, rule_matched, timestamp 
            FROM decisions 
            ORDER BY timestamp DESC 
            LIMIT 100
        """)
    else:
        cursor.execute("""
            SELECT request_id, decision, reason, confidence, rule_matched, timestamp 
            FROM decisions 
            WHERE decision = ?
            ORDER BY timestamp DESC 
            LIMIT 100
        """, (filter,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Génère HTML pour HTMX
    if not rows:
        html = '''
        <div class="text-center py-12 bg-gray-800/30 rounded-xl">
            <div class="text-6xl mb-4">📭</div>
            <div class="text-2xl font-bold mb-2">Aucune décision</div>
            <div class="text-gray-400">L'historique est vide</div>
        </div>
        '''
        return HTMLResponse(content=html)
    
    html = '<div class="space-y-3">'
    
    for row in rows:
        request_id, decision, reason, confidence, rule_matched, timestamp = row
        
        # Couleur selon décision
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
        
        confidence_pct = int(confidence * 100)
        
        html += f'''
        <div class="{color} border rounded-xl p-5 hover:shadow-lg transition">
            <div class="flex justify-between items-start mb-3">
                <div class="flex items-center gap-3">
                    <span class="text-3xl">{emoji}</span>
                    <div>
                        <div class="font-bold text-white text-lg">Request #{request_id}</div>
                        <div class="text-xs {text_color} font-semibold">{decision}</div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-xs {text_color} bg-gray-900/50 px-3 py-1 rounded-full mb-1">
                        {confidence_pct}% confiance
                    </div>
                    <div class="text-xs text-gray-500" data-timestamp="{timestamp}">
                        {timestamp}
                    </div>
                </div>
            </div>
            <div class="text-sm {text_color} opacity-90 mb-2">
                💬 {reason}
            </div>
            <div class="text-xs text-gray-500">
                🎯 Règle: <span class="font-mono">{rule_matched}</span>
            </div>
        </div>
        '''
    
    html += '</div>'
    
    return HTMLResponse(content=html)

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
