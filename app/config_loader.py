# config_loader.py - PlexStaffAI Configuration Management

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class ConfigManager:
    """Charge et gère les règles AI personnalisées depuis config.yaml"""
    
    def __init__(self, config_path: str = "/config/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Charge le fichier YAML avec fallback sur defaults"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                print(f"⚠️  Config not found at {self.config_path}, using defaults")
                return self.get_default_config()
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut si YAML absent"""
        return {
            'ai_rules': {
                'auto_approve': {
                    'rating_above': 7.5,
                    'awards': ['Oscar', 'Emmy', 'Golden Globe'],
                    'genres': ['Documentary', 'Biography']
                },
                'auto_reject': {
                    'rating_below': 4.0,
                    'genres': ['Adult', 'Erotic'],
                    'keywords': ['CAM', 'LEAK', 'SCREENER']
                },
                'needs_review': {
                    'episode_count_above': 100,
                    'season_count_above': 10
                },
                'user_trust_levels': {
                    'new_user_days': 30,
                    'trusted_requests_min': 50,
                    'veteran_requests_min': 100
                }
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Accède config avec dot notation: 'ai_rules.auto_approve.rating_above'"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default


class ModerationDecision:
    """Représente une décision de modération enrichie"""
    
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    
    def __init__(self, decision: str, reason: str, confidence: float = 1.0, 
                 rule_matched: Optional[str] = None):
        self.decision = decision
        self.reason = reason
        self.confidence = confidence
        self.rule_matched = rule_matched
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision': self.decision,
            'reason': self.reason,
            'confidence': self.confidence,
            'rule_matched': self.rule_matched,
            'timestamp': self.timestamp.isoformat()
        }


class SmartModerator:
    """Modérateur intelligent avec règles personnalisées"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def should_auto_approve(self, request_data: Dict[str, Any]) -> Optional[ModerationDecision]:
        """Vérifie si la request match des règles auto-approve"""
        rules = self.config.get('ai_rules.auto_approve', {})
        
        # Check rating
        rating = request_data.get('rating', 0)
        threshold = rules.get('rating_above', 7.5)
        if rating >= threshold:
            return ModerationDecision(
                ModerationDecision.APPROVED,
                f"High rating ({rating}/10) exceeds threshold {threshold}",
                confidence=0.95,
                rule_matched="auto_approve.rating_above"
            )
        
        # Check awards
        awards = request_data.get('awards', [])
        approved_awards = rules.get('awards', [])
        matched_awards = set(awards) & set(approved_awards)
        if matched_awards:
            return ModerationDecision(
                ModerationDecision.APPROVED,
                f"Award-winning content: {', '.join(matched_awards)}",
                confidence=0.98,
                rule_matched="auto_approve.awards"
            )
        
        # Check genres
        genres = request_data.get('genres', [])
        approved_genres = rules.get('genres', [])
        matched_genres = set(genres) & set(approved_genres)
        if matched_genres:
            return ModerationDecision(
                ModerationDecision.APPROVED,
                f"Approved genre: {', '.join(matched_genres)}",
                confidence=0.90,
                rule_matched="auto_approve.genres"
            )
        
        return None
    
    def should_auto_reject(self, request_data: Dict[str, Any]) -> Optional[ModerationDecision]:
        """Vérifie si la request match des règles auto-reject"""
        rules = self.config.get('ai_rules.auto_reject', {})
        
        # Check rating
        rating = request_data.get('rating', 10)
        threshold = rules.get('rating_below', 4.0)
        if rating < threshold and rating > 0:
            return ModerationDecision(
                ModerationDecision.REJECTED,
                f"Low rating ({rating}/10) below threshold {threshold}",
                confidence=0.92,
                rule_matched="auto_reject.rating_below"
            )
        
        # Check banned genres
        genres = request_data.get('genres', [])
        banned_genres = rules.get('genres', [])
        matched_banned = set(genres) & set(banned_genres)
        if matched_banned:
            return ModerationDecision(
                ModerationDecision.REJECTED,
                f"Banned genre: {', '.join(matched_banned)}",
                confidence=0.99,
                rule_matched="auto_reject.genres"
            )
        
        # Check banned keywords
        title = request_data.get('title', '').upper()
        keywords = rules.get('keywords', [])
        matched_keywords = [kw for kw in keywords if kw.upper() in title]
        if matched_keywords:
            return ModerationDecision(
                ModerationDecision.REJECTED,
                f"Banned keyword detected: {', '.join(matched_keywords)}",
                confidence=0.97,
                rule_matched="auto_reject.keywords"
            )
        
        return None
    
    def needs_human_review(self, request_data: Dict[str, Any]) -> Optional[ModerationDecision]:
        """Vérifie si la request nécessite révision humaine"""
        rules = self.config.get('ai_rules.needs_review', {})
        
        # Check episode count (séries longues)
        episode_count = request_data.get('episode_count', 0)
        episode_threshold = rules.get('episode_count_above', 100)
        if episode_count > episode_threshold:
            return ModerationDecision(
                ModerationDecision.NEEDS_REVIEW,
                f"Long series ({episode_count} episodes) requires human review for storage",
                confidence=0.85,
                rule_matched="needs_review.episode_count"
            )
        
        # Check season count
        season_count = request_data.get('season_count', 0)
        season_threshold = rules.get('season_count_above', 10)
        if season_count > season_threshold:
            return ModerationDecision(
                ModerationDecision.NEEDS_REVIEW,
                f"Long series ({season_count} seasons) requires human review",
                confidence=0.85,
                rule_matched="needs_review.season_count"
            )
        
        # Check new user + obscure content
        user_age_days = request_data.get('user_age_days', 999)
        popularity = request_data.get('popularity', 100)
        
        new_user_rules = rules.get('new_user_obscure_content', {})
        user_age_threshold = new_user_rules.get('user_age_days', 30)
        pop_threshold = new_user_rules.get('popularity_below', 20)
        
        if user_age_days < user_age_threshold and popularity < pop_threshold:
            return ModerationDecision(
                ModerationDecision.NEEDS_REVIEW,
                f"New user ({user_age_days}d) requesting obscure content (pop: {popularity})",
                confidence=0.70,
                rule_matched="needs_review.new_user_obscure"
            )
        
        return None
    
    def moderate(self, request_data: Dict[str, Any]) -> ModerationDecision:
        """Modération complète avec cascade de règles"""
        
        # 1. Check auto-reject (priorité max)
        reject_decision = self.should_auto_reject(request_data)
        if reject_decision:
            return reject_decision
        
        # 2. Check auto-approve
        approve_decision = self.should_auto_approve(request_data)
        if approve_decision:
            return approve_decision
        
        # 3. Check needs review
        review_decision = self.needs_human_review(request_data)
        if review_decision:
            return review_decision
        
        # 4. Fallback: Send to AI with low confidence
        return ModerationDecision(
            ModerationDecision.NEEDS_REVIEW,
            "No rule matched, requires AI + human verification",
            confidence=0.50,
            rule_matched="fallback"
        )
