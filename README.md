# ESG Mefali

Plateforme conversationnelle IA qui democratise l'acces a la finance durable pour les PME africaines francophones.

## Prerequis

- Docker et Docker Compose
- Git

## Demarrage rapide

```bash
# 1. Cloner le projet
git clone <repo-url>
cd esg_mefali

# 2. Copier la configuration
cp .env.example .env
# Editer .env avec vos cles (OPENROUTER_API_KEY obligatoire pour le chat IA)

# 3. Lancer les 3 services
make dev
```

## Acces

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

## Premier parcours

1. Ouvrir http://localhost:3000
2. Cliquer sur "S'inscrire"
3. Remplir le formulaire (email, mot de passe, nom, entreprise)
4. Se connecter avec les identifiants crees
5. Utiliser le panneau de chat IA a droite pour envoyer un message

## Commandes

```bash
make dev          # Lancer en mode developpement
make build        # Build de production
make migrate      # Executer les migrations Alembic
make test         # Lancer tous les tests
make test-back    # Tests backend uniquement
make test-front   # Tests frontend uniquement
make down         # Arreter les services
make logs         # Voir les logs
make clean        # Arreter et supprimer les volumes
```

## Developpement local (sans Docker)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Base de donnees

PostgreSQL 16 avec pgvector doit etre installe localement ou via Docker :

```bash
docker compose up postgres -d
```

## Stack technique

- **Frontend** : Nuxt 4, Pinia, TailwindCSS 4, GSAP, Chart.js
- **Backend** : FastAPI, SQLAlchemy async, LangGraph, LangChain
- **LLM** : Claude (Anthropic) via OpenRouter
- **BDD** : PostgreSQL 16 + pgvector
- **Infra** : Docker Compose

## Variables d'environnement

Voir [.env.example](.env.example) pour la liste complete des variables.
# esg_mefali_v3
