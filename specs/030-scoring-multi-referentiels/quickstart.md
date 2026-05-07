# Quickstart F13 — Scoring ESG Multi-Référentiels

**Date** : 2026-05-07
**Spec** : [spec.md](./spec.md)
**Plan** : [plan.md](./plan.md)
**Data Model** : [data-model.md](./data-model.md)

## Prérequis

- F01 livré (catalogue Sources + Indicators + Referentials)
- F02 livré (multi-tenant + RLS + roles)
- F03 livré (audit log)
- F04 livré (versioning + Money typed)
- F05 livré (esg_assessments + indicator_values)
- F06 livré (PDF reports)
- F07 livré (Offer = Fonds × Intermédiaire)
- F11 livré (reminders)
- F12 livré (tools LangChain + tool_call_logs)
- PostgreSQL 16 + pgvector lancé localement (`docker compose up postgres -d`)
- Backend venv activé (`source backend/venv/bin/activate`)
- Frontend npm packages installés (`cd frontend && npm install`)

## 1. Lancer la migration F13

```bash
cd backend && source venv/bin/activate
alembic upgrade head
```

La migration `030_create_referential_scores` :
1. Crée la table `referential_scores` avec ses index et RLS.
2. Crée le type ENUM `referential_score_computed_by_enum`.
3. Seed (idempotent `ON CONFLICT DO NOTHING`) les 5 référentiels MVP : Mefali (UUID stable `00000000-0000-0000-0000-000000000001`), GCF, IFC PS, BOAD ESS, GRI 2021.
4. Backfill : pour chaque `EsgAssessment` existante (`overall_score IS NOT NULL`), crée une ligne `referential_scores` avec `referential_id=MEFALI_REFERENTIAL_UUID`, `referential_version='1.0.0'`, `computed_by='auto'`, `coverage_rate=0` (legacy, pas de tracking pré-F13).

### Vérifier le succès

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM referential_scores WHERE superseded_by IS NULL;"
# Doit être >= COUNT(esg_assessments WHERE overall_score IS NOT NULL)

psql $DATABASE_URL -c "SELECT code, name, version FROM referentials WHERE code IN ('mefali', 'gcf', 'ifc_ps', 'boad_ess', 'gri_2021') ORDER BY code;"
# Doit lister les 5 référentiels MVP
```

### Tester la réversibilité

```bash
alembic downgrade -1  # supprime referential_scores + ENUM
alembic upgrade head  # recrée + re-backfill
```

Idempotent.

## 2. Vérifier les seeds des indicateurs liés (dépendance F01)

```bash
psql $DATABASE_URL -c "
SELECT r.code, COUNT(ri.indicator_id) AS nb_indicators
FROM referentials r
LEFT JOIN referential_indicators ri ON ri.referential_id = r.id
WHERE r.code IN ('mefali', 'gcf', 'ifc_ps', 'boad_ess', 'gri_2021')
GROUP BY r.code
ORDER BY r.code;
"
```

Si un référentiel a 0 indicateur, le calcul retournera `coverage_rate=0` et l'UI cachera la card. Ce comportement est attendu si F01 n'a pas encore livré tous les indicateurs.

## 3. Tester le service `compute_all_referential_scores` via pytest

```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_multi_referential_service.py -v
pytest tests/integration/test_referential_scores_router.py -v
pytest tests/migrations/test_alembic_030.py -v
pytest tests/security/test_referential_scores_rls.py -v
```

Couverture cible : ≥ 80 %.

## 4. Tester le calcul via curl (avec backend lancé)

```bash
# Démarrer le backend
cd backend && source venv/bin/activate
uvicorn app.main:app --port 8000 &

# Authentification (récupérer un token JWT)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "test@mefali.app", "password": "test1234"}' \
    | jq -r '.access_token')

# Récupérer un assessment_id (PME finalisée existante)
ASSESSMENT_ID=$(curl -s http://localhost:8000/api/esg/assessments \
    -H "Authorization: Bearer $TOKEN" \
    | jq -r '.assessments[0].id')

# Lister les scores courants
curl -s http://localhost:8000/api/esg/assessments/$ASSESSMENT_ID/referential-scores \
    -H "Authorization: Bearer $TOKEN" \
    | jq '.scores | map({code: .referential_code, score: .overall_score, coverage: .coverage_rate})'

