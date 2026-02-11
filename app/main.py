from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import json

# ===== CONFIGURATION GLOBALE =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "true").lower() == "true"
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055")
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # 🆕 Optionnel
DB_PATH = "/config/moderation.db"

# Validation des variables requises
if not OVERSEERR_API_KEY:
    print("⚠️  WARNING: OVERSEERR_API_KEY not set!")
if not OVERSEERR_URL:
    print("⚠️  WARNING: OVERSEERR_API_URL not set!")

# Log de configuration
print(f"\n{'='*60}")
print(f"⚙️  PLEXSTAFFAI CONFIGURATION")
print(f"{'='*60}")
print(f"📍 Overseerr URL: {OVERSEERR_URL}")
print(f"🔑 Overseerr API Key: {'***' + OVERSEERR_API_KEY[-4:] if OVERSEERR_API_KEY else 'NOT SET'}")
print(f"🎬 TMDB API Key: {'SET ✅' if TMDB_API_KEY else 'NOT SET ⚠️'}")
print(f"🤖 OpenAI Enabled: {'YES ✅' if OPENAI_ENABLED and OPENAI_API_KEY else 'NO (Rules-Only Mode)'}")
if OPENAI_ENABLED and OPENAI_API_KEY:
    print(f"🔑 OpenAI API Key: ***{OPENAI_API_KEY[-4:]}")
print(f"🔔 Webhook Mode: ENABLED (Instant moderation ⚡)")
print(f"🔒 Webhook Secret: {'SET ✅' if WEBHOOK_SECRET else 'NOT SET (public)'}")
print(f"💾 Database Path: {DB_PATH}")
print(f"{'='*60}\n")

# ✨ IMPORTS - Système AI-First (APRÈS la config)
from app.config_loader import ConfigManager, SmartModerator, ModerationDecision
from app.ml_feedback import FeedbackDatabase, EnhancedModerator
from app.openai_moderator import OpenAIModerator
from app.rules_validator import RulesValidator

# ===== INITIALISATION FASTAPI =====
app = FastAPI(title="PlexStaffAI", version="1.7.0")

# ===== INITIALISATION DES MODULES =====
config = ConfigManager("/config/config.yaml")
feedback_db = FeedbackDatabase("/config/feedback.db")
moderator = EnhancedModerator(config, feedback_db)
rules_validator = RulesValidator(config)

# 🆕 OpenAI Moderator (FACULTATIF)
openai_moderator = None
if OPENAI_ENABLED and OPENAI_API_KEY:
    try:
        openai_moderator = OpenAIModerator(OPENAI_API_KEY)
        print("✅ OpenAI moderation enabled (AI + Rules mode)")
    except Exception as e:
        print(f"⚠️  OpenAI initialization failed: {e}")
        print("ℹ️  Falling back to rules-only mode")
        openai_moderator = None
else:
    print("ℹ️  OpenAI moderation disabled (Rules-Only mode)")

print("✅ PlexStaffAI initialization complete\n")


def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Decisions table (historique)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            title TEXT,
            username TEXT,
            media_type TEXT,
            decision TEXT,
            reason TEXT,
            confidence REAL DEFAULT 1.0,
            rule_matched TEXT DEFAULT 'legacy',
            request_data JSON,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: Ajoute colonnes si elles n'existent pas
    cursor.execute("PRAGMA table_info(decisions)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    if 'request_data' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE decisions ADD COLUMN request_data JSON")
            print("✅ Added request_data column to decisions table")
        except:
            pass

    if 'title' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE decisions ADD COLUMN title TEXT")
            print("✅ Added title column to decisions table")
        except:
            pass

    if 'username' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE decisions ADD COLUMN username TEXT")
            print("✅ Added username column to decisions table")
        except:
            pass

    if 'media_type' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE decisions ADD COLUMN media_type TEXT")
            print("✅ Added media_type column to decisions table")
        except:
            pass

    # Pending reviews table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER UNIQUE,
            title TEXT,
            username TEXT,
            media_type TEXT,
            request_data JSON,
            ai_decision TEXT,
            ai_reason TEXT,
            ai_confidence REAL,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration pour pending_reviews
    cursor.execute("PRAGMA table_info(pending_reviews)")
    existing_columns_pr = [col[1] for col in cursor.fetchall()]

    if 'title' not in existing_columns_pr:
        try:
            cursor.execute("ALTER TABLE pending_reviews ADD COLUMN title TEXT")
            print("✅ Added title column to pending_reviews table")
        except:
            pass

    if 'username' not in existing_columns_pr:
        try:
            cursor.execute("ALTER TABLE pending_reviews ADD COLUMN username TEXT")
            print("✅ Added username column to pending_reviews table")
        except:
            pass

    if 'media_type' not in existing_columns_pr:
        try:
            cursor.execute("ALTER TABLE pending_reviews ADD COLUMN media_type TEXT")
            print("✅ Added media_type column to pending_reviews table")
        except:
            pass

    conn.commit()
    conn.close()


