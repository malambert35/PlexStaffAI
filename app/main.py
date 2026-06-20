from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import json

# ===== CONFIGURATION GLOBALE (EN PREMIER) =====
# 🆕 Définir TOUTES les variables AVANT les imports de modules
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ENABLED = os.getenv("OPENAI_ENABLED", "true").lower() == "true"
OVERSEERR_URL = os.getenv("OVERSEERR_API_URL", "http://overseerr:5055")  # 🆕 Renommé pour cohérence
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # 🆕 Optionnel pour sécuriser le webhook
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
app = FastAPI(title="PlexStaffAI", version="1.6.0")

# ===== INITIALISATION DES MODULES =====
# Config Manager
config = ConfigManager("/config/config.yaml")

# Feedback Database (ML Learning)
feedback_db = FeedbackDatabase("/config/feedback.db")

# Enhanced Moderator (fallback rule-based)
moderator = EnhancedModerator(config, feedback_db)

# Rules Validator (TOUJOURS actif)
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
            title TEXT,                          -- 🆕 AJOUTÉ
            username TEXT,                       -- 🆕 AJOUTÉ
            media_type TEXT,                     -- 🆕 AJOUTÉ (movie/tv)
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
            title TEXT,                          -- 🆕 AJOUTÉ
            username TEXT,                       -- 🆕 AJOUTÉ
            media_type TEXT,                     -- 🆕 AJOUTÉ
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
        
        # 🆕 Si 404, la requête n'existe plus (déjà traitée ou supprimée)
        if response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr (already processed or deleted)")
            return True  # ✅ Considère comme succès
        
        response.raise_for_status()
        print(f"✅ Approved request {request_id} in Overseerr")
        return True
        
    except httpx.HTTPStatusError as e:
        # 🆕 Gérer 404 aussi dans les exceptions
        if e.response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr")
            return True  # ✅ Considère comme succès
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
        
        # 🆕 Si 404, la requête n'existe plus
        if response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr (already processed or deleted)")
            return True  # ✅ Considère comme succès
        
        response.raise_for_status()
        print(f"❌ Declined request {request_id} in Overseerr")
        return True
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"⚠️  Request {request_id} not found in Overseerr")
            return True  # ✅ Considère comme succès
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
        # Vérifie si la requête existe dans Overseerr
        try:
            response = httpx.get(
                f"{OVERSEERR_URL}/api/v1/request/{request_id}",
                headers={"X-Api-Key": OVERSEERR_API_KEY},
                timeout=10.0
            )
            
            if response.status_code == 404:
                # Requête n'existe plus, supprimer la review
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

# Endpoint pour nettoyer manuellement
@app.get("/staff/cleanup-reviews")
async def cleanup_reviews_endpoint():
    """Cleanup stale reviews (requests no longer in Overseerr)"""
    removed = cleanup_stale_reviews()
    return {"removed": removed, "message": f"Cleaned up {removed} stale reviews"}


# Appeler automatiquement au démarrage
@app.on_event("startup")
async def startup_cleanup():
    """Cleanup stale reviews on startup"""
    print("🧹 Cleaning up stale reviews...")
    cleanup_stale_reviews()

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


def run_moderation(request_id: int, request_details: dict, extracted_info: dict = None):
    """Run the complete rules-first moderation workflow for one request.

    Overseerr's polling API and webhook payloads use different field names;
    normalize both forms here so every entry point follows the same path.
    """
    try:
        request_obj = request_details.get('request') or request_details
        media = request_details.get('media') or request_obj.get('media') or {}
        requested_by = request_obj.get('requestedBy') or request_details.get('requestedBy') or {}
        if not isinstance(requested_by, dict):
            requested_by = {}

        media_type = (
            (extracted_info or {}).get('media_type')
            or media.get('mediaType')
            or media.get('media_type')
            or request_details.get('mediaType')
            or 'movie'
        ).lower()
        media_type = 'tv' if media_type in {'tv', 'show'} else 'movie'

        tmdb_id = media.get('tmdbId') or media.get('tmdb_id') or request_details.get('tmdbId')
        try:
            tmdb_id = int(tmdb_id) if tmdb_id else None
        except (TypeError, ValueError):
            tmdb_id = None
        tmdb_data = enrich_from_tmdb(tmdb_id, media_type) if tmdb_id else {}

        title = (
            (extracted_info or {}).get('title')
            or media.get('title')
            or media.get('name')
            or tmdb_data.get('title')
            or tmdb_data.get('original_title')
            or request_details.get('subject')
            or f'Request #{request_id}'
        )
        username = (
            (extracted_info or {}).get('username')
            or request_obj.get('requestedBy_username')
            or requested_by.get('displayName')
            or requested_by.get('username')
            or 'Unknown'
        )

        moderation_data = {
            **tmdb_data,
            'title': title,
            'media_type': media_type,
            'requested_by': username,
            'user_id': requested_by.get('id') or request_obj.get('requestedById'),
            # Missing account age must not accidentally classify a user as new.
            'user_age_days': request_details.get('user_age_days', 999),
            'genres': tmdb_data.get('genres') or media.get('genres') or [],
            'rating': tmdb_data.get('rating', media.get('voteAverage', 0)),
            'popularity': tmdb_data.get('popularity', media.get('popularity', 0)),
            'year': tmdb_data.get('year') or str(media.get('releaseDate') or '')[:4],
            'episode_count': tmdb_data.get('episode_count', 0),
            'season_count': tmdb_data.get('season_count', 0),
        }

        # Clear allow/deny cases bypass OpenAI to save cost and latency.
        precheck = rules_validator.validate(
            {'decision': 'PENDING', 'confidence': 0.5, 'reason': 'Rules pre-check'},
            moderation_data,
        )
        if precheck['final_decision'] != 'PENDING':
            result = {
                'decision': precheck['final_decision'],
                'confidence': precheck['final_confidence'],
                'reason': precheck['final_reason'],
                'rule_matched': ', '.join(precheck['rules_matched']) or 'strict_rule',
                'source': 'strict_rules',
            }
        elif openai_moderator:
            ai_result = openai_moderator.moderate(moderation_data)
            validated = rules_validator.validate(ai_result, moderation_data)
            result = {
                'decision': validated['final_decision'],
                'confidence': validated['final_confidence'],
                'reason': validated['final_reason'],
                'rule_matched': ', '.join(validated['rules_matched']) or 'openai',
                'source': 'openai',
            }
        else:
            result = moderator.moderate_with_learning(moderation_data)

        decision = result['decision']
        reason = result['reason']
        confidence = result['confidence']
        rule_matched = result.get('rule_matched') or result.get('source', 'rules_only')

        if decision == 'APPROVED':
            action_succeeded = approve_overseerr_request(request_id)
        elif decision == 'REJECTED':
            action_succeeded = decline_overseerr_request(request_id)
        else:
            save_for_review(request_id, moderation_data, result, title, username, media_type)
            action_succeeded = True

        # A failed call to Overseerr must remain actionable instead of being
        # recorded as a completed approval/rejection.
        if not action_succeeded:
            decision = 'NEEDS_REVIEW'
            reason = f'Could not apply {result["decision"]} in Overseerr; manual review required.'
            confidence = 0.0
            rule_matched = 'overseerr_action_failed'
            save_for_review(request_id, moderation_data, {
                'decision': decision, 'reason': reason, 'confidence': confidence
            }, title, username, media_type)

        save_decision(
            request_id, decision, reason, confidence, rule_matched,
            moderation_data, title, username, media_type,
        )
        print(f"Decision #{request_id}: {decision} ({rule_matched})")
        return {
            **result,
            'decision': decision,
            'reason': reason,
            'confidence': confidence,
            'title': title,
            'saved': True,
        }
    except Exception as e:
        print(f"run_moderation ERROR: {e}")
        return {'decision': 'ERROR', 'error': str(e), 'saved': False}


