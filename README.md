# PlexStaffAI 🚀 IA Staff Booster pour Overseerr/Plex

**Modération automatique des requests par IA** (GPT-4o-mini), insights prédictifs, audits complets.  
**Unraid/Plex/*arr ready** – Réduit 80% du toil staff.

[![Docker Pulls](https://img.shields.io/docker/pulls/tonpseudo/plexstaffai)](https://hub.docker.com/r/tonpseudo/plexstaffai)
[![Docker Stars](https://img.shields.io/docker/stars/tonpseudo/plexstaffai)](https://hub.docker.com/r/tonpseudo/plexstaffai)
[![GitHub Stars](https://img.shields.io/github/stars/tonpseudo/plexstaffai)](https://github.com/tonpseudo/plexstaffai)
[![License](https://img.shields.io/github/license/tonpseudo/plexstaffai)](LICENSE)

## 🎯 Fonctionnalités Uniques

| Fonctionnalité | Description | Impact |
|---------------|-------------|--------|
| 🤖 **Modération IA** | GPT-4o-mini approve/reject spam/abuse auto | **-80% temps staff** |
| 📊 **Insights Prédictifs** | Top users, tendances Plex, alertes anomalies | **Décisions data-driven** |
| 🗄️ **Audits SQLite** | Logs traçables toutes décisions IA | **Compliance/Wazuh ready** |
| ⚙️ **Cron Auto** | Modération toutes 30min, rapports quotidiens | **Zéro manuel** |
| 🔌 **API Overseerr/Plex** | Intégration native ton stack | **Plug & play** |

**Rien d'équivalent** : Premier tool IA native pour Overseerr staff management.

## 🚀 Quickstart Unraid (2min)

### Méthode 1: Docker Hub (Recommandé)
```bash
docker run -d \
  --name plexstaffai \
  -e OPENAI_API_KEY=sk-your-key \
  -e OVERSEERR_API_URL=http://overseerr:5055 \
  -e OVERSEERR_API_KEY=your-api-key \
  -e PLEX_URL=http://plex:32400 \
  -e PLEX_TOKEN=your-plex-token \
  -p 5056:5056 \
  -v /mnt/user/appdata/plexstaffai:/config \
  --network proxarr \
  --restart unless-stopped \
  tonpseudo/plexstaffai:latest
