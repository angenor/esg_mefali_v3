# Quickstart — F14 Matching Projet ↔ Offre

## Prérequis

- Branche `feat/F14-matching-projet-offre` à jour avec `main`
- Toutes les features dépendantes mergées : F01, F06, F07, F13
- Backend venv activé : `source backend/venv/bin/activate`
- BDD PostgreSQL 16 + pgvector accessible

## Setup local

```bash
# 1. Migration
cd backend
alembic upgrade head

# 2. Vérifier les tables F14
psql -d esg_mefali -c "\d offer_matches"
psql -d esg_mefali -c "\d match_alerts_subscriptions"

# 3. Backfill (déjà fait par la migration 036, vérification)
psql -d esg_mefali -c "SELECT count(*) FROM offer_matches;"

# 4. Lancer le backend
uvicorn app.main:app --reload

# 5. Lancer le frontend
cd ../frontend
npm run dev
```

## Test manuel d'un parcours complet

### Scénario 1 — Voir mes offres compatibles

1. Créer un compte PME, login
2. Créer un profil entreprise (sector `agriculture`, country `SEN`)
3. Créer un projet (`/profile/projects/new`) :
   - Nom : « Panneaux solaires 5M FCFA »
   - Sector : agriculture
   - Target amount : 5 000 000 XOF
   - Location country : SEN
   - Financing structure : `subvention`
4. Naviguer vers `/profile/projects/[id]`
5. Section « Offres compatibles » → ≥ 1 MatchCard avec score décomposé visible

### Scénario 2 — Comparer 3 intermédiaires

1. Sur la page projet, cliquer « Comparer 3 intermédiaires pour GCF »
2. Page `/financing/compare/[fund_id]?project_id=X`
3. Table avec colonnes BOAD / UNDP / AFD
4. Lignes : Score global / Score fonds (commun) / Score intermédiaire / Frais / Délais / Documents / Track record / Bottleneck
5. Highlight gagnant par ligne
6. Cliquer « Démarrer ma candidature via BOAD » → redirige `/financing/offers/[offer_id]`

### Scénario 3 — Comprendre les critères manquants

1. Sur `/financing/offers/[offer_id]`, sélectionner le projet
2. Section « Mon score pour ce projet »
3. Cliquer un critère manquant
4. SourceModal F01 s'ouvre avec extrait + URL + badge « verified »

### Scénario 4 — Activer les alertes

1. Sur `/profile/projects/[id]`, toggle « Recevoir des alertes » → ON
2. Refresh → état persisté
3. Simuler un nouveau match :
   ```bash
   python -m scripts.notify_new_offer_matches
   ```
4. Vérifier `/dashboard` → Reminder F19 `kind='new_offer_alert'` visible

## Tests

```bash
# Backend (couverture F14)
cd backend
pytest tests/modules/financing/test_matching_service.py \
       tests/modules/financing/test_matching_router.py \
       tests/modules/financing/test_alerts_service.py \
       tests/graph/tools/test_matching_tools.py \
       tests/test_alembic_036.py \
       --cov=app.modules.financing.matching_service \
       --cov=app.modules.financing.alerts_service \
       --cov=app.models.offer_match \
       --cov=app.models.match_alert_subscription \
       --cov=app.graph.tools.matching_tools \
       --cov-report=term-missing

# Frontend
cd ../frontend
npm run test:unit -- matching

# E2E Playwright
npm run test:e2e -- F14-matching-projet-offre
```

## Round-trip Alembic

```bash
cd backend
alembic upgrade 036_offer_matches_and_alerts
alembic downgrade -1
alembic upgrade 036_offer_matches_and_alerts
```

## Crons à activer (F19)

```cron
# Recompute des matches stale (quotidien 02:00)
0 2 * * * cd /app/backend && python -m scripts.recompute_stale_matches

# Notify nouveaux matches (quotidien 08:00)
0 8 * * * cd /app/backend && python -m scripts.notify_new_offer_matches
```

## Variables d'environnement

Aucune nouvelle variable requise pour F14. Réutilise :
- `DATABASE_URL` (asyncpg)
- `OPENROUTER_API_KEY` (optionnel pour les tools — F14 est déterministe)

## Feature flag

`NUXT_PUBLIC_USE_OFFER_MATCH_VIEW=false` (par défaut MVP). Quand `true` (post-MVP), la page `/financing` utilise les `offer_matches` au lieu des `fund_matches` legacy.

## Troubleshooting

### Backfill skippé pour mon compte
→ Cause : aucun projet actif OU aucune offre `(fund_id, intermediary_id=DIRECT, version published)`.
→ Solution : créer un projet, puis `POST /api/projects/{id}/recompute-matches`.

### Pas de match alors que sector matche
→ Vérifier `Offer.publication_status='published'` ET `Offer.is_active=true`.
→ Vérifier `Fund.publication_status='published'`.

### RLS bloque l'admin
→ Vérifier que `current_setting('app.current_role')='ADMIN'` est bien set par `set_rls_context`.
→ Tester via `SELECT current_setting('app.current_role');` après login admin.

### Recompute infini
→ Vérifier la ContextVar `_recompute_in_progress` (anti-récursion).
