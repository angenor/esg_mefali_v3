# Quickstart — F17 Carbone Mix UEMOA + Facteurs Sourcés

Date : 2026-05-07
Branche : `feat/F17-carbone-mix-uemoa-source` (alias SpecKit `024-carbone-mix-uemoa-source`)

## Objectif du quickstart

Permettre à un développeur fraîchement assigné à F17 de prendre en main la feature, valider l'environnement, exécuter la migration, lancer les tests, et démarrer le développement.

## Prérequis

- Python 3.12 + venv backend (`source backend/venv/bin/activate`)
- Node 20+ + npm (frontend Nuxt 4)
- PostgreSQL 16 + pgvector (via Docker Compose : `docker compose up postgres -d`)
- F01 (sourçage catalogue) et F02 (multi-tenant) mergés sur `main`
- Variables d'environnement standard ESG Mefali (`backend/.env` configuré)

## 1. Synchronisation et branche

```bash
cd /Users/mac/Documents/projets/2025/esg_mefali_v3
git fetch origin
git checkout feat/F17-carbone-mix-uemoa-source
git pull --ff-only  # si la branche existe déjà sur le remote
```

## 2. Activation venv backend

```bash
cd backend
source venv/bin/activate
which python  # doit pointer vers backend/venv/bin/python
pip install -r requirements.txt  # si besoin
```

## 3. État de la base avant migration

Vérifier que F01 et F02 sont bien appliquées :

```bash
cd backend
alembic current  # doit afficher la révision F01 (020_create_sources_catalog) ou plus récente
```

Vérifier que la table `emission_factors` existe avec les colonnes F01 :

```bash
docker exec -it esg_postgres psql -U postgres -d esg_mefali -c "\d+ emission_factors"
```

Attendu : colonnes `id`, `code`, `label`, `category`, `country`, `value`, `unit`, `source_id`, `publication_status`, `account_id`, `created_by_user_id`, `created_at`, `updated_at`.

## 4. Application de la migration F17

```bash
cd backend
alembic upgrade head
```

Comportement attendu :
- Ajout colonne `year: Integer NOT NULL` (default 2024 pour les lignes existantes F01)
- Ajout index composite `idx_emission_factors_lookup`
- Ajout contrainte `UNIQUE (category, country, year)`
- Seed ~50 facteurs (idempotent)
- Ajout `source_id` + `factor_id` à `carbon_emission_entries` (NULL puis backfill puis NOT NULL)

Vérifier :

```bash
docker exec -it esg_postgres psql -U postgres -d esg_mefali -c "SELECT COUNT(*) FROM emission_factors WHERE category = 'electricity'"
# Attendu : 8 (les 8 pays UEMOA)

docker exec -it esg_postgres psql -U postgres -d esg_mefali -c "SELECT COUNT(*) FROM carbon_emission_entries WHERE source_id IS NULL"
# Attendu : 0 (toutes les entries historiques ont été backfillées)
```

## 5. Test de la migration en cycle complet

```bash
cd backend
alembic downgrade -1
alembic upgrade head
```

Doit passer sans erreur. Aucune donnée perdue.

## 6. Tests backend

```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_factor_service.py tests/unit/test_seed_factors.py tests/unit/test_carbon_tools_f17.py tests/integration/test_carbon_pipeline_f17.py tests/migrations/test_alembic_f17.py -v
```

Couverture attendue : ≥ 80 % sur les fichiers ajoutés/modifiés (mesurée par pytest-cov).

```bash
pytest tests/ -v --cov=app/modules/carbon --cov=app/graph/tools/carbon_tools.py --cov-report=term-missing
```

## 7. Démarrage backend local

```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API joinable sur `http://localhost:8000`.

## 8. Tests frontend

```bash
cd frontend
npm install  # si besoin
npm run test -- --coverage
```

Attendu : `EmissionFactorBadge.spec.ts` passe avec couverture ≥ 80 %.

## 9. Démarrage frontend local

```bash
cd frontend
npm run dev
```

UI joinable sur `http://localhost:3000`. Naviguer vers `/carbon/results` pour voir le composant `<EmissionFactorBadge>` en action (créer un bilan via le chat d'abord).

## 10. Tests E2E Playwright

```bash
cd frontend
npx playwright install --with-deps  # première fois seulement
npx playwright test tests/e2e/F17-carbone-mix-uemoa-source.spec.ts --reporter=html
```

Scénarios couverts (4) :
1. **CI électricité** : profil PME en CI, saisie 1000 kWh → factor `electricity_ci_2024` (~0.456) appliqué ; tCO2e = 0.456 ; badge avec source ADEME/IEA cliquable.
2. **SN électricité** : profil PME en SN, saisie 1000 kWh → factor `electricity_sn_2024` distinct ; tCO2e ≠ scénario 1.
3. **Achats ciment** : saisie « 50 tonnes ciment » → factor `purchases_cement_global_2024` (~0.9 kgCO2e/kg) ; tCO2e = 45 ; catégorie « Achats » apparaît dans la ventilation.
4. **SourceLink cliquable** : sur `/carbon/results`, le badge `<EmissionFactorBadge>` est visible, le pictogramme source est cliquable, la modale `<SourceModal>` s'ouvre avec publisher/page/date/URL.

Artefacts de test : `frontend/playwright-report/index.html`.

## 11. Vérification du seed admin (optionnel)

```bash
# Récupérer un token admin (via /auth/login + ADMIN seedé)
curl -X POST http://localhost:8000/api/admin/carbon/seed-factors \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Attendu : `{"inserted": 0, "skipped": 50, "total_in_db": 50, "sources_used": [...]}` (déjà appliqué par la migration).

## 12. Validation conversation chat (manuel)

1. Démarrer backend + frontend.
2. Se connecter avec un compte PME ayant `country = "CI"` dans son profil.
3. Démarrer une conversation, saisir « Je veux faire un bilan carbone 2026 ».
4. Le LLM appelle `create_carbon_assessment(year=2026)`.
5. Saisir « J'ai consommé 15 000 kWh d'électricité cette année ».
6. Le LLM appelle `save_emission_entry(category='energy', quantity=15000, unit='kWh', subcategory='electricity', ...)`.
7. Le LLM répond : « Empreinte calculée : 6,84 tCO2e (15 000 kWh × 0,456 kgCO2e/kWh) [Source ADEME/IEA] ».
8. Cliquer sur le picto Source → modale ouverte → publisher = ADEME ou IEA, page = X.
9. Saisir « J'ai aussi acheté 10 tonnes de ciment ».
10. Le LLM appelle `save_emission_entry(category='purchases', quantity=10, unit='t', subcategory='purchases_cement', ...)`.
11. Le LLM ajoute 9 tCO2e au total (10 000 kg × 0,9 kgCO2e/kg / 1000).
12. Naviguer vers `/carbon/results` → ventilation par catégorie inclut Énergie et Achats, badges cliquables sur chaque facteur.

## 13. Rollback en cas de problème

```bash
cd backend && source venv/bin/activate
alembic downgrade -1
git stash || git reset --hard HEAD  # si besoin
```

La migration F17 est réversible. Les données legacy (`source_description`) sont conservées.

## 14. Liens utiles

- Spec : [spec.md](./spec.md)
- Plan technique : [plan.md](./plan.md)
- Recherche Phase 0 : [research.md](./research.md)
- Modèle de données : [data-model.md](./data-model.md)
- Contrats : [contracts/carbon-emission-factor.md](./contracts/carbon-emission-factor.md)
- Tasks (Phase 2) : [tasks.md](./tasks.md) (généré par `/speckit.tasks`)