# ===== STARTUP EVENT =====
@app.on_event("startup")
async def startup_event():
    """Initialize app on startup"""
    init_db()
    cleanup_stale_reviews()

    print(f"\n🚀 {'='*60}")
    print(f"🚀 PLEXSTAFFAI v1.7.0 STARTED")
    print(f"🚀 Mode: WEBHOOK (Instant moderation ⚡)")
    print(f"🚀 OpenAI: {'✅ Configured' if openai_moderator else '❌ Disabled'}")
    print(f"🚀 TMDB: {'✅ Configured' if TMDB_API_KEY else '❌ Not set'}")
    print(f"🚀 {'='*60}\n")


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
            f"{OVERSEERR_URL}/api/v1/request",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            params={"take": 50, "skip": 0, "filter": "pending"},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"Error fetching Overseerr requests: {e}")
        return []


def approve_overseerr_request(request_id: int) -> bool:
    """Approve request in Overseerr with 404 handling"""
    try:
        response = httpx.post(
            f"{OVERSEERR_URL}/api/v1/request/{request_id}/approve",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            timeout=30.0
        )

        if response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr (already processed or deleted)")
            return True

        response.raise_for_status()
        print(f"✅ Approved request {request_id} in Overseerr")
        return True

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr")
            return True
        print(f"❌ Error approving request {request_id}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error approving request {request_id}: {e}")
        return False


def decline_overseerr_request(request_id: int) -> bool:
    """Decline request in Overseerr with 404 handling"""
    try:
        response = httpx.post(
            f"{OVERSEERR_URL}/api/v1/request/{request_id}/decline",
            headers={"X-Api-Key": OVERSEERR_API_KEY},
            timeout=30.0
        )

        if response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr (already processed or deleted)")
            return True

        response.raise_for_status()
        print(f"❌ Declined request {request_id} in Overseerr")
        return True

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr")
            return True
        print(f"❌ Error declining request {request_id}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error declining request {request_id}: {e}")
        return False


def cleanup_stale_reviews():
    """Remove reviews for requests that no longer exist in Overseerr"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, request_id, title
        FROM pending_reviews 
        WHERE status = 'pending'
    """)

    reviews = cursor.fetchall()
    removed = 0

    for review_id, request_id, title in reviews:
        try:
            response = httpx.get(
                f"{OVERSEERR_URL}/api/v1/request/{request_id}",
                headers={"X-Api-Key": OVERSEERR_API_KEY},
                timeout=10.0
            )

            if response.status_code == 404:
                cursor.execute("""
                    UPDATE pending_reviews 
                    SET status = 'stale' 
                    WHERE id = ?
                """, (review_id,))
                removed += 1
                print(f"🗑️  Removed stale review #{review_id}: {title} (request {request_id} no longer exists)")

        except Exception as e:
            print(f"⚠️  Error checking request {request_id}: {e}")

    conn.commit()
    conn.close()

    if removed > 0:
        print(f"🧹 Cleaned up {removed} stale review(s)")

    return removed


