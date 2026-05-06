# Quickstart — F01 Fondations Sourçage et Catalogue Source

**Feature** : F01
**Date** : 2026-05-06

> Procédure pas-à-pas pour exécuter F01 localement et vérifier que les principaux parcours fonctionnent. Suppose que la phase B (`/speckit.implement`) a été exécutée et que la branche est à jour.

## 0. Prérequis

- Docker Compose installé (pour PostgreSQL).
- Python 3.12 + `venv` créé dans `backend/venv/`.
- Node.js 20+ + npm installés.
- Variables d'environnement renseignées dans `backend/.env` (notamment `DATABASE_URL`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY` pour les embeddings).

## 1. Cloner et basculer sur la branche

```bash
git fetch origin
git checkout feat/F01-fondations-sourcage-catalogue
git pull --ff-only
```

## 2. Démarrer PostgreSQL

```bash
docker compose up postgres -d
```

Vérifier la connectivité :

```bash
docker compose exec postgres pg_isready
```

## 3. Activer le venv backend et appliquer la migration

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt  # synchronise les dépendances
alembic upgrade head
```

Sortie attendue : la migration `020_create_sources_catalog` s'applique, créant 11 nouvelles tables. Le log doit afficher :

```
INFO  [alembic.runtime.migration] Running upgrade ... -> 020_create_sources_catalog, create sources catalog
```

Vérifier les tables créées :

```bash
docker compose exec postgres psql -U esg_mefali -d esg_mefali \
  -c "\dt sources indicators referentials referential_indicators criteria formulas thresholds emission_factors required_documents simulation_factors unsourced_flags"
```

## 4. Vérifier le seed

Le seed des 30+ sources est exécuté automatiquement par la migration (fonction `data_upgrade()` appelée après `op.create_table(...)`).

```bash
docker compose exec postgres psql -U esg_mefali -d esg_mefali \
  -c "SELECT publisher, COUNT(*) FROM sources WHERE verification_status = 'verified' GROUP BY publisher ORDER BY publisher;"
```

Sortie attendue (exemple) :

```
 publisher       | count
-----------------+-------
 ADEME           |    3
 BCEAO           |    2
 BOAD            |    3
 GCF             |    2
 Gold Standard   |    2
 IEA             |    3
 IFC             |    2
 IPCC            |    3
 ODD ONU         |    6
 UEMOA           |    3
 Verra           |    2
(11 rows)
TOTAL >= 31
```

## 5. Vérifier la migration des données existantes

```bash
docker compose exec postgres psql -U esg_mefali -d esg_mefali \
  -c "SELECT COUNT(*) AS emission_factors_count FROM emission_factors;"
docker compose exec postgres psql -U esg_mefali -d esg_mefali \
  -c "SELECT COUNT(*) AS indicators_count FROM indicators;"
docker compose exec postgres psql -U esg_mefali -d esg_mefali \
  -c "SELECT COUNT(*) AS pending_simulation_factors FROM simulation_factors WHERE status = 'pending';"
```

Sortie attendue :
- `emission_factors_count` ≥ 25 (correspondant au mapping de `backend/app/modules/carbon/emission_factors.py::EMISSION_FACTORS`).
- `indicators_count` = 30 (les 30 critères ESG).
- `pending_simulation_factors` ≥ 1 (constantes simulateur sans source officielle).

## 6. Lancer les tests backend

```bash
cd backend && source venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing
```

Cible :
- ≥ 80 % de couverture sur `app/modules/sources/`, `app/graph/tools/sourcing_tools.py`, `app/graph/validators/source_required.py`.
- Tous les tests passent.

## 7. Démarrer le backend

```bash
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## 8. Tester l'API REST `/api/sources`

### a. Liste publique (PME)

```bash
TOKEN_PME=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pme@test.local","password":"..."}' | jq -r .access_token)

curl -s http://localhost:8000/api/sources \
  -H "Authorization: Bearer $TOKEN_PME" | jq '.items[0]'
```

Attendu : un item avec `verification_status = "verified"` (les autres statuts sont filtrés côté backend pour les PME).

### b. Création admin (workflow 4-yeux)

```bash
TOKEN_ADMIN_A=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin-a@test.local","password":"..."}' | jq -r .access_token)

# Création
SOURCE_ID=$(curl -s -X POST http://localhost:8000/api/sources \
  -H "Authorization: Bearer $TOKEN_ADMIN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.org/doc.pdf",
    "title": "Document de test",
    "publisher": "ADEME",
    "version": "v1",
    "date_publi": "2024-01-01"
  }' | jq -r .id)

# Demande de validation
curl -s -X POST http://localhost:8000/api/sources/$SOURCE_ID/request-verification \
  -H "Authorization: Bearer $TOKEN_ADMIN_A" | jq .verification_status
# Attendu : "pending"

# Tentative de validation par le créateur — doit échouer 403
curl -s -w "%{http_code}" -X POST http://localhost:8000/api/sources/$SOURCE_ID/verify \
  -H "Authorization: Bearer $TOKEN_ADMIN_A"
# Attendu : 403 + "four_eyes_violation"

# Validation par admin différent
TOKEN_ADMIN_B=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin-b@test.local","password":"..."}' | jq -r .access_token)

curl -s -X POST http://localhost:8000/api/sources/$SOURCE_ID/verify \
  -H "Authorization: Bearer $TOKEN_ADMIN_B" | jq .verification_status
# Attendu : "verified"
```

