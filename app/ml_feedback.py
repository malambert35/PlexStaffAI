# ml_feedback.py - Machine Learning Feedback Loop System

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json

class FeedbackDatabase:
    """Base de données pour stocker les décisions humaines et entraîner l'IA"""
    
    def __init__(self, db_path: str = "/config/feedback.db"):
        self.db_path = Path(db_path)
        self.init_database()
    
    def init_database(self):
        """Crée les tables si elles n'existent pas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des feedbacks humains
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS human_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                ai_decision TEXT,
                ai_confidence REAL,
                ai_reason TEXT,
                human_decision TEXT NOT NULL,
                human_reason TEXT,
                staff_username TEXT,
                request_data JSON,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                learning_applied BOOLEAN DEFAULT 0
            )
        """)
        
        # Table des patterns appris
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                pattern_value TEXT,
                decision TEXT,
                confidence REAL,
                occurrences INTEGER DEFAULT 1,
                success_rate REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME
            )
        """)
        
        # Table des stats utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                account_created DATETIME,
                total_requests INTEGER DEFAULT 0,
                approved_requests INTEGER DEFAULT 0,
                rejected_requests INTEGER DEFAULT 0,
                trust_level TEXT DEFAULT 'new',
                last_request DATETIME
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_feedback(self, feedback_data: Dict[str, Any]) -> int:
        """Enregistre une décision humaine pour apprentissage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO human_feedback 
            (request_id, ai_decision, ai_confidence, ai_reason, 
             human_decision, human_reason, staff_username, request_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_data['request_id'],
            feedback_data.get('ai_decision'),
            feedback_data.get('ai_confidence'),
            feedback_data.get('ai_reason'),
            feedback_data['human_decision'],
            feedback_data.get('human_reason'),
            feedback_data.get('staff_username'),
            json.dumps(feedback_data.get('request_data', {}))
        ))
        
        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Déclencher apprentissage si threshold atteint
        self.trigger_learning_if_needed()
        
        return feedback_id
    
    def get_feedback_count(self, unlearned_only: bool = True) -> int:
        """Compte les feedbacks non encore appris"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if unlearned_only:
            cursor.execute("SELECT COUNT(*) FROM human_feedback WHERE learning_applied = 0")
        else:
            cursor.execute("SELECT COUNT(*) FROM human_feedback")
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def trigger_learning_if_needed(self):
        """Déclenche apprentissage si threshold de feedbacks atteint"""
        unlearned_count = self.get_feedback_count(unlearned_only=True)
        threshold = 100
        
        if unlearned_count >= threshold:
            print(f"🧠 Learning threshold reached ({unlearned_count} feedbacks). Training patterns...")
            self.learn_from_feedback()
    
    def learn_from_feedback(self):
        """Analyse les feedbacks et crée des patterns appris"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, request_data, human_decision 
            FROM human_feedback 
            WHERE learning_applied = 0
        """)
        
        feedbacks = cursor.fetchall()
        patterns_learned = 0
        
        for feedback_id, request_data_json, decision in feedbacks:
            request_data = json.loads(request_data_json)
            
            # Pattern: Genre
            genres = request_data.get('genres', [])
            for genre in genres:
                self.upsert_pattern('genre', genre, decision, conn)
                patterns_learned += 1
            
            # Marquer feedback comme appris
            cursor.execute("""
                UPDATE human_feedback 
                SET learning_applied = 1 
                WHERE id = ?
            """, (feedback_id,))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Learned {patterns_learned} patterns from {len(feedbacks)} feedbacks")
    
    def upsert_pattern(self, pattern_type: str, pattern_value: str, decision: str, conn):
        """Insère ou met à jour un pattern appris"""
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, occurrences FROM learned_patterns 
            WHERE pattern_type = ? AND pattern_value = ? AND decision = ?
        """, (pattern_type, pattern_value, decision))
        
        existing = cursor.fetchone()
        
        if existing:
            pattern_id, occurrences = existing
            cursor.execute("""
                UPDATE learned_patterns 
                SET occurrences = ?, last_used = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (occurrences + 1, pattern_id))
        else:
            cursor.execute("""
                INSERT INTO learned_patterns 
                (pattern_type, pattern_value, decision, confidence)
                VALUES (?, ?, ?, ?)
            """, (pattern_type, pattern_value, decision, 0.7))
    
    def get_learned_decision(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Récupère une décision basée sur patterns appris"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        matched_patterns = []
        
        # Check genres
        genres = request_data.get('genres', [])
        for genre in genres:
            cursor.execute("""
                SELECT decision, confidence, occurrences 
                FROM learned_patterns 
                WHERE pattern_type = 'genre' AND pattern_value = ?
                ORDER BY occurrences DESC LIMIT 1
            """, (genre,))
            match = cursor.fetchone()
            if match:
                matched_patterns.append({
                    'type': 'genre',
                    'decision': match[0],
                    'confidence': match[1],
                    'occurrences': match[2]
                })
        
        conn.close()
        
        if not matched_patterns:
            return None
        
        # Sélectionner le pattern avec le plus d'occurrences
        best_match = max(matched_patterns, key=lambda x: x['occurrences'])
        
        return {
            'decision': best_match['decision'],
            'confidence': min(0.85, 0.6 + (best_match['occurrences'] * 0.05)),
            'reason': f"Learned from {best_match['occurrences']} similar past decisions ({best_match['type']})",
            'source': 'machine_learning'
        }
    
    def update_user_stats(self, user_id: str, username: str, decision: str):
        """Met à jour les stats utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT total_requests FROM user_stats WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE user_stats 
                SET total_requests = total_requests + 1,
                    approved_requests = approved_requests + ?,
                    rejected_requests = rejected_requests + ?,
                    last_request = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                1 if decision == 'APPROVED' else 0,
                1 if decision == 'REJECTED' else 0,
                user_id
            ))
        else:
            cursor.execute("""
                INSERT INTO user_stats 
                (user_id, username, account_created, total_requests, 
                 approved_requests, rejected_requests, last_request)
                VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?, ?, CURRENT_TIMESTAMP)
            """, (
                user_id,
                username,
                1 if decision == 'APPROVED' else 0,
                1 if decision == 'REJECTED' else 0
            ))
        
        conn.commit()
        conn.close()