@app.get("/staff/cleanup-reviews")
async def cleanup_reviews_endpoint():
    """Cleanup stale reviews (requests no longer in Overseerr)"""
    removed = cleanup_stale_reviews()
    return {"removed": removed, "message": f"Cleaned up {removed} stale reviews"}


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
    RULES-FIRST Moderation with AI Fallback

    Workflow:
    1. Rules validation FIRST (genres whitelist/blacklist, ratings strictes)
    2. Si règle stricte match → Skip OpenAI (économise tokens)
    3. Sinon → OpenAI analyse + Rules ajustements
    """

    media = request_data.get('media', {})
    media_type = media.get('mediaType', 'unknown')
    tmdb_id = media.get('tmdbId')

    requested_by_obj = request_data.get('requestedBy', {})
    username = requested_by_obj.get('displayName') or                requested_by_obj.get('username') or                requested_by_obj.get('email') or                'Unknown User'
    user_id = str(requested_by_obj.get('id', 'unknown'))

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

    title = get_title_from_media(media, tmdb_enriched)
    year = tmdb_enriched.get('year') or (media.get('releaseDate', '')[:4] if media.get('releaseDate') else '')
    requested_by = username

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

    user_created = request_data.get('requestedBy', {}).get('createdAt', '')
    if user_created:
        try:
            created_date = datetime.fromisoformat(user_created.replace('Z', '+00:00'))
            enriched_data['user_age_days'] = (datetime.now(created_date.tzinfo) - created_date).days
            print(f"👶 User age: {enriched_data['user_age_days']} days")
        except:
            enriched_data['user_age_days'] = 999

    print(f"\n🎯 {'='*60}")
    print(f"🎯 PRE-VALIDATION: Checking strict rules FIRST")
    print(f"🎯 {'='*60}")

    fake_ai_result = {
        'decision': 'PENDING',
        'confidence': 0.5,
        'reason': 'Pre-validation check'
    }

    pre_validation = rules_validator.validate(fake_ai_result, enriched_data)

    if pre_validation['rule_override']:
        decision = pre_validation['final_decision']
        confidence = pre_validation['final_confidence']
        reason = pre_validation['final_reason']
        rule_matched = f"rule_strict:{','.join(pre_validation['rules_matched'][:2])}"

        print(f"⚡ FAST PATH: Strict rule override, skipping OpenAI")
        print(f"⚡ Decision: {decision} ({confidence:.1%})")

        emoji = '✅' if decision == 'APPROVED' else '❌' if decision == 'REJECTED' else '🧑‍⚖️'
        print(f"\n{emoji} {'='*60}")
        print(f"{emoji} FINAL DECISION: {decision}")
        print(f"📝 Reason: {reason}")
        print(f"🎯 Path: {rule_matched}")
        print(f"💯 Confidence: {confidence:.1%}")
        print(f"💰 OpenAI Cost: $0.00 (skipped)")
        print(f"{emoji} {'='*60}\n")

        if decision == 'NEEDS_REVIEW':
            save_for_review(request_id, enriched_data, {
                'decision': decision,
                'reason': reason,
                'confidence': confidence,
                'rule_matched': rule_matched
            }, title=title, username=username, media_type=media_type)

            return {
                'decision': 'NEEDS_REVIEW',
                'reason': reason,
                'confidence': confidence,
                'action': 'pending_staff_review',
                'title': title,
                'username': username,
                'media_type': media_type
            }

        if decision == 'APPROVED':
            approve_overseerr_request(request_id)
        elif decision == 'REJECTED':
            decline_overseerr_request(request_id)

        save_decision(request_id, decision, reason, confidence, rule_matched, 
                      enriched_data, title=title, username=username, media_type=media_type)

        return {
            'request_id': request_id,
            'decision': decision,
            'reason': reason,
            'confidence': confidence,
            'rule_matched': rule_matched,
            'title': title,
            'username': username,
            'media_type': media_type
        }

    print(f"⚡ No strict rule match, consulting OpenAI...")

    if openai_moderator:
        ai_result = openai_moderator.moderate(enriched_data)

        validation_result = rules_validator.validate(ai_result, enriched_data)

        decision = validation_result['final_decision']
        confidence = validation_result['final_confidence']
        reason = validation_result['final_reason']

        if validation_result['rule_override']:
            rule_matched = f"ai_override:{','.join(validation_result['rules_matched'][:2])}"
        else:
            rule_matched = f"ai_primary:{ai_result.get('model_used', 'gpt-4o-mini')}"

    else:
        print("⚠️  OpenAI not configured, using rule-based fallback")
        decision_result = moderator.moderate_with_learning(enriched_data)
        decision = decision_result['decision']
        reason = decision_result['reason']
        confidence = decision_result.get('confidence', 1.0)
        rule_matched = decision_result.get('rule_matched', 'fallback')

    emoji = '✅' if decision == 'APPROVED' else '❌' if decision == 'REJECTED' else '🧑‍⚖️'
    print(f"\n{emoji} {'='*60}")
    print(f"{emoji} FINAL DECISION: {decision}")
    print(f"📝 Reason: {reason}")
    print(f"🎯 Path: {rule_matched}")
    print(f"💯 Confidence: {confidence:.1%}")
    print(f"{emoji} {'='*60}\n")

    if decision == 'NEEDS_REVIEW':
        save_for_review(request_id, enriched_data, {
            'decision': decision,
            'reason': reason,
            'confidence': confidence,
            'rule_matched': rule_matched
        }, title=title, username=username, media_type=media_type)

        return {
            'decision': 'NEEDS_REVIEW',
            'reason': reason,
            'confidence': confidence,
            'action': 'pending_staff_review',
            'title': title,
            'username': username,
            'media_type': media_type
        }

    if decision == 'APPROVED':
        approve_overseerr_request(request_id)
    elif decision == 'REJECTED':
        decline_overseerr_request(request_id)

    save_decision(request_id, decision, reason, confidence, rule_matched, 
                  enriched_data, title=title, username=username, media_type=media_type)

    return {
        'request_id': request_id,
        'decision': decision,
        'reason': reason,
        'confidence': confidence,
        'rule_matched': rule_matched,
        'title': title,
        'username': username,
        'media_type': media_type
    }


def save_for_review(request_id: int, enriched_data: dict, ai_result: dict, 
                    title: str, username: str, media_type: str):
    """Sauvegarde une requête pour révision manuelle"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO pending_reviews 
        (request_id, title, username, media_type, request_data, 
         ai_decision, ai_reason, ai_confidence, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        request_id,
        title,
        username,
        media_type,
        json.dumps(enriched_data),
        ai_result.get('decision'),
        ai_result.get('reason'),
        ai_result.get('confidence'),
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    print(f"💾 Saved to pending_reviews: {title} by {username}")


def save_decision(request_id: int, decision: str, reason: str, 
                  confidence: float, rule_matched: str, enriched_data: dict,
                  title: str, username: str, media_type: str):
    """Sauvegarde la décision dans l'historique"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, decision, timestamp 
        FROM decisions 
        WHERE request_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (request_id,))

    existing = cursor.fetchone()

    if existing:
        existing_decision = existing[1]
        existing_timestamp = existing[2]

        try:
            if 'T' in existing_timestamp:
                existing_time = datetime.fromisoformat(existing_timestamp.replace('Z', '+00:00'))
            else:
                existing_time = datetime.strptime(existing_timestamp, '%Y-%m-%d %H:%M:%S')

            time_diff = datetime.now() - existing_time.replace(tzinfo=None)

            if time_diff.total_seconds() < 300:
                print(f"⏭️  Duplicate detected: Request #{request_id} already saved {int(time_diff.total_seconds())}s ago")
                conn.close()
                return

        except Exception as e:
            print(f"⚠️  Timestamp parse error: {e}")

    try:
        cursor.execute("""
            INSERT INTO decisions 
            (request_id, title, username, media_type, decision, reason, 
             confidence, rule_matched, request_data, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            title,
            username,
            media_type,
            decision,
            reason,
            confidence,
            rule_matched,
            json.dumps(enriched_data),
            datetime.now().isoformat()
        ))

        conn.commit()
        print(f"💾 Saved to decisions: {title} by {username} → {decision}")

    except sqlite3.IntegrityError as e:
        print(f"⚠️  Database constraint error (possible duplicate): {e}")
    except Exception as e:
        print(f"❌ Error saving decision: {e}")
    finally:
        conn.close()


