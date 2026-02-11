# 🤖 PlexStaffAI

**Modération automatique intelligente pour Overseerr/Plex avec IA**

PlexStaffAI est un système de modération automatique qui analyse les demandes de contenu dans Overseerr en temps réel, utilise l'IA pour prendre des décisions intelligentes, et automatise l'approbation/rejet selon des règles personnalisables.

---

## ✨ Fonctionnalités

### 🚀 **Modération Instantanée via Webhook**
- **Réaction en < 1 seconde** après chaque demande utilisateur
- Webhook Overseerr intégré (plus besoin de polling)
- Traitement en arrière-plan non-bloquant

### 🧠 **IA Hybride : Rules-First + OpenAI**
- **Validation par règles AVANT OpenAI** (économise des tokens)
- Whitelist/Blacklist de genres automatiques
- Seuils de rating, popularité, nombre d'épisodes
- Fallback OpenAI pour cas complexes uniquement
- Support GPT-4o-mini et GPT-4o

### 🌐 **Enrichissement TMDB Automatique**
- Récupère les métadonnées manquantes depuis TMDB
- Normalisation des genres (FR → EN)
- Détection précise des saisons/épisodes
- Fallback robuste si données Overseerr incomplètes

### 🎯 **3 Types de Décisions**
1. **APPROVED** ✅ : Approuvé automatiquement dans Overseerr
2. **REJECTED** ❌ : Rejeté automatiquement
3. **NEEDS_REVIEW** 🧑‍⚖️ : Envoyé en révision manuelle

