# 🚀 PlexStaffAI

**Modération IA automatique pour Overseerr** - Approuve ou rejette intelligemment les demandes de contenu avec OpenAI GPT-4o-mini, règles personnalisées et apprentissage machine.

[![Docker Hub](https://img.shields.io/docker/pulls/malambert35/plexstaffai)](https://hub.docker.com/r/malambert35/plexstaffai)
[![Version](https://img.shields.io/badge/version-1.6.0-blue)](https://github.com/malambert35/PlexStaffAI)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## ✨ Fonctionnalités

### 🤖 Modération IA Intelligente
- **OpenAI GPT-4o-mini** : Analyse contextuelle avancée du contenu
- **Smart Rules** : Règles personnalisables (genres, notes, utilisateurs, quotas)
- **ML Learning** : Apprentissage automatique basé sur vos décisions
- **Confiance ajustable** : Seuils de décision configurables

### ⏰ Automatisation
- **Auto-Scan** : Scanner automatique toutes les N minutes (configurable)
- **Scheduler intégré** : APScheduler pour tâches périodiques
- **Webhook-ready** : Réaction instantanée aux événements Overseerr

### 🎨 Interface Web Moderne
- **Dashboard bilingue** 🇫🇷 🇬🇧 : Interface en français et anglais
- **Stats en temps réel** : Graphiques et métriques de modération
- **Review Dashboard** : Interface de révision manuelle pour décisions incertaines
- **Historique complet** : Traçabilité de toutes les décisions

### 📊 Statistiques & Rapports
- Taux d'approbation
- Coûts OpenAI détaillés
- Performance par utilisateur
- Export CSV

---

## 🖼️ Captures d'Écran

### Dashboard Principal
![Dashboard](https://via.placeholder.com/800x400?text=Dashboard+PlexStaffAI)

### Review Dashboard
![Review](https://via.placeholder.com/800x400?text=Review+Dashboard)

### Statistiques OpenAI
![Stats](https://via.placeholder.com/800x400?text=OpenAI+Statistics)

---

## 🚀 Installation Rapide

### Prérequis
- Docker & Docker Compose
- Overseerr installé et configuré
- Clé API OpenAI
- (Optionnel) Clé API TMDB

### Docker Compose (Recommandé)

```yaml
version: '3.8'

services:
  plexstaffai:
    image: malambert35/plexstaffai:latest
    container_name: PlexStaffAI
    ports:
      - "5056:5056"
    volumes:
      - ./config:/config
      - ./logs:/logs
      - ./static:/app/static  # Pour modifications en temps réel
    environment:
      # OpenAI (REQUIS)
      - OPENAI_API_KEY=sk-your-openai-api-key

      # Overseerr (REQUIS)
      - OVERSEERR_API_URL=http://overseerr:5055
      - OVERSEERR_API_KEY=your-overseerr-api-key

      # TMDB (Optionnel mais recommandé)
      - TMDB_API_KEY=your-tmdb-api-key

      # Configuration Auto-Scan
      - SCAN_INTERVAL_MINUTES=1  # Scan toutes les 1 minute (1-60)

    restart: unless-stopped
    networks:
      - plex-network

networks:
  plex-network:
    external: true
```

### Démarrage

```bash
# 1. Créer les dossiers
mkdir -p config logs static

# 2. Créer docker-compose.yml (copier le contenu ci-dessus)
nano docker-compose.yml

# 3. Configurer les variables d'environnement
# Éditer docker-compose.yml avec vos clés API

# 4. Démarrer
docker-compose up -d

# 5. Vérifier les logs
docker logs -f PlexStaffAI

# 6. Accéder au dashboard
# http://votre-ip:5056
```

---

## ⚙️ Configuration

### Fichier `config/config.yaml`

Créez un fichier `config/config.yaml` pour personnaliser les règles :

```yaml
# PlexStaffAI Configuration v1.6.0

# Seuils de confiance AI
confidence:
  auto_approve: 0.85    # Approbation automatique si confiance >= 85%
  auto_reject: 0.15     # Rejet automatique si confiance <= 15%
  needs_review: true    # Envoyer en révision manuelle si entre les deux

# Règles de modération
rules:
  # Genres interdits
  blocked_genres:
    - "Horror"
    - "Adult"

  # Genres toujours approuvés
  allowed_genres:
    - "Documentary"
    - "Animation"

  # Note minimum TMDB
  min_rating: 6.0

  # Popularité minimum
  min_popularity: 10.0

  # Utilisateurs de confiance (auto-approve)
  trusted_users:
    - "admin"
    - "family_user"

  # Utilisateurs restreints (auto-reject)
  restricted_users:
    - "guest"

  # Quotas utilisateur (par semaine)
  user_quotas:
    default: 10
    trusted: 50
    restricted: 2

  # Limites de saison pour séries
  max_seasons: 10

# Apprentissage machine
ml:
  enabled: true
  feedback_weight: 0.3  # Influence du feedback manuel (0-1)

# Intégrations
integrations:
  radarr:
    enabled: false
    url: "http://radarr:7878"
    api_key: "your-radarr-api-key"

  sonarr:
    enabled: false
    url: "http://sonarr:8989"
    api_key: "your-sonarr-api-key"

# Notifications (à venir)
notifications:
  discord:
    enabled: false
    webhook_url: ""

  email:
    enabled: false
```

---

## 📖 Utilisation

### Interface Web

**Dashboard Principal** : `http://votre-ip:5056/`
- Statistiques en temps réel
- Bouton "Modérer Maintenant" pour scan manuel
- Sélecteur de langue 🇫🇷/🇬🇧 en haut à droite

**Review Dashboard** : `http://votre-ip:5056/review-dashboard`
- Réviser manuellement les décisions incertaines
- Approuver ou rejeter en un clic
- Feedback automatique pour l'apprentissage ML

**Historique** : `http://votre-ip:5056/history`
- Toutes les décisions passées
- Filtres par type de décision
- Export CSV

**Rapport Complet** : `http://votre-ip:5056/staff/report`
- Statistiques détaillées
- Performance par utilisateur
- Activité récente

**Stats OpenAI** : `http://votre-ip:5056/staff/openai-stats`
- Coûts détaillés par modèle
- Consommation de tokens
- Appels récents

---

## 🔧 API Endpoints

### Documentation Interactive
`http://votre-ip:5056/docs` - Swagger UI

### Endpoints Principaux

```bash
# Health Check
GET /health

# Modérer toutes les requests en attente
POST /moderate

# Statistiques
GET /stats

# Historique
GET /history

# Review Dashboard
GET /review-dashboard
POST /staff/review/{review_id}/approve
POST /staff/review/{review_id}/reject

# OpenAI Stats
GET /staff/openai-stats

# Rapport détaillé
GET /staff/report
```

---

## 🎯 Workflow de Modération

```
┌─────────────────────────┐
│  Request Overseerr      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  PlexStaffAI Auto-Scan  │ ← Toutes les N minutes
│  (ou Webhook)           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Enrichissement TMDB    │ ← Métadonnées complètes
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Validation Rules       │ ← Genres, quotas, users
└───────────┬─────────────┘
            │
     ┌──────┴──────┐
     │ Rules match?│
     └──────┬──────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌─────────┐   ┌─────────────────┐
│ APPROVE │   │ Analyse OpenAI  │
│ REJECT  │   │ (GPT-4o-mini)   │
└─────────┘   └────────┬────────┘
                       │
              ┌────────┴────────┐
              │ Confiance >= 85%│
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌────────┐  ┌─────────────┐ ┌────────┐
    │APPROVE │  │NEEDS_REVIEW │ │REJECT  │
    └────────┘  └──────┬──────┘ └────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Review Dashboard│
              │ (Staff Manual)  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ ML Feedback DB  │ ← Amélioration continue
              └─────────────────┘
```

---

## 🌍 Traduction

PlexStaffAI supporte le français et l'anglais :

- **Français** 🇫🇷 (par défaut)
- **English** 🇬🇧

**Changer de langue** : Cliquez sur le sélecteur en haut à droite de n'importe quelle page.

Le choix est sauvegardé dans le navigateur (localStorage).

---

## 🛠️ Développement

### Structure du Projet

```
PlexStaffAI/
├── app/
│   ├── main.py                  # FastAPI app principale
│   ├── config_loader.py         # Gestion config YAML
│   ├── openai_moderator.py      # Intégration OpenAI
│   ├── ml_feedback.py           # Système ML learning
│   └── rules_validator.py       # Validation des règles
├── static/
│   ├── index.html               # Dashboard principal
│   ├── translations.js          # Système i18n FR/EN
│   └── favicon.svg              # Logo
├── config/
│   ├── config.yaml              # Configuration utilisateur
│   ├── moderation.db            # Base de données SQLite
│   └── feedback.db              # Base de données ML
├── logs/
│   └── app.log                  # Logs application
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### Build Local

```bash
# Clone
git clone https://github.com/malambert35/PlexStaffAI.git
cd PlexStaffAI

# Build image
docker build -t plexstaffai:dev .

# Run
docker run -p 5056:5056 \
  -e OPENAI_API_KEY=sk-xxx \
  -e OVERSEERR_API_URL=http://overseerr:5055 \
  -e OVERSEERR_API_KEY=xxx \
  -v $(pwd)/config:/config \
  plexstaffai:dev
```

### Dépendances

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
pyyaml==6.0.1
scikit-learn==1.4.0
numpy==1.26.3
openai==1.10.0
APScheduler==3.10.4
```

---

## 📊 Variables d'Environnement

| Variable | Requis | Par Défaut | Description |
|----------|--------|------------|-------------|
| `OPENAI_API_KEY` | ✅ Oui | - | Clé API OpenAI |
| `OVERSEERR_API_URL` | ✅ Oui | `http://overseerr:5055` | URL de l'API Overseerr |
| `OVERSEERR_API_KEY` | ✅ Oui | - | Clé API Overseerr |
| `TMDB_API_KEY` | ⚠️ Recommandé | - | Clé API TMDB (enrichissement) |
| `SCAN_INTERVAL_MINUTES` | ❌ Non | `1` | Intervalle auto-scan (1-60 min) |

---

## 🤝 Contribution

Les contributions sont les bienvenues ! 

1. Fork le projet
2. Créez une branche (`git checkout -b feature/amazing-feature`)
3. Committez vos changements (`git commit -m 'feat: add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrez une Pull Request

---

## 📝 Roadmap

### v1.7.0 (À venir)
- [ ] Notifications Discord/Slack
- [ ] Webhooks Overseerr natifs
- [ ] Graphiques de performance
- [ ] Export PDF des rapports
- [ ] Support multi-langues (ES, DE, IT)

### v2.0.0 (Future)
- [ ] Interface admin avancée
- [ ] Règles basées sur le temps (ex: "approuver automatiquement le vendredi soir")
- [ ] Intégration Plex directe (statistiques de visionnage)
- [ ] API publique avec authentification
- [ ] Mode "Learning" initial (observation sans action)

---

## 🐛 Problèmes Connus

### Le bouton de langue ne s'affiche pas
**Solution** : Ajoutez le volume `static` dans `docker-compose.yml`:
```yaml
volumes:
  - ./static:/app/static
```
Puis `docker-compose restart`

### Auto-scan ne fonctionne pas
**Solution** : Vérifiez que `APScheduler` est installé. Rebuild l'image :
```bash
docker build --no-cache -t malambert35/plexstaffai:latest .
```

### Erreur "404 Not Found" sur les pages
**Solution** : Vérifiez que les routes HTML existent dans `main.py`. Voir la documentation.

---

## 📄 Licence

MIT License - Voir [LICENSE](LICENSE) pour plus de détails.

---

## 👨‍💻 Auteur

**Marc-Antoine Lambert**
- GitHub: [@malambert35](https://github.com/malambert35)
- Docker Hub: [malambert35/plexstaffai](https://hub.docker.com/r/malambert35/plexstaffai)

---

## 🙏 Remerciements

- [OpenAI](https://openai.com) pour GPT-4o-mini
- [Overseerr](https://overseerr.dev) pour l'excellente API
- [TMDB](https://www.themoviedb.org) pour les métadonnées
- [FastAPI](https://fastapi.tiangolo.com) pour le framework web
- [HTMX](https://htmx.org) pour l'interactivité sans JS complexe
- Anthropic Claude Sonnet 4.5 pour l'assistance au développement

---

## 💬 Support

- **Issues** : [GitHub Issues](https://github.com/malambert35/PlexStaffAI/issues)
- **Discussions** : [GitHub Discussions](https://github.com/malambert35/PlexStaffAI/discussions)
- **Discord** : *(à venir)*

---

**⭐ N'oubliez pas de mettre une étoile sur GitHub si vous aimez le projet !**

```
   ____  _           _____ _          __  __    _    ___ 
  |  _ \| | _____  _/ ____| |_ __ _ / _|/ _|  / \  |_ _|
  | |_) | |/ _ \ \/ / (___ | __/ _` | |_| |_  / _ \  | | 
  |  __/| |  __/>  < \___ \| || (_| |  _|  _|/ ___ \ | | 
  |_|   |_|\___/_/\_\____) |\__\__,_|_| |_| /_/   \_\___|
                    |____/                                
```

**Modération intelligente pour votre serveur Plex/Overseerr** 🚀🤖