def get_processed_request_ids() -> set:
    """Récupère les IDs de requêtes déjà traitées depuis la DB"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT request_id FROM decisions")

        processed_ids = {row[0] for row in cursor.fetchall()}

        conn.close()

        return processed_ids

    except Exception as e:
        print(f"⚠️  Error loading processed IDs: {e}")
        return set()


# ===== WEBHOOK ENDPOINT =====
@app.post("/webhook/overseerr")
async def overseerr_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive webhook from Overseerr for instant moderation

    Overseerr Configuration:
    - URL: http://plexstaffai:5056/webhook/overseerr
    - Authorization: Bearer YOUR_WEBHOOK_SECRET (optional)
    - Events: Media Requested, Media Pending
    """
    try:
        # 🔒 Vérifier le token si configuré
        if WEBHOOK_SECRET:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {WEBHOOK_SECRET}"
            if auth_header != expected:
                print(f"⚠️  Webhook unauthorized: {auth_header[:20]}...")
                raise HTTPException(status_code=401, detail="Unauthorized")

        payload = await request.json()

        notification_type = payload.get('notification_type', 'unknown')
        event = payload.get('event', 'unknown')
        subject = payload.get('subject', 'Unknown')

        print(f"\n🔔 {'='*60}")
        print(f"🔔 WEBHOOK RECEIVED from Overseerr")
        print(f"🔔 Type: {notification_type}")
        print(f"🔔 Event: {event}")
        print(f"🔔 Subject: {subject}")
        print(f"🔔 {'='*60}\n")

        # Extraire request_id
        request_id = None
        request_data = payload.get('request', {})

        if request_data:
            request_id = request_data.get('request_id') or request_data.get('id')

        if not request_id:
            media_data = payload.get('media', {})
            request_id = media_data.get('request_id')

        if not request_id:
            print("⚠️  No request_id found in webhook payload")
            print(f"📦 Full payload: {json.dumps(payload, indent=2)}")
            return {"status": "ignored", "reason": "no request_id"}

        # Vérifier si déjà traité
        already_processed = get_processed_request_ids()

        if request_id in already_processed:
            print(f"⏭️  Request #{request_id} already processed, skipping")
            return {
                "status": "skipped", 
                "request_id": request_id,
                "reason": "already_processed"
            }

        # 🚀 Trigger modération en arrière-plan (non-bloquant)
        background_tasks.add_task(process_webhook_request, request_id, payload)

        return {
            "status": "accepted",
            "request_id": request_id,
            "message": "Moderation triggered ⚡"
        }

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        print(f"❌ Webhook JSON parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def process_webhook_request(request_id: int, webhook_payload: dict):
    """Process a single request from webhook (background task)"""
    try:
        print(f"\n🎬 {'='*60}")
        print(f"🎬 PROCESSING WEBHOOK REQUEST #{request_id}")
        print(f"🎬 {'='*60}\n")

        # Récupérer les détails complets depuis Overseerr
        try:
            response = httpx.get(
                f"{OVERSEERR_URL}/api/v1/request/{request_id}",
                headers={"X-Api-Key": OVERSEERR_API_KEY},
                timeout=10.0
            )
            response.raise_for_status()
            request_details = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"⚠️  Request #{request_id} not found in Overseerr (may be deleted)")
                return
            raise

        # Modérer
        result = moderate_request(request_id, request_details)

        decision = result.get('decision', 'UNKNOWN')
        print(f"\n✅ Webhook request #{request_id} processed: {decision}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ Error processing webhook request #{request_id}: {e}")
        import traceback
        traceback.print_exc()


# ===== MANUAL TRIGGER ENDPOINT (pour tests) =====
@app.post("/admin/moderate-now")
async def manual_moderate_now(background_tasks: BackgroundTasks):
    """Manually trigger moderation for all pending requests"""
    try:
        requests = get_overseerr_requests()

        if not requests:
            return {
                "status": "success",
                "message": "No pending requests found",
                "processed": 0
            }

        already_processed = get_processed_request_ids()

        pending_count = 0
        for req in requests:
            request_id = req.get('id')
            if request_id not in already_processed:
                background_tasks.add_task(process_webhook_request, request_id, req)
                pending_count += 1

        return {
            "status": "success",
            "message": f"Processing {pending_count} pending request(s)",
            "total_found": len(requests),
            "already_processed": len(requests) - pending_count
        }

    except Exception as e:
        print(f"❌ Manual moderate error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


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
