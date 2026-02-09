# 🤖 PlexStaffAI

**Intelligent AI-powered content moderation system for Overseerr/Plex with OpenAI GPT-4o-mini**

[![Docker](https://img.shields.io/badge/docker-latest-blue.svg)](https://hub.docker.com/r/malambert35/plexstaffai)
[![Version](https://img.shields.io/badge/version-1.6.0-green.svg)](https://github.com/malambert35/PlexStaffAI/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Built with AI](https://img.shields.io/badge/built_with-Claude_Sonnet-8A2BE2.svg)](https://www.anthropic.com/claude)

# PlexStaffAI

![Version](https://img.shields.io/badge/stable-v1.6.0-blue?style=for-the-badge)
![Docker](https://img.shields.io/docker/pulls/malambert35/plexstaffai?style=for-the-badge)

**🧪 v1.6 Available:** Smart Rules + ML Feedback System

### ✨ Key Features

- 🤖 **OpenAI GPT-4o-mini** primary moderation with deep reasoning
- 🎯 **Rules Validation Layer** that can override or adjust AI decisions
- 📊 **TMDB Enrichment** for complete metadata when Overseerr data is incomplete
- 🧠 **Machine Learning** that improves from staff feedback
- 📈 **Advanced Analytics** with confidence scores and risk assessment
- 🎨 **Beautiful Dashboard** with real-time statistics
- 🧑‍⚖️ **Review Queue** for edge cases requiring human judgment
- 💾 **Complete History** with full request metadata

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API Key (required) - [Get one here](https://platform.openai.com/api-keys)
- Overseerr instance with API access
- TMDB API Key (optional but recommended) - [Get one here](https://www.themoviedb.org/settings/api)

### Installation

#### Option 1: Docker Compose (Recommended)

**1. Create `docker-compose.yml`:**

```yaml
version: '3.8'

services:
  plexstaffai:
    image: malambert35/plexstaffai:latest
    container_name: plexstaffai
    restart: unless-stopped
    ports:
      - "5056:5056"
    volumes:
      - ./config:/config
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OVERSEERR_API_URL=${OVERSEERR_API_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
      - TMDB_API_KEY=${TMDB_API_KEY}
```

**2. Create `.env` file:**

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
OVERSEERR_API_URL=http://overseerr:5055
OVERSEERR_API_KEY=your-overseerr-api-key
TMDB_API_KEY=your-tmdb-api-key
```

**3. Create `config/config.yaml`:**

```yaml
# PlexStaffAI Configuration v1.6.0

# Auto-approve rules (strict - will override AI if matched)
auto_approve:
  rating_above: 8.0          # TMDB rating >= 8.0
  popularity_above: 100      # TMDB popularity >= 100
  genres:                    # Whitelisted genres
    - Drama
    - Documentary
    - Science Fiction

# Auto-reject rules (strict - will override AI if matched)
auto_reject:
  rating_below: 4.0          # TMDB rating <= 4.0
  genres:                    # Blacklisted genres
    - Reality
    - Talk

# Needs review triggers (AI + rules collaboration)
needs_review:
  episode_count_above: 100   # Long series need review
  new_user_days: 30          # New users (<30 days)
  obscure_popularity_threshold: 10  # Low popularity content

# Machine Learning
machine_learning:
  enabled: true
  min_samples_to_learn: 100
  confidence_threshold: 0.75
  auto_apply_patterns: true
```

**4. Start:**

```bash
docker-compose up -d
```

**5. Access Dashboard:**

```
http://localhost:5056
```

---

#### Option 2: Docker Run

```bash
docker run -d \
  --name plexstaffai \
  --restart unless-stopped \
  -p 5056:5056 \
  -v $(pwd)/config:/config \
  -e OPENAI_API_KEY="sk-proj-xxx..." \
  -e OVERSEERR_API_URL="http://overseerr:5055" \
  -e OVERSEERR_API_KEY="your-key" \
  -e TMDB_API_KEY="your-tmdb-key" \
  malambert35/plexstaffai:latest
```

---

## 📊 Architecture

### AI-First Workflow

```
┌─────────────────────────────────────────────────────┐
│  NEW REQUEST from Overseerr                         │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  📊 DATA ENRICHMENT                                 │
│  - Overseerr metadata                               │
│  - TMDB API enrichment (if needed)                  │
│  - User trust level calculation                     │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  🤖 LEVEL 1: OPENAI ANALYSIS                       │
│  - GPT-4o-mini deep reasoning                       │
│  - Multi-dimensional risk assessment                │
│  - Confidence scoring                               │
│  - Value score calculation                          │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  🎯 LEVEL 2: RULES VALIDATION                      │
│  - Check auto-approve rules                         │
│  - Check auto-reject rules                          │
│  - Adjust confidence based on rules                 │
│  - Override AI if strict rule matched               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  ✅ FINAL DECISION                                  │
│  - APPROVED → Auto-approve in Overseerr             │
│  - REJECTED → Auto-decline in Overseerr             │
│  - NEEDS_REVIEW → Queue for staff review            │
└─────────────────────────────────────────────────────┘
```

### Decision Logic

1. **OpenAI Primary Analysis**: GPT-4o-mini analyzes content quality, storage impact, user trust, and appropriateness
2. **Rules Validation**: Configured rules can:
   - **Override AI** (auto-approve/reject based on strict rules)
   - **Adjust confidence** (increase/decrease based on supporting rules)
   - **Trigger review** (edge cases that need human judgment)
3. **Final Action**: Execute decision in Overseerr or queue for staff review

---

## 🎛️ Configuration Guide

### OpenAI Settings

**Model:** `gpt-4o-mini` (default)
**Cost:** ~$0.02 per request
**Temperature:** 0.3 (consistent decisions)
**Max Tokens:** 300 (detailed reasoning)

### Rules Configuration

#### Auto-Approve (Strict Override)

```yaml
auto_approve:
  rating_above: 8.0          # High-quality content
  popularity_above: 100      # Popular mainstream content
  genres:
    - Documentary            # Educational content
    - Animation              # Family-friendly
```

**Effect**: If ANY rule matches, AI decision is overridden to APPROVED (unless rejected by auto-reject rule)

#### Auto-Reject (Strict Override)

```yaml
auto_reject:
  rating_below: 4.0          # Low-quality content
  genres:
    - Reality                # Not desired genres
    - Talk Show
```

**Effect**: If ANY rule matches, AI decision is overridden to REJECTED

#### Needs Review Triggers

```yaml
needs_review:
  episode_count_above: 100   # Very long series
  new_user_days: 30          # New/untrusted users
  obscure_popularity_threshold: 10  # Obscure content
```

**Effect**: Reduces AI confidence, may trigger human review if confidence drops below 75%

---

## 📱 Dashboard Features

### Main Dashboard (`/`)
- Real-time statistics
- Manual moderation trigger
- Quick access to all features

### Health Check (`/health`)
- Service status monitoring
- API connectivity checks
- System uptime

### Moderation Report (`/staff/report`)
- Comprehensive statistics
- Top rules used
- Recent decisions
- Approval rates

### History (`/history`)
- Complete decision log
- Full metadata display
- Filter by decision type
- Detailed reasoning

### Review Dashboard (`/review-dashboard`)
- Pending reviews queue
- Staff approval/rejection
- Feedback for ML learning

### OpenAI Stats (`/staff/openai-stats`)
- API usage tracking
- Cost estimation
- Decision distribution

---

## 💰 Cost Analysis

### OpenAI Costs (GPT-4o-mini)

- **Per Request**: ~$0.02
- **Per 100 Requests**: ~$2.00
- **Per 1000 Requests**: ~$20.00

### Example Monthly Costs

| Requests/Month | Estimated Cost |
|----------------|----------------|
| 50             | $1.00          |
| 200            | $4.00          |
| 500            | $10.00         |
| 1000           | $20.00         |
| 2000           | $40.00         |

### Cost Optimization Tips

1. **Use Rules First**: Strict rules bypass OpenAI calls
2. **Adjust Confidence**: Higher thresholds reduce reviews
3. **Cache Results**: Similar requests can reuse decisions (future feature)

---

## 🔧 API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/health` | GET | System health check |
| `/stats` | GET | Real-time statistics |
| `/staff/moderate` | GET/POST | Manual moderation trigger |
| `/moderate-html` | GET | HTMX moderation results |
| `/history` | GET | Full decision history |
| `/api/history` | GET | History API (JSON) |
| `/staff/report` | GET | Comprehensive report |
| `/review-dashboard` | GET | Staff review interface |
| `/staff/reviews` | GET | Pending reviews API |
| `/staff/review/approve/{id}` | POST | Approve pending review |
| `/staff/review/reject/{id}` | POST | Reject pending review |
| `/staff/openai-stats` | GET | OpenAI usage statistics |
| `/staff/ml-stats` | GET | ML system statistics |

---

## 🤖 OpenAI Integration

### How It Works

PlexStaffAI uses **GPT-4o-mini** with a carefully engineered prompt that analyzes:

1. **Content Quality**
   - TMDB rating and critical reception
   - Genre relevance and audience appeal
   - Cultural significance

2. **Storage Economics**
   - Series length vs quality ratio
   - Likelihood of actual viewing
   - Server capacity considerations

3. **User Trust Level**
   - Account age
   - Request history patterns
   - Risk assessment

4. **Risk Assessment**
   - Quality risk (0-10)
   - Storage risk (0-10)
   - Appropriateness risk (0-10)
   - User trust risk (0-10)

### Response Format

```json
{
  "decision": "APPROVED|REJECTED|NEEDS_REVIEW",
  "confidence": 0.85,
  "reason": "High-quality mainstream series with excellent rating",
  "detailed_reasoning": "Breaking Bad has exceptional critical acclaim...",
  "risk_factors": {
    "quality_risk": 1,
    "storage_risk": 3,
    "appropriateness_risk": 4,
    "user_trust_risk": 2
  },
  "value_score": 9.5
}
```

---

## 🧠 Machine Learning

### Self-Learning System

When staff reviews AI decisions:
1. **Feedback Collection**: Staff approval/rejection stored
2. **Pattern Recognition**: System identifies disagreement patterns
3. **Confidence Adjustment**: Future similar requests adjusted
4. **Continuous Improvement**: Learns from 100+ feedback samples

### ML Statistics

View ML stats at `/staff/ml-stats`:
- Total feedback collected
- Patterns learned
- Unlearned feedback
- Learning threshold status

---

## 🛠️ Development

### Project Structure

```
PlexStaffAI/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── openai_moderator.py     # OpenAI integration
│   ├── rules_validator.py      # Rules validation layer
│   ├── config_loader.py        # Configuration management
│   └── ml_feedback.py          # Machine learning system
├── static/
│   ├── index.html              # Main dashboard
│   ├── history.html            # History page
│   └── review_dashboard.html   # Review interface
├── config/
│   ├── config.yaml             # User configuration
│   ├── moderation.db           # Decisions database
│   └── feedback.db             # ML feedback database
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### Building from Source

```bash
# Clone repository
git clone https://github.com/malambert35/PlexStaffAI.git
cd PlexStaffAI

# Build Docker image
docker build -t plexstaffai:custom .

# Run with custom image
docker run -d \
  --name plexstaffai \
  -p 5056:5056 \
  -v $(pwd)/config:/config \
  -e OPENAI_API_KEY="sk-xxx" \
  plexstaffai:custom
```

### Development Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 5056
```

---

## 📚 Examples

### Example 1: High-Quality Series

**Request:** Breaking Bad (TMDB Rating: 8.9, 62 episodes)

```
🤖 OpenAI Analysis:
   Decision: APPROVED
   Confidence: 95%
   Reason: Exceptional critically-acclaimed series
   Value Score: 9.5/10

🎯 Rules Validation:
   ✅ Rule "rating_above" supports decision (+10%)
   Final: APPROVED (100%)
```

### Example 2: Long Low-Quality Series

**Request:** Generic Reality Show (TMDB Rating: 3.2, 500 episodes)

```
🤖 OpenAI Analysis:
   Decision: REJECTED
   Confidence: 90%
   Reason: Low quality, extremely long series
   Value Score: 2.0/10

🎯 Rules Validation:
   ✅ Rule "rating_below" supports decision (+10%)
   ✅ Genre blacklisted
   Final: REJECTED (100%)
```

### Example 3: New User + Obscure Content

**Request:** Unknown Indie Series (Popularity: 5, User: 10 days old)

```
🤖 OpenAI Analysis:
   Decision: APPROVED
   Confidence: 65%
   Reason: Decent quality but obscure
   Value Score: 5.5/10

🎯 Rules Validation:
   ⚠️  New user + obscure content (-10%)
   Final: NEEDS_REVIEW (55%)
   → Queued for staff review
```

---

## 🔒 Security & Privacy

- **API Keys**: Store in `.env` file, never commit to git
- **Database**: Local SQLite, no external data transmission
- **OpenAI**: Only sends metadata (title, rating, genres), no personal info
- **Logs**: Review logs for sensitive data before sharing

---

## 🐛 Troubleshooting

### OpenAI Errors

**Error:** `"AI error: You tried to access openai.ChatCompletion..."`

**Solution:** Update OpenAI package:
```bash
pip install openai>=1.0.0
```

### TMDB Enrichment Not Working

**Check:**
1. `TMDB_API_KEY` is set
2. API key is valid
3. Check logs for TMDB errors

### No Requests Detected

**Check:**
1. Overseerr API URL is correct
2. Overseerr API key is valid
3. Requests are actually pending in Overseerr

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## 📝 Changelog

### v1.6.0 (2026-02-08)
- ✨ Added OpenAI GPT-4o-mini primary moderation
- ✨ Added rules validation layer
- ✨ Added TMDB enrichment
- ✨ Added OpenAI usage statistics
- 🔧 Updated API to OpenAI v1.0+
- 📊 Enhanced history with full metadata

### v1.5.0
- ✨ Machine learning feedback system
- ✨ Enhanced moderation rules
- 🎨 Improved dashboard UI

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- **OpenAI** for GPT-4o-mini API
- **TMDB** for metadata enrichment
- **Overseerr** for request management
- **FastAPI** for web framework

---

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/malambert35/PlexStaffAI/issues)
- **Discussions**: [GitHub Discussions](https://github.com/malambert35/PlexStaffAI/discussions)
- **Email**: contact via GitHub

---

## ⭐ Star History

If you find this project useful, please consider giving it a star! ⭐

---

<div align="center">

**Made with ❤️ by [@malambert35](https://github.com/malambert35)**

</div>