# Recalculer le score IFC ciblé
IFC_ID=$(psql $DATABASE_URL -t -c "SELECT id FROM referentials WHERE code='ifc_ps';" | xargs)
curl -s -X POST "http://localhost:8000/api/esg/assessments/$ASSESSMENT_ID/recompute-score?referentiel_id=$IFC_ID" \
    -H "Authorization: Bearer $TOKEN" \
    | jq

# Polling 2s jusqu'à voir computed_at récent
sleep 5
curl -s http://localhost:8000/api/esg/assessments/$ASSESSMENT_ID/referential-scores \
    -H "Authorization: Bearer $TOKEN" \
    | jq '.scores | map(select(.referential_code == "ifc_ps"))'
```

## 5. Générer un PDF multi-référentiels via curl

```bash
# Body multi-référentiels avec annexe sources
curl -s -X POST http://localhost:8000/api/reports/esg/$ASSESSMENT_ID/generate \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"referentials": ["mefali", "ifc_ps"], "include_appendix_sources": true}' \
    | jq

# Récupérer report_id
REPORT_ID=$(curl -s -X POST http://localhost:8000/api/reports/esg/$ASSESSMENT_ID/generate \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"referentials": ["mefali", "ifc_ps"], "include_appendix_sources": true}' \
    | jq -r '.report_id')

# Polling jusqu'à PDF prêt
sleep 30
curl -L -o /tmp/esg_report_F13.pdf \
    http://localhost:8000/api/reports/$REPORT_ID/download \
    -H "Authorization: Bearer $TOKEN"

# Ouvrir le PDF
open /tmp/esg_report_F13.pdf  # macOS
# ou: xdg-open /tmp/esg_report_F13.pdf  # Linux
```

Vérifications dans le PDF :
- ☐ Page de garde avec score Mefali principal
- ☐ Section dédiée « Selon référentiel ESG Mefali »
- ☐ Section dédiée « Selon référentiel IFC Performance Standards » avec radar 8 piliers
- ☐ Tableau comparatif `indicateur × référentiel`
- ☐ Annexe « Sources et références » avec URLs cliquables
- ☐ Bannière « Rapport préliminaire » si `coverage_rate < 0.5` pour un référentiel

## 6. Tester les 3 tools LangChain via le chat interactif local

Lancer le frontend :

```bash
cd frontend && npm run dev
```

Ouvrir `http://localhost:3000/chat` et envoyer ces messages :

1. **Test `compare_referentials`** :
   ```
   Compare-moi mes scores selon Mefali et IFC PS pour mon évaluation actuelle.
   ```
   Le chat doit appeler `compare_referentials` et formuler une réponse en français avec accents.

2. **Test `recompute_score`** :
   ```
   Recalcule mon score IFC.
   ```
   Le chat doit appeler `recompute_score` et répondre « Recalcul IFC en cours… ».

3. **Test `finalize_esg_assessment`** :
   ```
   Finalise mon évaluation et calcule les scores Mefali, IFC et BOAD.
   ```
   Le chat doit appeler `finalize_esg_assessment(referentials_to_compute=["mefali", "ifc_ps", "boad_ess"])`.

Vérifier les logs des tool calls :
```bash
psql $DATABASE_URL -c "
SELECT tool_name, success, duration_ms, called_at
FROM tool_call_logs
WHERE tool_name IN ('finalize_esg_assessment', 'recompute_score', 'compare_referentials')
ORDER BY called_at DESC LIMIT 10;
"
```

## 7. Exécuter le cron `check_referential_versions_evolution.py` manuellement

```bash
cd backend && source venv/bin/activate

# Simuler une évolution de version : modifier referentials.version pour IFC PS
psql $DATABASE_URL -c "UPDATE referentials SET version='1.1.0', updated_at=NOW() WHERE code='ifc_ps';"

# Lancer le cron
python scripts/check_referential_versions_evolution.py

# Vérifier qu'un reminder a été créé pour chaque PME concernée
psql $DATABASE_URL -c "
SELECT r.kind, r.metadata, r.account_id, r.created_at
FROM reminders r
WHERE r.kind = 'referential_version_evolved'
ORDER BY r.created_at DESC LIMIT 5;
"

# Vérifier l'idempotence : 2ème exécution ne crée pas de doublon
python scripts/check_referential_versions_evolution.py
psql $DATABASE_URL -c "SELECT COUNT(*) FROM reminders WHERE kind='referential_version_evolved';"
# Le compte ne doit pas avoir augmenté
```

## 8. Tester les RLS multi-tenant (SC-009)

Créer 2 comptes A et B avec leurs assessments :