## 9. Démarrer le frontend

```bash
cd frontend
npm install
npm run dev
```

## 10. Vérifier l'UI

### a. Page catalogue `/sources`

Ouvrir `http://localhost:3000/sources`. Vérifier :
- La liste affiche uniquement les sources `verified`.
- La barre de recherche filtre en texte libre (essayer « ADEME »).
- Le filtre publisher fonctionne (essayer « UEMOA »).
- Cliquer sur une entrée ouvre la modal détail avec lien officiel.
- Le mode sombre est respecté (toggle dark via `stores/ui.ts`).

### b. Page résultats ESG

1. Connecter une PME, lancer une évaluation ESG.
2. Naviguer vers la page de résultats.
3. Vérifier qu'un picto `<SourceLink>` apparaît à côté de chaque score, recommandation, critère.
4. Cliquer sur un picto : la modal `SourceModal.vue` s'ouvre, affiche les métadonnées et un bouton « Ouvrir le document officiel » qui ouvre l'URL dans un nouvel onglet.

### c. Page résultats carbone

1. Connecter une PME, lancer un calcul carbone.
2. Naviguer vers `/carbon/results`.
3. Vérifier qu'un picto `<SourceLink>` apparaît à côté de chaque facteur d'émission (issu de la table `emission_factors` migrée).

## 11. Tester le validator backend

Envoyer dans le chat (via UI ou via endpoint `/api/chat/messages`) la question :

> « Quel est le facteur d'émission de l'électricité réseau en Côte d'Ivoire ? »

Vérifier dans la console backend :
- L'agent invoque `cite_source(<uuid_source_ade me_ou_iea>)`.
- Le validator passe (`source_required.validate_response().passed = True`).
- La réponse SSE contient le chiffre + le picto cliquable côté frontend.

Pour tester le rejet :

> Forcer (via test mocké) une réponse contenant « 0,41 kgCO2e/kWh » sans `cite_source`.

Vérifier que :
- Le retry est déclenché (1 fois).
- Si le retry échoue, le texte est substitué par « [je ne dispose pas d'une source vérifiée pour ce chiffre] ».
- Un incident est journalisé.

## 12. Lancer les tests frontend

```bash
cd frontend
npm run test -- --coverage
```

Cible : ≥ 80 % de couverture sur les composants `components/sources/`.

## 13. Lancer les tests E2E Playwright

```bash
cd frontend
npx playwright test tests/e2e/F01-fondations-sourcage-catalogue.spec.ts --reporter=html
```

Les 3 parcours doivent passer :
1. PME consulte `/sources` et ouvre une modal.
2. Fund officer simulé ouvre une modal sur un score ESG.
3. Validator backend rejette une réponse sans citation (mock API).

Artefacts disponibles dans `frontend/playwright-report/index.html`.

## 14. Vérifier l'annexe PDF

Générer un rapport ESG :

```bash
curl -s -X POST http://localhost:8000/api/reports/generate \
  -H "Authorization: Bearer $TOKEN_PME" \
  -H "Content-Type: application/json" \
  -d '{"company_id":"<uuid>","assessment_id":"<uuid>"}' | jq .report_id
```

Télécharger le PDF :

```bash
curl -s http://localhost:8000/api/reports/<report_id>/download \
  -H "Authorization: Bearer $TOKEN_PME" -o /tmp/report.pdf
```

Ouvrir `/tmp/report.pdf` et vérifier :
- Section finale « Sources et références » présente.
- Chaque source listée avec [n], titre, publisher, version, date, page, statut, URL.
- Les chiffres dans le corps portent un renvoi inline « [n] ».

## 15. Rollback (si nécessaire)

```bash
cd backend && source venv/bin/activate
alembic downgrade -1
alembic upgrade head
```

Le cycle up/down/up doit être idempotent (testé en Phase B).

---

**Quickstart complet** : à la fin de la procédure, l'utilisateur a (1) une BDD avec 11 nouvelles tables peuplées, (2) un backend qui expose `/api/sources` avec workflow 4-yeux fonctionnel, (3) un frontend avec pictos source cliquables et page catalogue, (4) un agent IA qui cite ses sources et un validator backend qui rejette les chiffres sans citation, (5) un rapport PDF avec annexe sources auto-générée.