### 📊 **Dashboard Web Temps Réel**
- Interface moderne avec Tailwind CSS + HTMX
- Statistiques en temps réel (taux d'approbation, décisions)
- Historique complet des modérations
- Gestion des révisions manuelles (approve/reject)
- Support multilingue (FR/EN)
- Statistiques d'utilisation OpenAI

### 🔒 **Sécurité**
- Authentification webhook par Bearer Token (optionnel)
- Validation des requêtes Overseerr
- Détection de duplicatas
- Nettoyage automatique des requêtes obsolètes

---

## 🏗️ Architecture

```
┌─────────────────┐
│   Overseerr     │
│  (User Request) │
└────────┬────────┘
         │ Webhook (< 1s)
         ↓
┌─────────────────┐
│  PlexStaffAI    │
│                 │
│  1. TMDB Enrich │ ← Métadonnées complètes
│  2. Rules Check │ ← Whitelist/Blacklist/Limits
│  3. OpenAI (si  │ ← IA pour cas complexes
│     nécessaire) │
│  4. Decision    │ → APPROVED/REJECTED/REVIEW
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Overseerr     │ ← Auto-approve/decline
│   Radarr/Sonarr │ ← Download si approuvé
└─────────────────┘
```

---

## 🚀 Installation

### **Prérequis**
- Docker + Docker Compose
- Overseerr configuré et fonctionnel
- Clés API :
  - **TMDB API Key** (gratuit) : https://www.themoviedb.org/settings/api
  - **Overseerr API Key** : Settings → General → API Key
  - **OpenAI API Key** (optionnel) : https://platform.openai.com/api-keys

---

### **1. Clone le dépôt**
```bash
git clone https://github.com/malambert35/PlexStaffAI.git
cd PlexStaffAI
```

---

### **2. Configuration Docker Compose**

**`docker-compose.yml`**
```yaml
version: '3.8'

services:
  plexstaffai:
    container_name: PlexStaffAI
    image: ghcr.io/malambert35/plexstaffai:latest
    # build: .  # Si tu veux build localement
    ports:
      - "5056:5056"
    volumes:
      - ./config:/config
    environment:
      # ✅ REQUIS
      - OVERSEERR_API_URL=http://overseerr:5055
      - OVERSEERR_API_KEY=your_overseerr_api_key_here
      - TMDB_API_KEY=your_tmdb_api_key_here

      # 🤖 OpenAI (optionnel, mais recommandé)
      - OPENAI_API_KEY=your_openai_api_key_here
      - OPENAI_ENABLED=true  # false = Rules-Only mode

      # 🔒 Sécurité Webhook (optionnel)
      - WEBHOOK_SECRET=mon-super-token-secret-123

    restart: unless-stopped
    networks:
      - overseerr_network

networks:
  overseerr_network:
    external: true  # Si Overseerr est sur un réseau Docker existant
```

---

### **3. Configuration des Règles**

**`config/config.yaml`** (créé automatiquement au premier démarrage)

```yaml
# 🎯 RÈGLES DE MODÉRATION
rules:
  # Genres - Auto-Approve
  genres:
    whitelist:
      - Documentary
      - Animation
      - Family

    # Genres - Auto-Reject
    blacklist:
      - Adult
      - Erotic

  # Limites strictes
  limits:
    min_rating: 6.0          # Minimum TMDB rating
    max_episodes: 300        # Reject séries > 300 épisodes
    max_seasons: 15          # Reject séries > 15 saisons
    min_popularity: 5.0      # Minimum popularité TMDB

  # Nouveaux utilisateurs
  new_user_threshold_days: 30
  new_user_needs_review: true  # Envoie en révision manuelle

# 🤖 OpenAI Configuration
openai:
  model: "gpt-4o-mini"  # ou "gpt-4o" pour + de précision
  temperature: 0.3
  max_tokens: 500
```

---

### **4. Démarrage**

```bash
# Démarrer
docker-compose up -d

# Vérifier les logs
docker logs -f PlexStaffAI

# Tu devrais voir :
# 🚀 PLEXSTAFFAI v1.7.0 STARTED
# 🚀 Mode: WEBHOOK (Instant moderation ⚡)
# 🚀 OpenAI: ✅ Configured
# 🚀 TMDB: ✅ Configured
```

---

### **5. Configuration Overseerr Webhook**

**Settings → Notifications → Webhook**

```
✅ Enable Agent: ON

Webhook URL:
http://plexstaffai:5056/webhook/overseerr

Authorization Header:
Bearer mon-super-token-secret-123
(⚠️ Doit correspondre à WEBHOOK_SECRET dans docker-compose.yml)

JSON Payload: ✅ Enabled

Notification Types:
  ✅ Media Requested
  ❌ Media Approved (décocher)
  ❌ Media Declined (décocher)
  ❌ Media Available (décocher)
  ❌ Tout le reste (décocher)
```

**💡 Si tu ne veux pas de sécurité :** Laisse `Authorization Header` vide et ne mets pas `WEBHOOK_SECRET` dans docker-compose.yml

---

## 🎛️ Utilisation

### **Dashboard Web**
```
http://localhost:5056
```

**Pages disponibles :**
- **/** : Dashboard principal (stats + modération manuelle)
- **/history** : Historique complet des décisions
- **/staff/report** : Rapport détaillé
- **/review-dashboard** : Gestion des révisions manuelles
- **/staff/openai-stats** : Statistiques d'utilisation OpenAI

---

### **Workflow Automatique**

1. **Utilisateur demande un film/série dans Overseerr**
2. **Webhook instantané** → PlexStaffAI (< 1 seconde)
3. **Enrichissement TMDB** (si données manquantes)
4. **Validation par règles** :
   - Whitelist genres → ✅ Auto-approve (skip OpenAI)
   - Blacklist genres → ❌ Auto-reject (skip OpenAI)
   - Limites dépassées → 🧑‍⚖️ Needs review
5. **Si aucune règle stricte** → OpenAI analyse le contenu
6. **Décision finale** :
   - ✅ **APPROVED** → Approuvé dans Overseerr + Download lancé
   - ❌ **REJECTED** → Rejeté dans Overseerr
   - 🧑‍⚖️ **NEEDS_REVIEW** → Attente révision manuelle

---

### **Révision Manuelle**

**Pour les requêtes en `NEEDS_REVIEW` :**

```
http://localhost:5056/review-dashboard
```

- Voir toutes les demandes en attente
- Approuver/Rejeter manuellement avec raison custom
- Les décisions manuelles sont enregistrées pour apprentissage futur

---

### **Trigger Manuel (pour tests)**

```bash
# Forcer la modération de toutes les requêtes en attente
curl -X POST http://localhost:5056/admin/moderate-now

# Nettoyer les reviews obsolètes
curl http://localhost:5056/staff/cleanup-reviews
```

---

## 📊 Exemples de Logs

### **✅ Approved (Rules-First)**
```
🎬 REQUEST #1903: Mia
📺 Type: movie
📅 Year: 2017
👤 User: john.doe
🌐 Data source: TMDB API enrichment ✅
  Rating: 6.1/10
  Genres: Drama, Documentary

🎯 PRE-VALIDATION: Checking strict rules FIRST
⚠️  OVERRIDE: Genre ['Documentary'] is whitelisted (auto-approve)
⚡ FAST PATH: Strict rule override, skipping OpenAI

✅ FINAL DECISION: APPROVED
📝 Reason: Genre whitelisted
🎯 Path: rule_strict:auto_approve.genres
💯 Confidence: 90.0%
💰 OpenAI Cost: $0.00 (skipped)
```

### **❌ Rejected (OpenAI)**
```
🎬 REQUEST #1904: The Last Temptation
📺 Type: movie
  Rating: 4.2/10
  Genres: Horror, Thriller

⚡ No strict rule match, consulting OpenAI...

🤖 OpenAI Analysis:
  Model: gpt-4o-mini
  Tokens: 245 (prompt) + 78 (completion) = 323 total
  Cost: $0.0002

❌ FINAL DECISION: REJECTED
📝 Reason: Low rating (4.2/10), excessive violence
🎯 Path: ai_primary:gpt-4o-mini
💯 Confidence: 85.0%
```

### **🧑‍⚖️ Needs Review**
```
🎬 REQUEST #1905: Game of Thrones (Complete Series)
📺 Type: tv
  Seasons: 8
  Episodes: 73

⚠️  OVERRIDE: Episode count (73) within limits, but flagged for review
⚡ Decision: NEEDS_REVIEW (80.0%)

🧑‍⚖️ FINAL DECISION: NEEDS_REVIEW
📝 Reason: High episode count, requires staff approval
🎯 Path: rule_strict:needs_review.episodes
💯 Confidence: 80.0%
```

---

## ⚙️ Configuration Avancée

### **Mode Rules-Only (sans OpenAI)**

```yaml
environment:
  - OPENAI_ENABLED=false
  # Ne pas mettre OPENAI_API_KEY
```

**Dans ce mode :**
- Seules les règles strictes sont appliquées
- Pas de coût OpenAI
- Cas complexes → Envoyés en `NEEDS_REVIEW`

---

### **Ajuster les Règles**

**`config/config.yaml`**

```yaml
rules:
  genres:
    whitelist:
      - Documentary
      - Animation
      - Family
      - Musical
      - Biography

    blacklist:
      - Adult
      - Erotic
      - Gore
      - Splatter

  limits:
    min_rating: 5.5          # Plus permissif
    max_episodes: 500        # Plus permissif pour séries
    max_seasons: 20
    min_popularity: 3.0

    # Nouveaux paramètres
    min_year: 1980           # Rejeter films trop anciens
    max_runtime: 180         # Minutes (pour films)
```

---

### **Changer le Modèle OpenAI**

```yaml
openai:
  model: "gpt-4o"  # Plus précis, mais + cher (~10x)
  temperature: 0.2  # Plus déterministe (0.0-1.0)
  max_tokens: 800   # Plus de détails dans les raisons
```

**Coûts estimés (par requête) :**
- `gpt-4o-mini` : $0.0002-0.0005
- `gpt-4o` : $0.002-0.005

---

## 🐛 Dépannage

### **Le webhook ne fonctionne pas**

```bash
# Vérifier les logs Overseerr
docker logs overseerr | grep webhook

# Vérifier les logs PlexStaffAI
docker logs PlexStaffAI | grep WEBHOOK

# Tester manuellement
curl -X POST http://localhost:5056/webhook/overseerr   -H "Authorization: Bearer ton-token"   -H "Content-Type: application/json"   -d '{"notification_type": "MEDIA_PENDING", "request": {"id": 999}}'
```

---

### **Erreur "Request not found in Overseerr"**

C'est normal ! Cela arrive si :
- La requête a été supprimée manuellement
- Elle a déjà été traitée par un autre système
- PlexStaffAI nettoie automatiquement ces cas

---

### **OpenAI ne répond pas**

```bash
# Vérifier la clé API
docker exec PlexStaffAI env | grep OPENAI

# Tester la connexion
curl https://api.openai.com/v1/models   -H "Authorization: Bearer ta-cle-openai"
```

---

### **TMDB enrichissement échoue**

```bash
# Vérifier la clé TMDB
docker exec PlexStaffAI env | grep TMDB

# Tester l'API
curl "https://api.themoviedb.org/3/movie/550?api_key=ta-cle-tmdb"
```

---

## 📈 Performance

**Tests réels (serveur Plex avec ~200 utilisateurs) :**

| Métrique | Avant (Scan 5min) | Après (Webhook) |
|----------|-------------------|-----------------|
| **Latence moyenne** | 2-5 minutes | < 1 seconde |
| **Coût OpenAI/mois** | $15-20 | $5-8 (rules-first) |
| **Taux auto-approve** | ~60% | ~75% |
| **Révisions manuelles** | ~40% | ~10% |

---

## 🛠️ Développement

### **Structure du projet**

```
PlexStaffAI/
├── app/
│   ├── main.py                 # Core FastAPI app + webhook
│   ├── config_loader.py        # Chargement config.yaml
│   ├── openai_moderator.py     # Intégration OpenAI
│   ├── rules_validator.py      # Règles strictes
│   ├── ml_feedback.py          # Apprentissage ML (futur)
│   └── utils/
├── static/
│   ├── index.html              # Dashboard web
│   ├── translations.js         # i18n FR/EN
│   └── favicon.svg
├── config/
│   ├── config.yaml             # Configuration règles
│   ├── moderation.db           # SQLite historique
│   └── feedback.db             # Feedback ML
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

### **Build local**

```bash
# Build
docker build -t plexstaffai:dev .

# Run
docker run -d   -p 5056:5056   -v ./config:/config   -e OVERSEERR_API_URL=http://overseerr:5055   -e OVERSEERR_API_KEY=xxx   -e TMDB_API_KEY=xxx   -e OPENAI_API_KEY=xxx   plexstaffai:dev
```

---

### **Tests**

```bash
# Tests unitaires (à implémenter)
pytest tests/

# Test webhook
curl -X POST http://localhost:5056/webhook/overseerr   -H "Content-Type: application/json"   -d @tests/fixtures/webhook_payload.json
```

---

## 🤝 Contribution

**Pull Requests bienvenues !**

**Idées de contributions :**
- [ ] Support Jellyseer
- [ ] Support Jellyfin webhooks
- [ ] Machine Learning auto-tuning des règles
- [ ] Support multi-serveurs Overseerr
- [ ] Notifications Discord/Slack
- [ ] Dashboard analytics avancé
- [ ] Export CSV des décisions
- [ ] API REST complète

---

## 📄 Licence

**MIT License**

---

## 🙏 Remerciements

- **Overseerr** : https://github.com/sct/overseerr
- **TMDB** : https://www.themoviedb.org
- **OpenAI** : https://openai.com
- **FastAPI** : https://fastapi.tiangolo.com

---

## 📞 Support

- **Issues** : https://github.com/malambert35/PlexStaffAI/issues
- **Discussions** : https://github.com/malambert35/PlexStaffAI/discussions
- **Discord** : [lien-serveur-discord]

---

## 🔮 Roadmap

**v1.8.0 (Q1 2026)**
- [ ] Support Jellyseer/Jellyfin
- [ ] Machine Learning auto-tuning
- [ ] Multi-serveurs Overseerr
- [ ] Notifications Discord/Slack

**v2.0.0 (Q2 2026)**
- [ ] Dashboard analytics avancé
- [ ] API REST complète
- [ ] Plugin system
- [ ] Web UI pour éditer config.yaml

---

## ⭐ Star History

Si ce projet t'aide, laisse une étoile ! ⭐

[![Star History Chart](https://api.star-history.com/svg?repos=malambert35/PlexStaffAI&type=Date)](https://star-history.com/#malambert35/PlexStaffAI&Date)

---

**Made with ❤️ for the Plex/Overseerr community**
