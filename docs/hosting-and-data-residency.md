# Hébergement & résidence des données — ESG Mefali

> Document interne — Version 1.0 — Mise à jour : 2026-05-07

## 1. Provider d'hébergement (à confirmer en production)

| Critère | Choix MVP | Justification |
|---------|-----------|---------------|
| Provider candidat | OVH / Scaleway / Africa Data Centres | À arbitrer avant déploiement prod |
| Région privilégiée | Europe (FR/EU) ou Afrique de l'Ouest (CI/SN) | **PAS USA** |
| Type de service | VPS dédié + S3-compatible storage | Cohérent avec stack Docker Compose |
| SLA cible | 99.5 % | Acceptable MVP |

### 1.1 Région — Décision

La région d'hébergement DOIT être **soit l'Union Européenne** (RGPD natif)
**soit l'Afrique de l'Ouest** (UEMOA + lois nationales). En aucun cas les
données ne seront hébergées sur un territoire soumis au CLOUD Act US.

### 1.2 Migration provider

Tout changement de provider sera tracé dans la section « Historique »
de ce document avec la date, le motif et les conditions DPA renégociées.

## 2. Chiffrement at-rest

| Composant | Méthode |
|-----------|---------|
| Volumes BDD PostgreSQL | AES-256 (offert par le provider, transparent) |
| Stockage fichiers (`/uploads/`) | AES-256 (filesystem encrypted ou S3 SSE) |
| Backups quotidiens | AES-256, rotation 30 jours |
| Logs applicatifs | AES-256 si nominatifs (sinon chiffrés au transit only) |

## 3. Chiffrement en transit

| Canal | Méthode |
|-------|---------|
| Frontend ↔ Backend | TLS 1.3 (Let's Encrypt ou wildcard du provider) |
| Backend ↔ PostgreSQL | TLS 1.3 |
| Backend ↔ OpenRouter (LLM) | TLS 1.3, API key dans `OPENROUTER_API_KEY` env |
| Backend ↔ exchangerate-api.com | TLS 1.3, API key dans `EXCHANGERATE_API_KEY` env |
| Backend ↔ SMTP | STARTTLS si `SMTP_USER` configuré |

## 4. Sous-traitants (DPA requis)

| Fournisseur | Service | Région | DPA |
|-------------|---------|--------|-----|
| OpenRouter (Anthropic / Claude API) | LLM inference | USA + multi-region | DPA avec clause européenne, à confirmer pour résidents UE/UEMOA |
| exchangerate-api.com | Taux de change USD pivot | USA | DPA, données non personnelles uniquement |
| Provider d'hébergement | Infrastructure (VPS, BDD, S3) | UE ou Afrique Ouest (PAS USA) | DPA standard du provider |
| Provider SMTP (TBD) | Envoi emails transactionnels | UE | DPA + DPO du provider |

### 4.1 Statut DPA OpenRouter

OpenRouter route les requêtes vers Anthropic (Claude). En production, vérifier :
- Le DPA OpenRouter accepte-t-il un transit limité à des régions UE
  (proxy européen) ?
- Anthropic propose-t-il un endpoint EU isolé (clause SCC européenne) ?

Tant que ce point n'est pas tranché : **les données envoyées à
OpenRouter sont anonymisées au maximum** (pas de PII directe — uniquement
des montants, secteurs, scores, textes ESG).

### 4.2 Pas de cookies analytics tiers

ESG Mefali n'utilise pas Google Analytics, Hotjar, Facebook Pixel, etc.
Aucune donnée comportementale n'est partagée avec des tiers analytiques.
Aucun banner cookies n'est requis.

## 5. Variables d'environnement requises

```bash
# Application
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
SECRET_KEY=<random-256-bit>
ENV=production

# F05 — RGPD
EXPORT_URL_SIGNING_KEY=<random-256-bit>     # défaut: secret_key
PRIVACY_POLICY_VERSION=v1.0
ACCOUNT_DELETION_GRACE_PERIOD_DAYS=30

# SMTP (optionnel — fallback stub si vide)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=no-reply@esg-mefali.com
SMTP_PASSWORD=<app-password>
EMAIL_FROM=no-reply@esg-mefali.com

# LLM
OPENROUTER_API_KEY=<key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-sonnet-4-20250514

# Currency
EXCHANGERATE_API_KEY=<key>

# F08 — Attestations Ed25519
ATTESTATION_PRIVATE_KEY_PEM=<PEM-PKCS8>
ATTESTATION_PUBLIC_KEY_ID=v1
ATTESTATION_VERIFICATION_BASE_URL=https://app.esg-mefali.com
```

## 6. Backups & restauration

| Critère | Politique |
|---------|-----------|
| Fréquence | Quotidienne (BDD), hebdo (uploads) |
| Rétention | 30 jours BDD, 90 jours uploads |
| Chiffrement | AES-256 |
| Test restauration | Trimestriel |
| RPO (Recovery Point Objective) | 24h max |
| RTO (Recovery Time Objective) | 4h max |

## 7. Suppression effective lors d'une purge RGPD

Lorsqu'un compte est purgé (cron `purge_scheduled_deletions.py`) :

1. Toutes les rows `account_id` sont DELETE.
2. Tous les fichiers sous `/uploads/{account_id}/` sont supprimés.
3. Les refresh tokens sont DELETE.
4. L'audit_log est anonymisé via UPDATE en place
   (`user_id=NULL, account_id=NULL, payload filtré`).
5. Les **backups antérieurs à la purge** contiennent encore les données
   purgées, mais leur durée de rétention max est de 30 jours (BDD) ou
   90 jours (uploads). Au-delà, les backups expirent et sont écrasés.
6. Les **logs applicatifs** sont rotés tous les 7 jours sur disque, 30 jours
   sur stockage froid, puis supprimés.

## 8. Historique des versions

| Version | Date | Auteur | Changements |
|---------|------|--------|-------------|
| 1.0 | 2026-05-07 | Équipe ESG Mefali | Version initiale (F05 MVP) |
