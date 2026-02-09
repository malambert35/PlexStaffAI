from typing import Dict, List
from app.config_loader import ConfigManager, ModerationDecision

class RulesValidator:
    """Validates and potentially overrides AI decisions based on strict rules"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def validate(self, ai_result: Dict, request_data: Dict) -> Dict:
        """
        Valide la décision AI avec les règles configurées
        
        Returns:
            {
                'final_decision': str,
                'final_confidence': float,
                'final_reason': str,
                'rule_override': bool,
                'override_reason': str,
                'rules_matched': List[str],
                'confidence_adjustments': List[Dict]
            }
        """
        
        ai_decision = ai_result['decision']
        ai_confidence = ai_result['confidence']
        ai_reason = ai_result['reason']
        
        # Extract data
        rating = request_data.get('rating', 0)
        popularity = request_data.get('popularity', 0)
        genres = request_data.get('genres', [])
        episodes = request_data.get('episode_count', 0)
        seasons = request_data.get('season_count', 0)
        user_age_days = request_data.get('user_age_days', 0)
        
        # Résultats
        final_decision = ai_decision
        final_confidence = ai_confidence
        final_reason = ai_reason
        rule_override = False
        override_reason = ""
        rules_matched = []
        confidence_adjustments = []
        
        print(f"\n🎯 {'='*60}")
        print(f"🎯 RULES VALIDATION LAYER")
        print(f"🎯 {'='*60}")
        print(f"🤖 AI Initial: {ai_decision} ({ai_confidence:.1%})")
        
        # ✅ STRICT AUTO-APPROVE RULES (Override AI if necessary)
        auto_approve = self.config.get('auto_approve', {})
        
        # Rule: Excellent rating
        if rating >= auto_approve.get('rating_above', 999):
            rules_matched.append('auto_approve.rating_above')
            if ai_decision != 'APPROVED':
                rule_override = True
                final_decision = 'APPROVED'
                final_confidence = 0.95
                override_reason = f"OVERRIDE: Excellent rating ({rating}/10) triggers auto-approve"
                print(f"⚠️  {override_reason}")
            else:
                confidence_adjustments.append({
                    'rule': 'rating_above',
                    'adjustment': +0.1,
                    'reason': f'High rating ({rating}) supports AI decision'
                })
                final_confidence = min(1.0, final_confidence + 0.1)
                print(f"✅ Rule rating_above: Supports AI decision (+10% confidence)")
        
        # Rule: Genre whitelist
        genre_whitelist = auto_approve.get('genres', [])
        if any(g in genres for g in genre_whitelist):
            matched_genres = [g for g in genres if g in genre_whitelist]
            rules_matched.append('auto_approve.genres')
            if ai_decision != 'APPROVED':
                rule_override = True
                final_decision = 'APPROVED'
                final_confidence = 0.90
                override_reason = f"OVERRIDE: Genre {matched_genres} is whitelisted"
                print(f"⚠️  {override_reason}")
            else:
                confidence_adjustments.append({
                    'rule': 'whitelisted_genre',
                    'adjustment': +0.05,
                    'reason': f'Preferred genre: {matched_genres}'
                })
                final_confidence = min(1.0, final_confidence + 0.05)
                print(f"✅ Rule genres: Supports AI decision (+5% confidence)")
        
        # ❌ STRICT AUTO-REJECT RULES
        auto_reject = self.config.get('auto_reject', {})
        
        # Rule: Very low rating
        if rating > 0 and rating <= auto_reject.get('rating_below', 0):
            rules_matched.append('auto_reject.rating_below')
            if ai_decision != 'REJECTED':
                rule_override = True
                final_decision = 'REJECTED'
                final_confidence = 0.95
                override_reason = f"OVERRIDE: Low rating ({rating}/10) triggers auto-reject"
                print(f"⚠️  {override_reason}")
            else:
                confidence_adjustments.append({
                    'rule': 'rating_below',
                    'adjustment': +0.1,
                    'reason': f'Very low rating ({rating}) supports rejection'
                })
                final_confidence = min(1.0, final_confidence + 0.1)
                print(f"✅ Rule rating_below: Supports AI decision (+10% confidence)")
        
        # Rule: Blacklisted genres
        genre_blacklist = auto_reject.get('genres', [])
        if any(g in genres for g in genre_blacklist):
            matched_genres = [g for g in genres if g in genre_blacklist]
            rules_matched.append('auto_reject.genres')
            if ai_decision != 'REJECTED':
                rule_override = True
                final_decision = 'REJECTED'
                final_confidence = 0.95
                override_reason = f"OVERRIDE: Genre {matched_genres} is blacklisted"
                print(f"⚠️  {override_reason}")
            else:
                confidence_adjustments.append({
                    'rule': 'blacklisted_genre',
                    'adjustment': +0.1,
                    'reason': f'Blacklisted genre: {matched_genres}'
                })
                final_confidence = min(1.0, final_confidence + 0.1)
                print(f"✅ Rule genres: Supports AI decision (+10% confidence)")
        
        # ⚠️ NEEDS_REVIEW TRIGGERS
        needs_review = self.config.get('needs_review', {})
        
        # Rule: Very long series
        if episodes > needs_review.get('episode_count_above', 999):
            rules_matched.append('needs_review.episode_count_above')
            if ai_decision == 'APPROVED' and ai_confidence < 0.90:
                # Lower confidence, might need human review
                confidence_adjustments.append({
                    'rule': 'long_series',
                    'adjustment': -0.15,
                    'reason': f'Very long series ({episodes} eps) needs caution'
                })
                final_confidence = max(0.5, final_confidence - 0.15)
                print(f"⚠️  Rule episode_count: Long series reduces confidence (-15%)")
                
                if final_confidence < 0.75:
                    final_decision = 'NEEDS_REVIEW'
                    override_reason = "AI approved but long series + low confidence → human review"
                    rule_override = True
                    print(f"⚠️  OVERRIDE: {override_reason}")
        
        # Rule: New user with obscure content
        if user_age_days < needs_review.get('new_user_days', 999):
            if popularity < needs_review.get('obscure_popularity_threshold', 0):
                rules_matched.append('needs_review.new_user_obscure')
                if ai_decision == 'APPROVED' and ai_confidence < 0.85:
                    confidence_adjustments.append({
                        'rule': 'new_user_risk',
                        'adjustment': -0.10,
                        'reason': 'New user + obscure content'
                    })
                    final_confidence = max(0.5, final_confidence - 0.10)
                    print(f"⚠️  Rule new_user: Reduces confidence (-10%)")
                    
                    if final_confidence < 0.75:
                        final_decision = 'NEEDS_REVIEW'
                        override_reason = "New user + obscure content → human review"
                        rule_override = True
                        print(f"⚠️  OVERRIDE: {override_reason}")
        
        # Summary
        print(f"\n🎯 Validation Summary:")
        print(f"   Rules Matched: {len(rules_matched)}")
        print(f"   Confidence Adjustments: {len(confidence_adjustments)}")
        print(f"   Rule Override: {'YES' if rule_override else 'NO'}")
        print(f"🎯 Final: {final_decision} ({final_confidence:.1%})")
        print(f"🎯 {'='*60}\n")
        
        return {
            'final_decision': final_decision,
            'final_confidence': final_confidence,
            'final_reason': override_reason if rule_override else ai_reason,
            'ai_original_decision': ai_decision,
            'ai_original_confidence': ai_confidence,
            'rule_override': rule_override,
            'override_reason': override_reason,
            'rules_matched': rules_matched,
            'confidence_adjustments': confidence_adjustments
        }