# Intégration dans main.py
from app.config_loader import ConfigManager, SmartModerator

class EnhancedModerator:
    """Modérateur avec ML feedback integration"""
    
    def __init__(self, config_manager: ConfigManager, feedback_db: FeedbackDatabase):
        self.config = config_manager
        self.feedback = feedback_db
        self.smart_moderator = SmartModerator(config_manager)
    
    def moderate_with_learning(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Modération avec apprentissage ML"""
        
        # 1. Check learned patterns first
        ml_enabled = self.config.get('machine_learning.enabled', True)
        if ml_enabled:
            learned_decision = self.feedback.get_learned_decision(request_data)
            if learned_decision and learned_decision['confidence'] > 0.75:
                return learned_decision
        
        # 2. Apply config rules
        decision = self.smart_moderator.moderate(request_data)
        
        return {
            'decision': decision.decision,
            'reason': decision.reason,
            'confidence': decision.confidence,
            'rule_matched': decision.rule_matched,
            'source': 'config_rules'
        }
    
    def record_human_decision(self, request_id: int, request_data: Dict[str, Any],
                             ai_decision: str, human_decision: str, 
                             human_reason: str, staff_username: str):
        """Enregistre décision humaine pour apprentissage"""
        
        feedback_data = {
            'request_id': request_id,
            'ai_decision': ai_decision,
            'human_decision': human_decision,
            'human_reason': human_reason,
            'staff_username': staff_username,
            'request_data': request_data
        }
        
        feedback_id = self.feedback.add_feedback(feedback_data)
        
        # Update user stats
        user_id = str(request_data.get('user_id', 'unknown'))
        username = request_data.get('requested_by', 'unknown')
        self.feedback.update_user_stats(user_id, username, human_decision)
        
        return feedback_id
