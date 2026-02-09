# PlexStaffAI

![Version](https://img.shields.io/badge/stable-v1.5.0-blue?style=for-the-badge)
![Dev](https://img.shields.io/badge/dev-v1.6.0--beta-orange?style=for-the-badge)
![Docker](https://img.shields.io/docker/pulls/malambert35/plexstaffai?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

**AI-Powered Content Moderation for Overseerr/Jellyseerr**

PlexStaffAI automatically moderates media requests using OpenAI's GPT models, reducing manual review workload while maintaining quality control through customizable rules and machine learning.

---

## 🆕 What's New in v1.6 (Beta)

### 🎯 Smart Configuration Rules
- **YAML-based customization** - Edit moderation rules without code changes
- **Auto-approve criteria** - High ratings, award-winning content, approved genres
- **Auto-reject filters** - Low ratings, banned genres, spam keywords
- **User trust levels** - Different rules for new/trusted/veteran users

### 🧑‍⚖️ Human Review System
- **NEEDS_REVIEW status** - Flag content requiring staff approval
- **Dedicated review dashboard** - Clean interface for pending decisions
- **Smart triggers** - Long series (100+ episodes), new users + obscure content
- **Manual override** - Staff can approve/reject with custom reasons

### 🧠 Machine Learning Feedback Loop
- **Learn from decisions** - Records all human approvals/rejections
- **Pattern recognition** - Auto-moderates similar content after 100+ feedbacks
- **Cost optimization** - Reduces OpenAI API calls over time
- **Confidence scoring** - Transparency on decision certainty

### 📊 Enhanced Analytics
- **Rule matching tracking** - See which rules triggered decisions
- **ML accuracy metrics** - Monitor learning performance
- **Per-user statistics** - Track user request patterns
- **Decision confidence** - Know when AI is uncertain

---

## 🚀 Quick Start

### Production (Stable)

```yaml
version: '3.8'

services:
  plexstaffai:
    image: malambert35/plexstaffai:latest
    container_name: plexstaffai
    environment:
      - OPENAI_API_KEY=sk-your-key-here
      - OVERSEERR_API_URL=http://overseerr:5055
      - OVERSEERR_API_KEY=your-overseerr-key
      - TZ=America/Montreal
    volumes:
      - /path/to/appdata/plexstaffai:/config
    ports:
      - "5056:5056"
    restart: unless-stopped
