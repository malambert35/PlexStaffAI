# PlexStaffAI 🚀

**IA Agent pour Staff Overseerr/Plex** : Modération auto requests, insights prédictifs, audits – Unraid ready.

[![Docker Image](https://img.shields.io/docker/pulls/tonpseudo/plexstaffai)](https://hub.docker.com/r/tonpseudo/plexstaffai)
[![GitHub stars](https://img.shields.io/github/stars/tonpseudo/plexstaffai)](https://github.com/tonpseudo/plexstaffai)

## 🎯 Fonctionnalités
- ✅ **Modération IA** : GPT-4o-mini approve/reject spam/abuse
- 📊 **Insights Staff** : Top users, prédictions hits Plex
- 🛡️ **Audits DB** : Logs décisions traçables
- 🔌 **Intègre Overseerr/Plex/*arr** (port 5056 UI)

## 🚀 Quickstart Unraid
```bash
git clone https://github.com/tonpseudo/plexstaffai
cd plexstaffai
cp config.json.example config.json  # Édite keys
docker compose up -d