```bash
# Compte A
TOKEN_A=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"email":"a@test.app","password":"test1234"}' | jq -r '.access_token')
ASSESSMENT_A_ID=$(curl -s http://localhost:8000/api/esg/assessments -H "Authorization: Bearer $TOKEN_A" | jq -r '.assessments[0].id')

# Compte B
TOKEN_B=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"email":"b@test.app","password":"test1234"}' | jq -r '.access_token')

# B tente d'accéder à l'assessment de A
RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null \
    http://localhost:8000/api/esg/assessments/$ASSESSMENT_A_ID/referential-scores \
    -H "Authorization: Bearer $TOKEN_B")

echo "HTTP code (must be 404): $RESPONSE"
```

Aussi via SQL direct (simulation utilisateur DB pour vérifier les RLS) :

```bash
psql $DATABASE_URL <<EOF
-- Sessionner pour le compte B
SET LOCAL app.current_account_id = '<account_b_uuid>';

-- Tenter de lire les scores de A : doit retourner 0 lignes
SELECT COUNT(*) FROM referential_scores WHERE assessment_id = '$ASSESSMENT_A_ID';
EOF
```

## 9. Lancer les tests E2E Playwright

```bash
# Terminal 1 : démarrer le backend
cd backend && source venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 2 : démarrer le frontend
cd frontend && npm run dev

# Terminal 3 : lancer les E2E F13
cd frontend
npx playwright test tests/e2e/F13-scoring-multi-referentiels.spec.ts --reporter=html
```

3 scénarios attendus :
1. **US1** — PME bascule entre référentiels et découvre les écarts (sélecteur, badge coverage, sources cliquables).
2. **US2** — PME consulte une Offre et voit son éligibilité réelle avec goulot d'étranglement (dual view).
3. **US3** — PME génère un rapport PDF avec sélection multi-référentiels.

Artefacts dans `frontend/playwright-report/index.html` et `frontend/test-results/`.

## 10. Couverture des tests

```bash
# Backend
cd backend && source venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html
# Couverture cible ≥ 80 % sur multi_referential_service, refactor service, refactor node, esg_tools, refactor reports

# Frontend
cd frontend
npm run test -- --coverage
# Couverture cible ≥ 80 % sur les 4 nouveaux composants + composable + 2 pages refactorées
```

## 11. Troubleshooting

### Migration `030_create_referential_scores` échoue avec « relation referentials does not exist »

F01 n'est pas livré ou pas mergé. Vérifier `alembic heads` :

```bash
alembic heads
# Doit montrer 028_offers_and_enrich (juste avant F13)

# Si F01 (020_create_sources_catalog) manque :
git log --oneline --all | grep 020_create_sources_catalog
```

### `compute_all_referential_scores` retourne `coverage_rate=0` pour tous les référentiels

Pas d'`IndicatorValues` saisis pour cet assessment, OU les `referential_indicators` (F01) ne sont pas seedés. Vérifier :

```bash
psql $DATABASE_URL -c "
SELECT iv.indicator_id, iv.value, ri.referential_id, r.code
FROM indicator_values iv
LEFT JOIN referential_indicators ri ON ri.indicator_id = iv.indicator_id
LEFT JOIN referentials r ON r.id = ri.referential_id
WHERE iv.assessment_id = '$ASSESSMENT_ID'
LIMIT 20;
"
```

### Les RLS bloquent même pour un super-admin

Vérifier que la session active `app.bypass_rls=true` :

```sql
SET LOCAL app.bypass_rls = 'true';
```

Le helper `get_db_session_with_admin_bypass` (F02) le fait automatiquement pour les endpoints admin.

### Background task perdu au redéploiement

C'est attendu en MVP (cf. Décision 3 de research.md). L'UI affiche un toast « Recalcul perdu, réessayer » après 30s de polling sans complétion. Post-MVP : migration vers Redis+Celery.

## 12. Référence rapide des codes de référentiels

| Code | Nom complet | Threshold | min_coverage_for_pdf |
|------|-------------|-----------|----------------------|
| `mefali` | ESG Mefali | 50.0 | 0.5 |
| `gcf` | Green Climate Fund | 60.0 | 0.5 |
| `ifc_ps` | IFC Performance Standards 2012 | 60.0 | 0.5 |
| `boad_ess` | BOAD ESS | 55.0 | 0.5 |
| `gri_2021` | GRI 2021 | 50.0 | 0.5 |
| `odd` (post-MVP via F09) | Objectifs de Développement Durable | 50.0 | 0.5 |
