import openai
import os
import json
from typing import Dict

class OpenAIModerator:
    """OpenAI-powered primary content moderation with deep reasoning"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
        
        self.model = "gpt-4o-mini"
        self.temperature = 0.3  # Un peu plus haut pour raisonnement naturel
        self.max_tokens = 300
    
    def moderate(self, request_data: Dict) -> Dict:
        """
        Analyse primaire avec OpenAI - raisonnement complet
        
        Returns:
            {
                'decision': 'APPROVED' | 'REJECTED' | 'NEEDS_REVIEW',
                'confidence': 0.0-1.0,
                'reason': str,
                'detailed_reasoning': str,
                'risk_factors': {...},
                'value_score': float
            }
        """
        if not self.api_key:
            return {
                'decision': 'NEEDS_REVIEW',
                'confidence': 0.0,
                'reason': 'OpenAI not configured',
                'detailed_reasoning': 'API key missing'
            }
        
        try:
            # Prépare contexte riche
            title = request_data.get('title', 'Unknown')
            media_type = request_data.get('media_type', 'unknown')
            year = request_data.get('year', 'N/A')
            rating = request_data.get('rating', 0)
            popularity = request_data.get('popularity', 0)
            genres = ', '.join(request_data.get('genres', []))
            seasons = request_data.get('season_count', 0)
            episodes = request_data.get('episode_count', 0)
            user = request_data.get('requested_by', 'Unknown')
            user_age_days = request_data.get('user_age_days', 0)
            
            # Classification utilisateur
            if user_age_days < 7:
                user_trust = "NEW (less than 1 week)"
            elif user_age_days < 30:
                user_trust = "RECENT (less than 1 month)"
            elif user_age_days < 365:
                user_trust = "ESTABLISHED (less than 1 year)"
            else:
                user_trust = "TRUSTED (over 1 year)"
            
            # 🎯 Prompt Engineering - Analyse Profonde
            system_prompt = """You are an expert media content curator and moderator for a personal Plex server.

Your role is to evaluate content requests with nuanced judgment, considering:

🎯 CONTENT QUALITY:
- TMDB rating and critical reception
- Genre relevance and audience appeal
- Cultural significance and lasting value

💾 STORAGE ECONOMICS:
- Series length vs quality ratio
- Likelihood of actual viewing
- Server capacity considerations

👤 USER TRUST LEVEL:
- Account age and history
- Pattern of requests (inferred)
- Risk of inappropriate requests

🎬 MODERATION PHILOSOPHY:
- Approve high-quality mainstream content readily
- Be selective with obscure/niche content
- Consider storage cost for very long series
- Trust established users more than new accounts
- Reject clearly low-quality or inappropriate content

Be decisive and confident in your reasoning. Explain your thought process.

Respond with valid JSON:
{
  "decision": "APPROVED|REJECTED|NEEDS_REVIEW",
  "confidence": 0.0-1.0,
  "reason": "Brief explanation (100 chars)",
  "detailed_reasoning": "Full analysis (200 chars)",
  "risk_factors": {
    "quality_risk": 0-10,
    "storage_risk": 0-10,
    "appropriateness_risk": 0-10,
    "user_trust_risk": 0-10
  },
  "value_score": 0-10
}"""

            user_prompt = f"""Evaluate this media request with full context:

📺 CONTENT PROFILE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title: {title}
Type: {media_type.upper()}
Year: {year}
TMDB Rating: {rating}/10 {"⭐⭐⭐" if rating >= 8 else "⭐⭐" if rating >= 6.5 else "⭐" if rating >= 5 else "❌"}
Popularity: {popularity} {"🔥" if popularity > 100 else "📈" if popularity > 50 else "📊" if popularity > 10 else "📉"}
Genres: {genres}
{"Series Length: " + str(seasons) + " seasons, " + str(episodes) + " episodes" if episodes > 0 else "Movie"}
{"⚠️  LONG SERIES (High storage)" if episodes > 100 else "✅ Reasonable length" if episodes > 0 else ""}

👤 USER CONTEXT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Username: {user}
Account Age: {user_age_days} days
Trust Level: {user_trust}

🤔 YOUR TASK:
Analyze this request deeply and provide:
1. Your moderation decision with confidence level
2. Brief reason (for user display)
3. Detailed reasoning (your thought process)
4. Risk assessment across 4 dimensions
5. Overall value score (0-10)

Think step-by-step about quality, storage impact, user trust, and appropriateness."""

            # Appel OpenAI
            print(f"\n🤖 {'='*60}")
            print(f"🤖 CONSULTING OPENAI GPT-4o-mini...")
            print(f"🤖 {'='*60}")
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Parse réponse
            content = response.choices[0].message.content.strip()
            
            # Nettoie markdown
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1]) if len(lines) > 2 else content
            
            result = json.loads(content)
            
            # Validation et extraction
            decision = result.get('decision', 'NEEDS_REVIEW')
            if decision not in ['APPROVED', 'REJECTED', 'NEEDS_REVIEW']:
                decision = 'NEEDS_REVIEW'
            
            confidence = float(result.get('confidence', 0.5))
            confidence = max(0.0, min(1.0, confidence))
            
            reason = result.get('reason', 'OpenAI analysis')[:150]
            detailed_reasoning = result.get('detailed_reasoning', reason)[:300]
            
            risk_factors = result.get('risk_factors', {
                'quality_risk': 5,
                'storage_risk': 5,
                'appropriateness_risk': 5,
                'user_trust_risk': 5
            })
            
            value_score = float(result.get('value_score', 5.0))
            
            # Logs
            print(f"🤖 AI Decision: {decision}")
            print(f"🤖 Confidence: {confidence:.1%}")
            print(f"🤖 Reason: {reason}")
            print(f"🤖 Value Score: {value_score}/10")
            print(f"🤖 Risk Profile:")
            print(f"   - Quality: {risk_factors.get('quality_risk', 0)}/10")
            print(f"   - Storage: {risk_factors.get('storage_risk', 0)}/10")
            print(f"   - Appropriateness: {risk_factors.get('appropriateness_risk', 0)}/10")
            print(f"   - User Trust: {risk_factors.get('user_trust_risk', 0)}/10")
            print(f"🤖 {'='*60}\n")
            
            return {
                'decision': decision,
                'confidence': confidence,
                'reason': reason,
                'detailed_reasoning': detailed_reasoning,
                'risk_factors': risk_factors,
                'value_score': value_score,
                'model_used': self.model
            }
            
        except json.JSONDecodeError as e:
            print(f"❌ OpenAI JSON parse error: {e}")
            print(f"Raw response: {content}")
            return {
                'decision': 'NEEDS_REVIEW',
                'confidence': 0.0,
                'reason': 'AI response parse error',
                'detailed_reasoning': str(e)
            }
        except Exception as e:
            print(f"❌ OpenAI error: {e}")
            return {
                'decision': 'NEEDS_REVIEW',
                'confidence': 0.0,
                'reason': f'AI error: {str(e)[:50]}',
                'detailed_reasoning': str(e)
            }
