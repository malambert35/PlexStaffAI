<div align="center">

# 🚀 PlexStaffAI

### Modération Automatique IA pour Overseerr/Plex

[![Docker Pulls](https://img.shields.io/docker/pulls/malambert35/plexstaffai?style=for-the-badge&logo=docker&logoColor=white)](https://hub.docker.com/r/malambert35/plexstaffai)
[![GitHub Stars](https://img.shields.io/github/stars/malambert35/PlexStaffAI?style=for-the-badge&logo=github)](https://github.com/malambert35/PlexStaffAI)
[![License](https://img.shields.io/github/license/malambert35/PlexStaffAI?style=for-the-badge)](LICENSE)
[![Docker Image Size](https://img.shields.io/docker/image-size/malambert35/plexstaffai?style=for-the-badge&logo=docker)](https://hub.docker.com/r/malambert35/plexstaffai)

**Dashboard Web HTMX • Auto-Scan 15min • Historique Persistant • GPT-4o-mini**

[🚀 Quickstart](#-quickstart-2min) • [📖 Documentation](#-configuration) • [💻 API](#-endpoints-api) • [🤝 Contribute](#-contribution)

---

</div>

## ⚡ Pourquoi PlexStaffAI ?

> **80% de temps staff économisé** avec modération IA contextuelle automatique

| Avant | Après PlexStaffAI |
|-------|-------------------|
| ❌ Modération manuelle 24/7 | ✅ Auto-scan toutes les 15min |
| ❌ Décisions subjectives incohérentes | ✅ IA GPT-4o-mini contextuelle |
| ❌ Pas d'historique auditable | ✅ Base SQLite persistante |
| ❌ Interface Overseerr basique | ✅ Dashboard moderne HTMX temps réel |
| ❌ Zéro insights staff performance | ✅ Stats live (%, 24h, total) |

---

## 🎯 Fonctionnalités Clés

<table>
<tr>
<td width="50%">

### 🤖 Modération IA
- GPT-4o-mini context-aware
- Approve/Reject automatique
- Raisons détaillées affichées
- Extraction titre robuste (multi-path)
- Fallback configurable (default approve)

</td>
<td width="50%">

### ⏰ Auto-Scan Cron
- Scan automatique 15min (configurable)
- Logs persistants `/logs/auto-moderate.log`
- Zéro intervention manuelle requise
- Force manual avec bouton dashboard
- Health monitoring `/health`

</td>
</tr>
<tr>
<td width="50%">

### 🌐 Dashboard HTMX
- Interface moderne Tailwind CSS
- Auto-refresh stats 30s
- Fragment loading (pas de refresh page)
- Responsive mobile-ready
- Actions temps réel AJAX

</td>
<td width="50%">

### 📜 Historique SQLite
- 100 dernières décisions tabulées
- Persistance volume Docker `/config`
- Stats globales (total, %, 24h)
- Audit trail complet
- Survit reboots/upgrades

</td>
</tr>
</table>

---

## 🚀 Quickstart (2min)

### Option 1: Docker Compose (Recommandé Unraid)

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
      - TZ=America/Montreal
    volumes:
      - /mnt/user/appdata/plexstaffai:/config
    ports:
      - 5056:5056
    networks:
      - proxarr
    restart: unless-stopped
```

Option 2: Docker Run

```
docker run -d \
  --name plexstaffai \
  -e OPENAI_API_KEY=sk-xxx \
  -e OVERSEERR_API_URL=http://overseerr:5055 \
  -e OVERSEERR_API_KEY=xxx \
  -p 5056:5056 \
  -v /mnt/user/appdata/plexstaffai:/config \
  --restart unless-stopped \
  malambert35/plexstaffai:latest
```

Option 3: Portainer Stack

Portainer → Stacks → Add Stack
Colle le docker-compose ci-dessus
Édite les variables OPENAI_API_KEY et OVERSEERR_API_KEY
Deploy Stack
Accès: http://ton-unraid:5056/
Obtenir clés API :
OpenAI : platform.openai.com/api-keys
Overseerr : Settings → General → API Key
