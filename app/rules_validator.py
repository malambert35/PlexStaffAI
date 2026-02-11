from typing import Dict, List
from datetime import datetime
from app.config_loader import ConfigManager, ModerationDecision

class RulesValidator:
    """Validates and potentially overrides AI decisions based on strict rules"""

    # Mapping FR → EN pour normalisation des genres
    GENRE_MAPPING = {
        # Français → Anglais
        "Documentaire": "Documentary",
        "Action & Adventure": "Action",
        "Action & Aventure": "Action",
        "Science-Fiction": "Science Fiction",
        "Fantastique": "Fantasy",
        "Comédie": "Comedy",
        "Drame": "Drama",
        "Horreur": "Horror",
        "Thriller": "Thriller",
        "Romance": "Romance",
        "Crime": "Crime",
        "Mystère": "Mystery",
        "Animation": "Animation",
        "Familial": "Family",
        "Famille": "Family",
        "Guerre": "War",
        "Histoire": "History",
        "Western": "Western",
        "Aventure": "Adventure",
        "Historique": "History",
        "Biographie": "Biography",
        "Musique": "Music",
        "Musical": "Musical",
    }

    def __init__(self, config: ConfigManager):
        self.config = config

    def normalize_genres(self, genres: List[str]) -> List[str]:
        """
        Normalise les genres FR → EN pour comparaison uniforme

        Args:
            genres: Liste des genres (possiblement en français)

        Returns:
            Liste des genres normalisés en anglais
        """
        normalized = []
        for genre in genres:
            # Essayer de mapper FR → EN
            normalized_genre = self.GENRE_MAPPING.get(genre, genre)
            normalized.append(normalized_genre)
        return normalized

    def validate(self, ai_result: Dict, request_data: Dict) -> Dict:
        """
        Valide la décision AI avec les règles configurées

        IMPORTANT: Si appelé avec ai_result['decision'] == 'PENDING',
        on check seulement les règles STRICTES (auto-approve/reject)
        pour le pre-check (avant OpenAI)

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
        genres_raw = request_data.get('genres', [])
        episodes = request_data.get('episode_count', 0)
        seasons = request_data.get('season_count', 0)
        user_age_days = request_data.get('user_age_days', 0)
        year = request_data.get('year', '')

        # NORMALISER LES GENRES FR → EN
        genres = self.normalize_genres(genres_raw)
        if genres != genres_raw:
            print(f"🌍 Genre normalization: {genres_raw} → {genres}")

        # Résultats
        final_decision = ai_decision
        final_confidence = ai_confidence
        final_reason = ai_reason
        rule_override = False
        override_reason = ""
        rules_matched = []
        confidence_adjustments = []

        # 🆕 Mode PRE-CHECK (avant OpenAI) - seulement règles STRICTES
        is_precheck = (ai_decision == 'PENDING')

        if not is_precheck:
            print(f"\n🎯 {'='*60}")
            print(f"🎯 RULES VALIDATION LAYER")
            print(f"🎯 {'='*60}")
            print(f"🤖 AI Initial: {ai_decision} ({ai_confidence:.1%})")

        # 🆕 MANUAL REVIEW FOR UPCOMING RELEASES (CHECK AVANT TOUT)
        if year:
            try:
                year_int = int(year)
                current_year = datetime.now().year

                # Si film sort cette année ou l'année prochaine
                if current_year <= year_int <= current_year + 1:
                    # Et rating = 0 (pas encore sorti)
                    if rating == 0:
                        print(f"🎬 Upcoming release detected: {year_int} (no rating yet)")
                        rules_matched.append('upcoming_release')
                        rule_override = True
                        final_decision = 'NEEDS_REVIEW'
                        final_confidence = 0.80
                        override_reason = f'Upcoming release ({year_int}), no rating available yet - requires manual staff review'

                        # Return immédiatement (priorité absolue)
                        return {
                            'final_decision': final_decision,
                            'final_confidence': final_confidence,
                            'final_reason': override_reason,
                            'ai_original_decision': ai_decision,
                            'ai_original_confidence': ai_confidence,
                            'rule_override': True,
                            'override_reason': override_reason,
                            'rules_matched': rules_matched,
                            'confidence_adjustments': []
                        }
            except:
                pass

        # ✅ STRICT AUTO-APPROVE RULES
        auto_approve = self.config.get('auto_approve', {})

        # Rule: Excellent rating (STRICT)
        if rating >= auto_approve.get('rating_above', 999):
            rules_matched.append('auto_approve.rating_above')
            rule_override = True
            final_decision = 'APPROVED'
            final_confidence = 0.95
            override_reason = f"OVERRIDE: Excellent rating ({rating}/10) triggers auto-approve"
            print(f"⚠️  {override_reason}")

            # En mode pre-check, return immédiatement
            if is_precheck:
                return {
                    'final_decision': final_decision,
                    'final_confidence': final_confidence,
                    'final_reason': override_reason,
                    'ai_original_decision': ai_decision,
                    'ai_original_confidence': ai_confidence,
                    'rule_override': True,
                    'override_reason': override_reason,
                    'rules_matched': rules_matched,
                    'confidence_adjustments': []
                }

        # Rule: Genre whitelist (STRICT)
        genre_whitelist = auto_approve.get('genres', [])
        matched_approved_genres = [g for g in genres if g in genre_whitelist]

        if matched_approved_genres:
            rules_matched.append('auto_approve.genres')
            rule_override = True
            final_decision = 'APPROVED'
            final_confidence = 0.90
            override_reason = f"OVERRIDE: Genre {matched_approved_genres} is whitelisted (auto-approve)"
            print(f"⚠️  {override_reason}")

            # En mode pre-check, return immédiatement
            if is_precheck:
                return {
                    'final_decision': final_decision,
                    'final_confidence': final_confidence,
                    'final_reason': override_reason,
                    'ai_original_decision': ai_decision,
                    'ai_original_confidence': ai_confidence,
                    'rule_override': True,
                    'override_reason': override_reason,
                    'rules_matched': rules_matched,
                    'confidence_adjustments': []
                }

        # ❌ STRICT AUTO-REJECT RULES
        auto_reject = self.config.get('auto_reject', {})

        # Rule: Very low rating (STRICT)
        if rating > 0 and rating <= auto_reject.get('rating_below', 0):
            rules_matched.append('auto_reject.rating_below')
            rule_override = True
            final_decision = 'REJECTED'
            final_confidence = 0.95
            override_reason = f"OVERRIDE: Low rating ({rating}/10) triggers auto-reject"
            print(f"⚠️  {override_reason}")

            # En mode pre-check, return immédiatement
            if is_precheck:
                return {
                    'final_decision': final_decision,
                    'final_confidence': final_confidence,
                    'final_reason': override_reason,
                    'ai_original_decision': ai_decision,
                    'ai_original_confidence': ai_confidence,
                    'rule_override': True,
                    'override_reason': override_reason,
                    'rules_matched': rules_matched,
                    'confidence_adjustments': []
                }

        # Rule: Blacklisted genres (STRICT)
        genre_blacklist = auto_reject.get('genres', [])
        matched_blacklisted_genres = [g for g in genres if g in genre_blacklist]

        if matched_blacklisted_genres:
            rules_matched.append('auto_reject.genres')
            rule_override = True
            final_decision = 'REJECTED'
            final_confidence = 0.95
            override_reason = f"OVERRIDE: Genre {matched_blacklisted_genres} is blacklisted (auto-reject)"
            print(f"⚠️  {override_reason}")

            # En mode pre-check, return immédiatement
            if is_precheck:
                return {
                    'final_decision': final_decision,
                    'final_confidence': final_confidence,
                    'final_reason': override_reason,
                    'ai_original_decision': ai_decision,
                    'ai_original_confidence': ai_confidence,
                    'rule_override': True,
                    'override_reason': override_reason,
                    'rules_matched': rules_matched,
                    'confidence_adjustments': []
                }

        # 🆕 Si on est en pre-check et aucune règle stricte → pas d'override
        if is_precheck:
            return {
                'final_decision': 'PENDING',
                'final_confidence': 0.5,
                'final_reason': 'No strict rule matched',
                'ai_original_decision': ai_decision,
                'ai_original_confidence': ai_confidence,
                'rule_override': False,
                'override_reason': '',
                'rules_matched': [],
                'confidence_adjustments': []
            }

        # ========================================================
        # À PARTIR D'ICI : Seulement si AI a déjà analysé
        # (ajustements non-stricts)
        # ========================================================

        # Si rating excellent ET AI a approuvé → boost confiance
        if rating >= auto_approve.get('rating_above', 999) and ai_decision == 'APPROVED':
            if 'auto_approve.rating_above' not in rules_matched:
                rules_matched.append('auto_approve.rating_above')
            confidence_adjustments.append({
                'rule': 'rating_above',
                'adjustment': +0.1,
                'reason': f'High rating ({rating}) supports AI decision'
            })
            final_confidence = min(1.0, final_confidence + 0.1)
            print(f"✅ Rule rating_above: Supports AI decision (+10% confidence)")

        # Si genre whitelist ET AI a approuvé → boost confiance
        if matched_approved_genres and ai_decision == 'APPROVED':
            if 'auto_approve.genres' not in rules_matched:
                rules_matched.append('auto_approve.genres')
            confidence_adjustments.append({
                'rule': 'whitelisted_genre',
                'adjustment': +0.05,
                'reason': f'Preferred genre: {matched_approved_genres}'
            })
            final_confidence = min(1.0, final_confidence + 0.05)
            print(f"✅ Rule genres: Supports AI decision (+5% confidence)")

        # Si rating très bas ET AI a rejeté → boost confiance
        if rating > 0 and rating <= auto_reject.get('rating_below', 0) and ai_decision == 'REJECTED':
            if 'auto_reject.rating_below' not in rules_matched:
                rules_matched.append('auto_reject.rating_below')
            confidence_adjustments.append({
                'rule': 'rating_below',
                'adjustment': +0.1,
                'reason': f'Very low rating ({rating}) supports rejection'
            })
            final_confidence = min(1.0, final_confidence + 0.1)
            print(f"✅ Rule rating_below: Supports AI decision (+10% confidence)")

        # Si genre blacklist ET AI a rejeté → boost confiance
        if matched_blacklisted_genres and ai_decision == 'REJECTED':
            if 'auto_reject.genres' not in rules_matched:
                rules_matched.append('auto_reject.genres')
            confidence_adjustments.append({
                'rule': 'blacklisted_genre',
                'adjustment': +0.1,
                'reason': f'Blacklisted genre: {matched_blacklisted_genres}'
            })
            final_confidence = min(1.0, final_confidence + 0.1)
            print(f"✅ Rule genres: Supports AI decision (+10% confidence)")

        # ⚠️ NEEDS_REVIEW TRIGGERS (non-stricts)
        needs_review = self.config.get('needs_review', {})

        # Rule: Very long series
        if episodes > needs_review.get('episode_count_above', 999):
            rules_matched.append('needs_review.episode_count_above')
            if ai_decision == 'APPROVED' and ai_confidence < 0.90:
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
