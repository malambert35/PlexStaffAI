# 🤖 PlexStaffAI

**Intelligent AI-powered content moderation system for Overseerr/Plex with OpenAI GPT-4o-mini**

[![Docker](https://img.shields.io/badge/docker-latest-blue.svg)](https://hub.docker.com/r/malambert35/plexstaffai)
[![Version](https://img.shields.io/badge/version-1.6.0-green.svg)](https://github.com/malambert35/PlexStaffAI/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)

---

## 🎯 Overview

PlexStaffAI is an **AI-first moderation system** that automatically evaluates Overseerr media requests using OpenAI's GPT-4o-mini with a sophisticated rules validation layer. It combines artificial intelligence reasoning with configurable rules to make intelligent decisions about content approval.

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