def save_for_review(request_id: int, enriched_data: dict, ai_result: dict, 
                    title: str, username: str, media_type: str):
    """Sauvegarde une requête pour révision manuelle"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Extraire les données avec fallback
    final_title = title or enriched_data.get('title', f'Request {request_id}')
    final_username = username or enriched_data.get('requested_by', 'Unknown')
    final_media_type = media_type or enriched_data.get('media_type', 'unknown')
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO pending_reviews 
            (request_id, title, username, media_type, request_data, 
             ai_decision, ai_reason, ai_confidence, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            request_id,
            final_title,
            final_username,
            final_media_type,
            json.dumps(enriched_data),
            ai_result.get('decision', 'NEEDS_REVIEW'),
            ai_result.get('reason', ''),
            ai_result.get('confidence', 0.8),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        print(f"💾 Saved to pending_reviews: {final_title} by {final_username}")
        
    except Exception as e:
        print(f"❌ Error saving to pending_reviews: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def save_decision(request_id: int, decision: str, reason: str, 
                  confidence: float, rule_matched: str, enriched_data: dict,
                  title: str, username: str, media_type: str):  # 🆕 params
    """Sauvegarde la décision dans l'historique"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO decisions 
        (request_id, title, username, media_type, decision, reason, 
         confidence, rule_matched, request_data, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request_id,
        title,                              # 🆕
        username,                           # 🆕
        media_type,                         # 🆕
        decision,
        reason,
        confidence,
        rule_matched,
        json.dumps(enriched_data),
        datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    
    print(f"💾 Saved to decisions: {title} by {username} → {decision}")


def get_processed_request_ids() -> set:
    """
    Récupère les IDs de requêtes déjà traitées depuis la DB
    
    Returns:
        Set d'IDs de requêtes (pour lookup O(1) rapide)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Récupérer tous les request_id déjà dans decisions
        cursor.execute("SELECT DISTINCT request_id FROM decisions")
        
        processed_ids = {row[0] for row in cursor.fetchall()}
        
        conn.close()
        
        return processed_ids
        
    except Exception as e:
        print(f"⚠️  Error loading processed IDs: {e}")
        return set()

def save_decision(request_id: int, decision: str, reason: str, confidence: float, 
                  rule_matched: str, request_data: dict, title: str = None, 
                  username: str = None, media_type: str = None):
    """Save moderation decision to database (avec protection anti-doublon)"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 🆕 Vérifier si déjà traité récemment (dernières 5 minutes)
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
            # Parse timestamp (ISO format ou datetime string)
            if 'T' in existing_timestamp:
                existing_time = datetime.fromisoformat(existing_timestamp.replace('Z', '+00:00'))
            else:
                existing_time = datetime.strptime(existing_timestamp, '%Y-%m-%d %H:%M:%S')
            
            time_diff = datetime.now() - existing_time.replace(tzinfo=None)
            
            # Si même décision dans les 5 dernières minutes → skip
            if time_diff.total_seconds() < 300:  # 5 minutes
                print(f"⏭️  Duplicate detected: Request #{request_id} already saved {int(time_diff.total_seconds())}s ago")
                conn.close()
                return
                
        except Exception as e:
            print(f"⚠️  Timestamp parse error: {e}")
    
    # Extraire title, username si pas fournis
    if not title or not username or not media_type:
        try:
            media = request_data.get('media', {})
            if not title:
                title = media.get('title') or media.get('name') or f"Request #{request_id}"
            if not username:
                requested_by = request_data.get('requestedBy', {})
                username = requested_by.get('displayName') or \
                          requested_by.get('username') or \
                          requested_by.get('email') or \
                          'Unknown'
            if not media_type:
                media_type = media.get('mediaType', 'unknown')
        except Exception as e:
            print(f"⚠️  Error extracting metadata: {e}")
    
    # Fallbacks
    title = title or f"Request #{request_id}"
    username = username or "Unknown"
    media_type = media_type or "unknown"
    
    # Save to database
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
            json.dumps(request_data),
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

@app.post("/webhook/overseerr")
async def overseerr_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
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
        print(f"🔔 Request obj: {payload.get('request')}")
        print(f"🔔 Media obj: {payload.get('media')}")
        print(f"🔔 {'='*60}\n")
        
        # ✅ Use real keys: 'request' and 'media'
        request_id = None

        req_obj = payload.get('request') or {}
        if req_obj:
            request_id = req_obj.get('request_id') or req_obj.get('id')
            print(f"🔍 Found request_id in request: {request_id}")

        if not request_id:
            media_obj = payload.get('media') or {}
            request_id = media_obj.get('request_id')
            print(f"🔍 Found request_id in media: {request_id}")

        if not request_id:
            request_id = payload.get('request_id')
            print(f"🔍 Found request_id in root: {request_id}")

        if not request_id:
            print("❌ NO REQUEST_ID FOUND!")
            print(f"📦 FULL PAYLOAD: {json.dumps(payload, indent=2)}")
            return {"status": "ignored", "reason": "no request_id"}

        request_id = int(request_id)
        print(f"🎯 REQUEST_ID EXTRACTED: {request_id}")
        
        already_processed = get_processed_request_ids()
        if request_id in already_processed:
            print(f"⏭️  Request #{request_id} already processed, skipping")
            return {"status": "skipped", "request_id": request_id, "reason": "already_processed"}
        
        # For now, keep it synchronous to be sure it runs
        process_webhook_request(request_id, payload)
        
        return {
            "status": "processed",
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
    """Process webhook → Extract → Save via moderate_request"""
    try:
        print(f"\n🎬 PROCESSING WEBHOOK REQUEST #{request_id}")
        
        # ✅ Use real keys: 'request' and 'media'
        request_obj = webhook_payload.get('request') or {}
        media_obj = webhook_payload.get('media') or {}
        
        username = request_obj.get('requestedBy_username') or 'Unknown'
        media_type = media_obj.get('media_type', 'movie')
        
        tmdb_id = media_obj.get('tmdbId') or media_obj.get('tmdbid')
        title = webhook_payload.get('subject') or f"Request #{request_id}"
        if tmdb_id:
            title = lookup_tmdb_title(tmdb_id, media_type)
        
        print(f"✅ EXTRAIT: USER='{username}' TITLE='{title}' TYPE='{media_type}' TMDB={tmdb_id}")
        
        extracted_info = {
            'title': title,
            'username': username,
            'media_type': media_type
        }
        
        result = run_moderation(request_id, webhook_payload, extracted_info)
        
        if result.get('saved'):
            print(f"✅ #{request_id} SAVED SUCCESS!")
        else:
            print(f"❌ #{request_id} SAVE FAILED: {result}")
            
    except Exception as e:
        print(f"💥 WEBHOOK PROCESS ERROR #{request_id}: {e}")
        import traceback
        traceback.print_exc()


def save_pending_review(request_id: int, title: str, username: str, media_type: str, payload: dict):
    """Save to pending_reviews with populated fields"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Delete existing
        cursor.execute("DELETE FROM pending_reviews WHERE request_id = ?", (request_id,))
        
        # Insert populated record
        cursor.execute("""
            INSERT INTO pending_reviews (
                request_id, title, username, media_type, 
                request_data, ai_reason, ai_confidence, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            request_id, 
            title, 
            username, 
            media_type,
            json.dumps(payload),
            "Upcoming release (2026), no rating available yet - requires manual staff review...", 
            0.8,
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()  # ✅ CRITICAL: Commit the transaction
        print(f"💾 SAVED #{request_id}: '{title}' by '{username}'")
        
    except Exception as e:
        print(f"❌ save_pending_review ERROR #{request_id}: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

def lookup_tmdb_title(tmdb_id: int, media_type: str = 'movie') -> str:
    """TMDB title lookup with error handling"""
    if not TMDB_API_KEY:
        print("⚠️ No TMDB_API_KEY - using fallback title")
        return f"Request TMDB #{tmdb_id}"
    
    try:
        base_url = "https://api.themoviedb.org/3"
        if media_type == 'tv':
            url = f"{base_url}/tv/{tmdb_id}"
        else:
            url = f"{base_url}/movie/{tmdb_id}"
            
        resp = httpx.get(
            url,
            params={"api_key": TMDB_API_KEY, "language": "fr-FR"},
            timeout=5
        )
        resp.raise_for_status()
        
        data = resp.json()
        title = data.get('title') or data.get('name', f"#{tmdb_id}")
        release_date = data.get('release_date') or data.get('first_air_date', '')
        if release_date:
            title += f" ({release_date[:4]})"
            
        return title
        
    except Exception as e:
        print(f"⚠️ TMDB error {tmdb_id}: {e}")
        return f"TMDB #{tmdb_id}"


def process_webhook_request(request_id: int, webhook_payload: dict):
    try:
        print(f"\n🎬 PROCESSING WEBHOOK REQUEST #{request_id}")
        
        request_obj = webhook_payload.get('request') or {}
        media_obj = webhook_payload.get('media') or {}
        
        # ✅ FIXED username extraction
        username = request_obj.get('requestedBy_username') or 'Unknown'
        media_type = media_obj.get('media_type', 'movie')
        
        tmdb_id = media_obj.get('tmdbId') or media_obj.get('tmdbid')
        title = webhook_payload.get('subject') or f"Request #{request_id}"
        if tmdb_id:
            title = lookup_tmdb_title(tmdb_id, media_type)
        
        print(f"✅ EXTRAIT: USER='{username}' TITLE='{title}' TYPE='{media_type}' TMDB={tmdb_id}")
        
        extracted_info = {
            'title': title,
            'username': username,
            'media_type': media_type
        }
        
        result = run_moderation(request_id, webhook_payload, extracted_info)
        
        print(f"RESULT: {result}")
        
    except Exception as e:
        print(f"💥 ERROR #{request_id}: {e}")
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
        result = run_moderation(req['id'], req)
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
        "last_24h": last_24h,
        "openai_enabled": openai_moderator is not None  # 🆕 Statut OpenAI
    }


@app.get("/staff/report", response_class=HTMLResponse)
async def staff_report_html():
    """Full report page with language support"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Stats globales
    cursor.execute("SELECT COUNT(*) FROM decisions")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM decisions WHERE decision = 'APPROVED'")
    approved = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM decisions WHERE decision = 'REJECTED'")
    rejected = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(confidence) FROM decisions")
    avg_conf = cursor.fetchone()[0] or 0
    
    approval_rate = int((approved / total * 100)) if total > 0 else 0
    
    # Activité récente
    cursor.execute("""
        SELECT request_id, decision, reason, timestamp 
        FROM decisions 
        ORDER BY timestamp DESC 
        LIMIT 10
    """)
    recent = cursor.fetchall()
    
    conn.close()
    
    recent_html = ""
    for row in recent:
        decision_badge = {
            'APPROVED': '<span class="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs">✅ Approved</span>',
            'REJECTED': '<span class="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">❌ Rejected</span>',
            'NEEDS_REVIEW': '<span class="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">⚠️ Review</span>'
        }.get(row[1], row[1])
        
        recent_html += f"""
        <div class="flex justify-between items-center p-3 bg-gray-700/30 rounded-lg hover:bg-gray-700/50 transition">
            <div class="flex-1">
                <div class="font-semibold">Request #{row[0]}</div>
                <div class="text-sm text-gray-400">{row[2][:80]}...</div>
                <div class="text-xs text-gray-500 mt-1">{row[3]}</div>
            </div>
            <div>{decision_badge}</div>
        </div>
        """
    
    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-i18n="reportTitle">Rapport Complet</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .lang-selector {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 100;
            display: flex;
            gap: 8px;
            background: rgba(31, 41, 55, 0.95);
            backdrop-filter: blur(10px);
            padding: 8px;
            border-radius: 12px;
            border: 1px solid rgba(75, 85, 99, 0.5);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        .lang-btn {{
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            background: transparent;
            color: #9CA3AF;
        }}
        .lang-btn:hover {{
            background: rgba(75, 85, 99, 0.5);
            color: #E5E7EB;
        }}
        .lang-btn.active {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
        }}
        .lang-btn .flag {{
            font-size: 18px;
            margin-right: 6px;
        }}
    </style>
</head>
<body class="bg-gray-900 text-white font-sans antialiased">
    
    <div class="lang-selector">
        <button class="lang-btn active" data-lang="fr" onclick="setLanguage('fr')">
            <span class="flag">🇫🇷</span> FR
        </button>
        <button class="lang-btn" data-lang="en" onclick="setLanguage('en')">
            <span class="flag">🇬🇧</span> EN
        </button>
    </div>

    <div class="max-w-7xl mx-auto px-4 py-12">
        <div class="mb-8">
            <a href="/" class="text-blue-400 hover:text-blue-300 transition">
                <span data-i18n="backToDashboard">← Retour au Dashboard</span>
            </a>
        </div>
        
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 p-8 rounded-3xl border border-gray-700 shadow-2xl">
            <h1 class="text-4xl font-black mb-8 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                📊 <span data-i18n="reportTitle">Rapport Complet</span>
            </h1>
            
            <!-- Overview Stats -->
            <div class="mb-8">
                <h2 class="text-2xl font-bold mb-6" data-i18n="reportOverview">Vue d'ensemble</h2>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div class="bg-gradient-to-br from-gray-700 to-gray-800 p-6 rounded-2xl">
                        <div class="text-gray-400 mb-2" data-i18n="reportTotalRequests">Total des requests</div>
                        <div class="text-4xl font-black text-white">{total}</div>
                    </div>
                    <div class="bg-gradient-to-br from-emerald-900 to-teal-900 p-6 rounded-2xl">
                        <div class="text-gray-300 mb-2" data-i18n="approved">Approuvés</div>
                        <div class="text-4xl font-black text-emerald-300">{approved}</div>
                    </div>
                    <div class="bg-gradient-to-br from-red-900 to-pink-900 p-6 rounded-2xl">
                        <div class="text-gray-300 mb-2" data-i18n="rejected">Rejetés</div>
                        <div class="text-4xl font-black text-red-300">{rejected}</div>
                    </div>
                    <div class="bg-gradient-to-br from-purple-900 to-indigo-900 p-6 rounded-2xl">
                        <div class="text-gray-300 mb-2" data-i18n="reportApprovalRate">Taux d'approbation</div>
                        <div class="text-4xl font-black text-purple-300">{approval_rate}%</div>
                    </div>
                </div>
            </div>
            
            <!-- Recent Activity -->
            <div>
                <h2 class="text-2xl font-bold mb-6" data-i18n="reportRecentActivity">Activité récente</h2>
                <div class="space-y-3">
                    {recent_html if recent_html else '<div class="text-center py-8 text-gray-400">Aucune activité</div>'}
                </div>
            </div>
            
            <div class="mt-8 text-center">
                <a href="/history" class="inline-block px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-xl font-bold transition">
                    <span data-i18n="viewHistory">📜 Voir Historique Complet</span>
                </a>
            </div>
        </div>
    </div>
    
    <script src="/static/translations.js"></script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

@app.get("/history", response_class=HTMLResponse)
async def history_html():
    """History page with decisions (no cache, fixed layout)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Récupère les dernières décisions
    cursor.execute("""
        SELECT request_id, title, username, media_type, decision, reason, 
               confidence, timestamp
        FROM decisions
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    
    decisions = cursor.fetchall()
    conn.close()
    
    # Build rows HTML
    rows_html = ""
    for row in decisions:
        request_id, title, username, media_type, decision, reason, confidence, timestamp = row
        
        # Decision badge styling
        if decision == 'APPROVED':
            badge_class = 'bg-emerald-900/50 text-emerald-300 border border-emerald-700'
            icon = '✅'
        elif decision == 'REJECTED':
            badge_class = 'bg-red-900/50 text-red-300 border border-red-700'
            icon = '❌'
        else:
            badge_class = 'bg-yellow-900/50 text-yellow-300 border border-yellow-700'
            icon = '🧑‍⚖️'
        
        # Format timestamp
        try:
            if 'T' in timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            formatted_time = dt.strftime('%Y-%m-%d %H:%M')
        except:
            formatted_time = timestamp[:16] if timestamp else 'N/A'
        
        # Confidence percentage
        try:
            conf_pct = f"{float(confidence) * 100:.0f}%" if confidence else "N/A"
        except:
            conf_pct = str(confidence) if confidence else "N/A"
        
        # Truncate long reasons
        display_reason = reason[:80] + '...' if len(reason) > 80 else reason
        
        rows_html += f"""
        <tr class="border-b border-gray-800 hover:bg-gray-800/50 transition">
            <td class="px-6 py-4 font-mono text-blue-400">#{request_id}</td>
            <td class="px-6 py-4 font-semibold">{title}</td>
            <td class="px-6 py-4">
                <span class="px-2 py-1 bg-gray-700 rounded text-xs">
                    {media_type}
                </span>
            </td>
            <td class="px-6 py-4 text-gray-400">👤{username}</td>
            <td class="px-6 py-4">
                <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-bold whitespace-nowrap {badge_class}">
                    {icon} {decision}
                </span>
            </td>
            <td class="px-6 py-4 text-sm text-gray-400 max-w-md">
                {display_reason}
            </td>
            <td class="px-6 py-4 text-center">
                <span class="px-2 py-1 bg-purple-900/50 text-purple-300 rounded text-sm font-semibold">
                    {conf_pct}
                </span>
            </td>
            <td class="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">{formatted_time}</td>
        </tr>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PlexStaffAI - Historique</title>
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="/static/translations.js"></script>
    <style>
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        tbody tr {{
            animation: fadeIn 0.3s ease-out;
        }}
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="max-w-7xl mx-auto px-4 py-8">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-4xl font-black bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                📜 <span data-i18n="historyTitle">Historique des Décisions</span>
            </h1>
            <a href="/" 
               class="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 
                      px-6 py-3 rounded-xl font-bold transition shadow-xl">
                <span data-i18n="backToDashboard">← Retour au Dashboard</span>
            </a>
        </div>
        
        <div class="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden shadow-2xl">
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead class="bg-gray-900/50 border-b border-gray-700">
                        <tr>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyRequestId">ID</span>
                            </th>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyTitleCol">Titre</span>
                            </th>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyMedia">Type</span>
                            </th>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyUser">Utilisateur</span>
                            </th>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyDecision">Décision</span>
                            </th>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyReason">Raison</span>
                            </th>
                            <th class="px-6 py-4 text-center text-sm font-semibold text-gray-400">
                                <span data-i18n="historyConfidence">Confiance</span>
                            </th>
                            <th class="px-6 py-4 text-left text-sm font-semibold text-gray-400">
                                <span data-i18n="historyDate">Date</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html if rows_html else '<tr><td colspan="8" class="px-6 py-12 text-center text-gray-500"><span data-i18n="historyNoDecisions">Aucune décision enregistrée</span></td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="mt-6 text-center text-gray-500 text-sm">
            <p>
                Affichage des 50 dernières décisions • 
                <button onclick="location.reload()" class="text-blue-400 hover:text-blue-300 cursor-pointer">
                    🔄 Actualiser
                </button>
            </p>
        </div>
    </div>
    
    <script>
        // Auto-refresh toutes les 30 secondes
        setTimeout(() => location.reload(), 30000);
        
        // Update translations on load
        document.addEventListener('DOMContentLoaded', function() {{
            updatePageLanguage();
        }});
        
        console.log('✅ History page loaded (auto-refresh in 30s)');
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html)


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
async def health_check_html():
    """Health check page with language support"""
    html_content = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-i18n="healthTitle">État du Système</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .lang-selector {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 100;
            display: flex;
            gap: 8px;
            background: rgba(31, 41, 55, 0.95);
            backdrop-filter: blur(10px);
            padding: 8px;
            border-radius: 12px;
            border: 1px solid rgba(75, 85, 99, 0.5);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        .lang-btn {
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            background: transparent;
            color: #9CA3AF;
        }
        .lang-btn:hover {
            background: rgba(75, 85, 99, 0.5);
            color: #E5E7EB;
        }
        .lang-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
        }
        .lang-btn .flag {
            font-size: 18px;
            margin-right: 6px;
        }
    </style>
</head>
<body class="bg-gray-900 text-white font-sans antialiased">
    
    <div class="lang-selector">
        <button class="lang-btn active" data-lang="fr" onclick="setLanguage('fr')">
            <span class="flag">🇫🇷</span> FR
        </button>
        <button class="lang-btn" data-lang="en" onclick="setLanguage('en')">
            <span class="flag">🇬🇧</span> EN
        </button>
    </div>

    <div class="max-w-4xl mx-auto px-4 py-12">
        <div class="mb-8">
            <a href="/" class="text-blue-400 hover:text-blue-300 transition">
                <span data-i18n="backToDashboard">← Retour au Dashboard</span>
            </a>
        </div>
        
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 p-8 rounded-3xl border border-gray-700 shadow-2xl">
            <h1 class="text-4xl font-black mb-8 bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
                💚 <span data-i18n="healthTitle">État du Système</span>
            </h1>
            
            <div class="space-y-4">
                <div class="flex justify-between items-center p-4 bg-gray-700/50 rounded-xl">
                    <span class="font-semibold" data-i18n="healthStatus">Statut</span>
                    <span class="px-4 py-2 bg-emerald-500 text-white rounded-lg font-bold" data-i18n="healthOk">✅ Opérationnel</span>
                </div>
                
                <div class="flex justify-between items-center p-4 bg-gray-700/50 rounded-xl">
                    <span class="font-semibold" data-i18n="healthVersion">Version</span>
                    <span class="text-gray-300">v1.6.0</span>
                </div>
                
                <div class="flex justify-between items-center p-4 bg-gray-700/50 rounded-xl">
                    <span class="font-semibold" data-i18n="healthDatabase">Base de données</span>
                    <span class="text-emerald-400" data-i18n="healthConnected">✅ Connectée</span>
                </div>
                
                <div class="flex justify-between items-center p-4 bg-gray-700/50 rounded-xl">
                    <span class="font-semibold" data-i18n="healthOpenAI">OpenAI API</span>
                    <span class="text-emerald-400" data-i18n="healthConfigured">✅ Configurée</span>
                </div>
                
                <div class="flex justify-between items-center p-4 bg-gray-700/50 rounded-xl">
                    <span class="font-semibold" data-i18n="healthOverseerr">Overseerr</span>
                    <span class="text-emerald-400" data-i18n="healthConfigured">✅ Configurée</span>
                </div>
                
                <div class="flex justify-between items-center p-4 bg-gray-700/50 rounded-xl">
                    <span class="font-semibold" data-i18n="healthTMDB">TMDB API</span>
                    <span class="text-emerald-400" data-i18n="healthConfigured">✅ Configurée</span>
                </div>
            </div>
            
            <div class="mt-8 text-center">
                <a href="/" class="inline-block px-8 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 rounded-xl font-bold transition">
                    <span data-i18n="healthBackToDashboard">← Retour au Dashboard</span>
                </a>
            </div>
        </div>
    </div>
    
    <script src="/static/translations.js"></script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/review-dashboard", response_class=HTMLResponse)
async def review_dashboard_html():
    """Review dashboard page with language support"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, request_id, request_data, ai_decision, ai_reason, ai_confidence, created_at
        FROM pending_reviews
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    pending = cursor.fetchall()
    conn.close()
    
    cards_html = ""
    for row in pending:
        request_data = json.loads(row[2]) if row[2] else {}
        media = request_data.get('media', {})
        title = media.get('title') or media.get('name') or f"Request #{row[1]}"
        user = request_data.get('requestedBy', {}).get('displayName', 'Unknown')
        
        decision_color = {
            'APPROVED': 'emerald',
            'REJECTED': 'red',
            'NEEDS_REVIEW': 'yellow'
        }.get(row[3], 'gray')
        
        cards_html += f"""
        <div class="bg-gray-700/50 p-6 rounded-2xl border border-gray-600 hover:border-purple-500 transition">
            <div class="flex justify-between items-start mb-4">
                <div>
                    <h3 class="text-xl font-bold text-white mb-2">{title}</h3>
                    <p class="text-sm text-gray-400">
                        <span data-i18n="reviewRequestedBy">Demandé par</span>: {user}
                    </p>
                </div>
                <span class="px-3 py-1 bg-{decision_color}-500/20 text-{decision_color}-400 rounded-full text-sm">
                    {row[3]}
                </span>
            </div>
            
            <div class="space-y-2 mb-4">
                <div class="text-sm">
                    <span class="text-gray-400" data-i18n="reviewAIReason">Raison IA</span>:
                    <span class="text-gray-300">{row[4][:150]}...</span>
                </div>
                <div class="text-sm">
                    <span class="text-gray-400" data-i18n="reviewAIConfidence">Confiance</span>:
                    <span class="text-white font-bold">{int(row[5]*100)}%</span>
                </div>
            </div>
            
            <div class="flex gap-3">
                <button onclick="processReview({row[0]}, 'approve')" 
                        class="flex-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg font-semibold transition">
                    <span data-i18n="reviewApprove">✅ Approuver</span>
                </button>
                <button onclick="processReview({row[0]}, 'reject')" 
                        class="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-semibold transition">
                    <span data-i18n="reviewReject">❌ Rejeter</span>
                </button>
            </div>
        </div>
        """
    
    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-i18n="reviewTitle">Tableau de Révision</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .lang-selector {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 100;
            display: flex;
            gap: 8px;
            background: rgba(31, 41, 55, 0.95);
            backdrop-filter: blur(10px);
            padding: 8px;
            border-radius: 12px;
            border: 1px solid rgba(75, 85, 99, 0.5);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        .lang-btn {{
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            background: transparent;
            color: #9CA3AF;
        }}
        .lang-btn:hover {{
            background: rgba(75, 85, 99, 0.5);
            color: #E5E7EB;
        }}
        .lang-btn.active {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
        }}
        .lang-btn .flag {{
            font-size: 18px;
            margin-right: 6px;
        }}
    </style>
</head>
<body class="bg-gray-900 text-white font-sans antialiased">
    
    <div class="lang-selector">
        <button class="lang-btn active" data-lang="fr" onclick="setLanguage('fr')">
            <span class="flag">🇫🇷</span> FR
        </button>
        <button class="lang-btn" data-lang="en" onclick="setLanguage('en')">
            <span class="flag">🇬🇧</span> EN
        </button>
    </div>

    <div class="max-w-7xl mx-auto px-4 py-12">
        <div class="mb-8">
            <a href="/" class="text-blue-400 hover:text-blue-300 transition">
                <span data-i18n="backToDashboard">← Retour au Dashboard</span>
            </a>
        </div>
        
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 p-8 rounded-3xl border border-gray-700 shadow-2xl">
            <div class="flex justify-between items-center mb-8">
                <h1 class="text-4xl font-black bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent">
                    🧑‍⚖️ <span data-i18n="reviewTitle">Tableau de Révision</span>
                </h1>
                <button onclick="location.reload()" class="px-6 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg font-semibold transition">
                    🔄 <span data-i18n="reportRefresh">Actualiser</span>
                </button>
            </div>
            
            <h2 class="text-2xl font-bold mb-6">
                <span data-i18n="reviewPending">Révisions en Attente</span> ({len(pending)})
            </h2>
            
            <div id="reviews-container" class="grid grid-cols-1 md:grid-cols-2 gap-6">
                {cards_html if cards_html else '<div class="col-span-2 text-center py-12 text-gray-400"><p data-i18n="reviewNoPending">✅ Aucune révision en attente</p></div>'}
            </div>
        </div>
    </div>
    
    <script src="/static/translations.js"></script>
    <script>
        async function processReview(reviewId, action) {{
            try {{
                const response = await fetch(`/staff/review/${{reviewId}}/${{action}}`, {{
                    method: 'POST'
                }});
                
                if (response.ok) {{
                    alert(t('reviewSuccess'));
                    location.reload();
                }} else {{
                    alert(t('reviewError'));
                }}
            }} catch (error) {{
                alert(t('reviewError') + ': ' + error.message);
            }}
        }}
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/staff/reviews")
async def get_pending_reviews():
    """Get pending review requests"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Pour accéder par nom de colonne
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id,
            request_id,
            title,
            username,
            media_type,
            request_data,
            ai_reason,
            ai_confidence,
            created_at
        FROM pending_reviews 
        WHERE status = 'pending'
        ORDER BY created_at DESC 
        LIMIT 50
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    reviews = []
    for row in rows:
        try:
            request_data = json.loads(row['request_data']) if row['request_data'] else {}
        except:
            request_data = {}
        
        reviews.append({
            'id': row['id'],              # ID pour approve/reject
            'request_id': row['request_id'],
            'title': row['title'] or 'Unknown',
            'username': row['username'] or 'Unknown',
            'media_type': row['media_type'] or 'unknown',
            'request_data': request_data,
            'ai_reason': row['ai_reason'],
            'ai_confidence': row['ai_confidence'],
            'created_at': row['created_at']
        })
    
    return JSONResponse(content={'reviews': reviews})


@app.post("/staff/review/{review_id}/approve")  # 🆕 Changé le path
async def approve_review(review_id: int, request: Request = None):
    """Staff approve a NEEDS_REVIEW request"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 🆕 Utilise review_id (clé primaire) au lieu de request_id
        cursor.execute("""
            SELECT 
                id, request_id, title, username, media_type, 
                request_data, ai_decision
            FROM pending_reviews 
            WHERE id = ? AND status = 'pending'
        """, (review_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return JSONResponse(
                content={'success': False, 'error': 'Review not found or already processed'},
                status_code=404
            )
        
        request_id = row['request_id']
        title = row['title'] or f"Request #{request_id}"
        username = row['username'] or 'Unknown'
        media_type = row['media_type'] or 'unknown'
        
        # Parse request_data
        try:
            request_data = json.loads(row['request_data']) if row['request_data'] else {}
        except:
            request_data = {}
        
        ai_decision = row['ai_decision']
        
        # 🆕 Record human feedback for ML
        if moderator:
            try:
                moderator.record_human_decision(
                    request_id=request_id,
                    request_data=request_data,
                    ai_decision=ai_decision,
                    human_decision='APPROVED',
                    human_reason='Staff approved',
                    staff_username='admin'
                )
            except Exception as e:
                print(f"⚠️  Failed to record ML feedback: {e}")
        
        # Approve in Overseerr
        approve_result = approve_overseerr_request(request_id)
        
        if not approve_result:
            conn.close()
            return JSONResponse(
                content={'success': False, 'error': 'Failed to approve in Overseerr'},
                status_code=500
            )
        
        # Update pending_reviews status
        cursor.execute("""
            UPDATE pending_reviews 
            SET status = 'approved' 
            WHERE id = ?
        """, (review_id,))
        
        # 🆕 Save to decisions with title/username
        cursor.execute("""
            INSERT INTO decisions 
            (request_id, title, username, media_type, decision, reason, 
             confidence, rule_matched, request_data, timestamp)
            VALUES (?, ?, ?, ?, 'APPROVED', 'Staff approved', 1.0, 
                    'manual_staff', ?, ?)
        """, (
            request_id,
            title,
            username,
            media_type,
            json.dumps(request_data),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Manual approval: {title} by {username}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Approved: {title}',
            'request_id': request_id
        })
        
    except Exception as e:
        print(f"❌ Error approving review: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={'success': False, 'error': str(e)},
            status_code=500
        )


@app.post("/staff/review/{review_id}/reject")  # 🆕 Changé le path
async def reject_review(review_id: int, request: Request = None):
    """Staff reject a NEEDS_REVIEW request"""
    try:
        # Parse body (optionnel)
        body = {}
        if request:
            try:
                body = await request.json()
            except:
                pass
        
        reason = body.get('reason', 'Staff rejected')
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 🆕 Utilise review_id (clé primaire)
        cursor.execute("""
            SELECT 
                id, request_id, title, username, media_type,
                request_data, ai_decision
            FROM pending_reviews 
            WHERE id = ? AND status = 'pending'
        """, (review_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return JSONResponse(
                content={'success': False, 'error': 'Review not found or already processed'},
                status_code=404
            )
        
        request_id = row['request_id']
        title = row['title'] or f"Request #{request_id}"
        username = row['username'] or 'Unknown'
        media_type = row['media_type'] or 'unknown'
        
        # Parse request_data
        try:
            request_data = json.loads(row['request_data']) if row['request_data'] else {}
        except:
            request_data = {}
        
        ai_decision = row['ai_decision']
        
        # 🆕 Record human feedback for ML
        if moderator:
            try:
                moderator.record_human_decision(
                    request_id=request_id,
                    request_data=request_data,
                    ai_decision=ai_decision,
                    human_decision='REJECTED',
                    human_reason=reason,
                    staff_username='admin'
                )
            except Exception as e:
                print(f"⚠️  Failed to record ML feedback: {e}")
        
        # Decline in Overseerr
        decline_result = decline_overseerr_request(request_id)
        
        if not decline_result:
            conn.close()
            return JSONResponse(
                content={'success': False, 'error': 'Failed to decline in Overseerr'},
                status_code=500
            )
        
        # Update pending_reviews status
        cursor.execute("""
            UPDATE pending_reviews 
            SET status = 'rejected' 
            WHERE id = ?
        """, (review_id,))
        
        # 🆕 Save to decisions with title/username
        cursor.execute("""
            INSERT INTO decisions 
            (request_id, title, username, media_type, decision, reason, 
             confidence, rule_matched, request_data, timestamp)
            VALUES (?, ?, ?, ?, 'REJECTED', ?, 1.0, 
                    'manual_staff', ?, ?)
        """, (
            request_id,
            title,
            username,
            media_type,
            reason,
            json.dumps(request_data),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        print(f"❌ Manual rejection: {title} by {username}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Rejected: {title}',
            'request_id': request_id
        })
        
    except Exception as e:
        print(f"❌ Error rejecting review: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={'success': False, 'error': str(e)},
            status_code=500
        )

@app.get("/admin/cleanup-duplicates")
async def cleanup_duplicates():
    """Remove duplicate decisions (keep only the first one for each request_id)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Trouver les request_id avec doublons
        cursor.execute("""
            SELECT request_id, COUNT(*) as count
            FROM decisions
            GROUP BY request_id
            HAVING count > 1
            ORDER BY count DESC
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            conn.close()
            return {
                "duplicates_found": 0,
                "entries_removed": 0,
                "message": "No duplicates found ✅"
            }
        
        total_removed = 0
        
        for request_id, count in duplicates:
            # Garder seulement le premier (plus ancien timestamp)
            cursor.execute("""
                DELETE FROM decisions
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM decisions
                    WHERE request_id = ?
                ) AND request_id = ?
            """, (request_id, request_id))
            
            removed = cursor.rowcount
            total_removed += removed
            
            print(f"🗑️  Request #{request_id}: Removed {removed} duplicate(s) (kept 1/{count})")
        
        conn.commit()
        conn.close()
        
        return {
            "duplicates_found": len(duplicates),
            "entries_removed": total_removed,
            "message": f"Cleaned up {total_removed} duplicate entries from {len(duplicates)} requests ✅"
        }
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "message": "Cleanup failed ❌"
        }

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


@app.get("/staff/openai-stats", response_class=HTMLResponse)
async def openai_stats_html():
    """OpenAI statistics page with language support"""
    
    # Récupère les stats (adapte selon ton implémentation)
    if not openai_moderator:
        stats = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "by_model": {},
            "recent_calls": []
        }
    else:
        stats = openai_moderator.get_usage_stats() if hasattr(openai_moderator, 'get_usage_stats') else {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "by_model": {},
            "recent_calls": []
        }
    
    # Calculs
    total_calls = stats.get("total_calls", 0)
    total_tokens = stats.get("total_tokens", 0)
    total_cost = stats.get("total_cost", 0.0)
    avg_cost = (total_cost / total_calls) if total_calls > 0 else 0
    avg_tokens = (total_tokens / total_calls) if total_calls > 0 else 0
    
    # By Model table
    by_model_html = ""
    for model, data in stats.get("by_model", {}).items():
        by_model_html += f"""
        <tr class="border-b border-gray-700 hover:bg-gray-700/30 transition">
            <td class="px-4 py-3 font-mono text-sm">{model}</td>
            <td class="px-4 py-3 text-center">{data.get('calls', 0)}</td>
            <td class="px-4 py-3 text-center">{data.get('tokens', 0):,}</td>
            <td class="px-4 py-3 text-center font-semibold text-emerald-400">${data.get('cost', 0):.4f}</td>
        </tr>
        """
    
    # Recent calls table
    recent_html = ""
    for call in stats.get("recent_calls", [])[:10]:
        recent_html += f"""
        <tr class="border-b border-gray-700 hover:bg-gray-700/30 transition">
            <td class="px-4 py-3 text-sm text-gray-400">{call.get('timestamp', 'N/A')}</td>
            <td class="px-4 py-3 font-mono text-xs">{call.get('model', 'N/A')}</td>
            <td class="px-4 py-3 text-center">{call.get('prompt_tokens', 0)}</td>
            <td class="px-4 py-3 text-center">{call.get('completion_tokens', 0)}</td>
            <td class="px-4 py-3 text-center font-semibold">{call.get('total_tokens', 0)}</td>
            <td class="px-4 py-3 text-center text-emerald-400">${call.get('cost', 0):.6f}</td>
        </tr>
        """
    
    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-i18n="openaiStatsTitle">Statistiques OpenAI</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .lang-selector {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 100;
            display: flex;
            gap: 8px;
            background: rgba(31, 41, 55, 0.95);
            backdrop-filter: blur(10px);
            padding: 8px;
            border-radius: 12px;
            border: 1px solid rgba(75, 85, 99, 0.5);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        .lang-btn {{
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
            background: transparent;
            color: #9CA3AF;
        }}
        .lang-btn:hover {{
            background: rgba(75, 85, 99, 0.5);
            color: #E5E7EB;
        }}
        .lang-btn.active {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: rgba(102, 126, 234, 0.5);
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
        }}
        .lang-btn .flag {{
            font-size: 18px;
            margin-right: 6px;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .pulse {{
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
    </style>
</head>
<body class="bg-gray-900 text-white font-sans antialiased">
    
    <div class="lang-selector">
        <button class="lang-btn active" data-lang="fr" onclick="setLanguage('fr')">
            <span class="flag">🇫🇷</span> FR
        </button>
        <button class="lang-btn" data-lang="en" onclick="setLanguage('en')">
            <span class="flag">🇬🇧</span> EN
        </button>
    </div>

    <div class="max-w-7xl mx-auto px-4 py-12">
        <div class="mb-8">
            <a href="/" class="text-blue-400 hover:text-blue-300 transition">
                <span data-i18n="backToDashboard">← Retour au Dashboard</span>
            </a>
        </div>
        
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 p-8 rounded-3xl border border-gray-700 shadow-2xl">
            <div class="flex justify-between items-center mb-8">
                <h1 class="text-4xl font-black bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">
                    🤖 <span data-i18n="openaiStatsTitle">Statistiques OpenAI</span>
                </h1>
                <button onclick="location.reload()" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg font-semibold transition">
                    🔄 <span data-i18n="reportRefresh">Actualiser</span>
                </button>
            </div>
            
            <!-- Global Stats -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
                <div class="bg-gradient-to-br from-blue-900 to-indigo-900 p-6 rounded-2xl border border-blue-700">
                    <div class="text-blue-300 mb-2 text-sm font-semibold" data-i18n="openaiTotalCalls">Appels Totaux</div>
                    <div class="text-4xl font-black text-white">{total_calls:,}</div>
                </div>
                <div class="bg-gradient-to-br from-purple-900 to-pink-900 p-6 rounded-2xl border border-purple-700">
                    <div class="text-purple-300 mb-2 text-sm font-semibold" data-i18n="openaiTotalTokens">Tokens Totaux</div>
                    <div class="text-4xl font-black text-white">{total_tokens:,}</div>
                </div>
                <div class="bg-gradient-to-br from-emerald-900 to-teal-900 p-6 rounded-2xl border border-emerald-700">
                    <div class="text-emerald-300 mb-2 text-sm font-semibold" data-i18n="openaiTotalCost">Coût Total</div>
                    <div class="text-4xl font-black text-emerald-300">${total_cost:.4f}</div>
                </div>
                <div class="bg-gradient-to-br from-yellow-900 to-orange-900 p-6 rounded-2xl border border-yellow-700">
                    <div class="text-yellow-300 mb-2 text-sm font-semibold" data-i18n="openaiAverageCost">Coût Moyen</div>
                    <div class="text-4xl font-black text-yellow-300">${avg_cost:.6f}</div>
                </div>
            </div>
            
            <!-- By Model Table -->
            {'<div class="mb-12"><h2 class="text-2xl font-bold mb-6"><span data-i18n="openaiByModel">Par Modèle</span></h2><div class="overflow-x-auto bg-gray-800/50 rounded-2xl border border-gray-700"><table class="w-full"><thead class="bg-gray-700/50"><tr><th class="px-4 py-3 text-left" data-i18n="openaiModel">Modèle</th><th class="px-4 py-3 text-center" data-i18n="openaiCalls">Appels</th><th class="px-4 py-3 text-center" data-i18n="openaiTokensUsed">Tokens Utilisés</th><th class="px-4 py-3 text-center" data-i18n="openaiCost">Coût</th></tr></thead><tbody>' + by_model_html + '</tbody></table></div></div>' if by_model_html else '<div class="mb-12 text-center py-8 text-gray-400"><p data-i18n="openaiNoStats">Aucune statistique par modèle disponible</p></div>'}
            
            <!-- Recent Calls Table -->
            {'<div><h2 class="text-2xl font-bold mb-6"><span data-i18n="openaiRecentCalls">Appels Récents</span></h2><div class="overflow-x-auto bg-gray-800/50 rounded-2xl border border-gray-700"><table class="w-full"><thead class="bg-gray-700/50"><tr><th class="px-4 py-3 text-left" data-i18n="openaiTimestamp">Horodatage</th><th class="px-4 py-3 text-left" data-i18n="openaiModel">Modèle</th><th class="px-4 py-3 text-center" data-i18n="openaiPromptTokens">Prompt</th><th class="px-4 py-3 text-center" data-i18n="openaiCompletionTokens">Complétion</th><th class="px-4 py-3 text-center">Total</th><th class="px-4 py-3 text-center" data-i18n="openaiCost">Coût</th></tr></thead><tbody>' + recent_html + '</tbody></table></div></div>' if recent_html else '<div class="text-center py-8 text-gray-400"><p data-i18n="openaiNoStats">Aucun appel récent</p></div>'}
            
            <!-- Info Box -->
            <div class="mt-8 p-6 bg-blue-900/20 border border-blue-700 rounded-2xl">
                <div class="flex items-start gap-3">
                    <span class="text-3xl">💡</span>
                    <div class="flex-1">
                        <h3 class="font-bold text-blue-300 mb-2">À propos des coûts</h3>
                        <p class="text-sm text-gray-300">
                            Les coûts sont calculés selon les tarifs OpenAI actuels. 
                            Les tokens de prompt et de complétion ont des prix différents selon le modèle utilisé.
                        </p>
                        <div class="mt-3 text-xs text-gray-400">
                            <strong>GPT-4o-mini:</strong> $0.150 / 1M tokens input • $0.600 / 1M tokens output<br>
                            <strong>GPT-4o:</strong> $2.50 / 1M tokens input • $10.00 / 1M tokens output
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="/static/translations.js"></script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

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


@app.on_event("shutdown")
async def shutdown_event():
    """Log graceful shutdown; scheduling is handled by cron."""
    print("\nPlexStaffAI stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
