# PlexStaffAI 🚀 IA Staff Management pour Overseerr/Plex

**Modération automatique IA des requests Overseerr** avec GPT-4o-mini, dashboard web HTMX, historique persistant et auto-scan cron.  
**Unraid/*arr ready** – Réduit 80% du toil staff Plex.

[![Docker Pulls](https://img.shields.io/docker/pulls/malambert35/plexstaffai)](https://hub.docker.com/r/malambert35/plexstaffai)
[![Docker Stars](https://img.shields.io/docker/stars/malambert35/plexstaffai)](https://hub.docker.com/r/malambert35/plexstaffai)
[![GitHub Stars](https://img.shields.io/github/stars/malambert35/PlexStaffAI)](https://github.com/malambert35/PlexStaffAI)
[![License](https://img.shields.io/github/license/malambert35/PlexStaffAI)](LICENSE)

---

## 🎯 Fonctionnalités v1.5

| Feature | Description | Impact |
|---------|-------------|--------|
| 🤖 **Modération IA GPT-4o-mini** | Approve/reject automatique requests Overseerr avec raisons contextuelles | **-80% temps staff** |
| 🌐 **Dashboard Web HTMX** | Interface moderne temps réel (Tailwind CSS + HTMX) | **UI pro sans JS build** |
| 📜 **Historique Persistant** | Base SQLite 100 dernières décisions (survit reboots) | **Audits complets** |
| ⏰ **Auto-Scan 15min** | Cron automatique modère queue Overseerr sans intervention | **Zéro manuel** |
| 🔗 **API Overseerr Native** | Vraie intégration approve/decline (pas mock) | **Actions réelles** |
| 📊 **Stats Temps Réel** | Total décisions, % approved, activité 24h (auto-refresh 30s) | **Métriques live** |
| 🛡️ **Context-Aware IA** | Titre, type, année, user → décisions intelligentes | **Précision optimale** |

---

## 🚀 Quickstart (2min)

### Docker Compose (Recommandé)
```yaml
version: '3.8'
services:
  plexstaffai:
    image: malambert35/plexstaffai:latest
    container_name: plexstaffai
    environment:
      - OPENAI_API_KEY=sk-your-openai-key
      - OVERSEERR_API_URL=http://overseerr:5055
      - OVERSEERR_API_KEY=your-overseerr-api-key
      - PLEX_URL=http://plex:32400
      - PLEX_TOKEN=your-plex-token
      - TZ=America/Montreal
    volumes:
      - /mnt/user/appdata/plexstaffai:/config
    ports:
      - 5056:5056
    networks:
      - proxarr
    restart: unless-stopped
networks:
  proxarr:
    external: true


