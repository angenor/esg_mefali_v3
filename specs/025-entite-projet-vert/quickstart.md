# Quickstart — F06 Entité Projet Vert

**Audience** : développeur souhaitant tester la feature F06 localement après implémentation.

## Pré-requis

- Backend démarré (`cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000`)
- Frontend démarré (`cd frontend && npm run dev`)
- PostgreSQL local (`docker compose up postgres -d`)
- F01/F02/F03/F04 mergées sur `main` (vérifié par `alembic current` retournant au moins `024_carbone_mix_uemoa`)
- 1 utilisateur de test (PME) créé via `POST /auth/register` ou seed

## 1. Migrer la base

```bash
cd backend && source venv/bin/activate
alembic upgrade head
# Doit afficher: Running upgrade 024_carbone_mix_uemoa -> 025_create_projects
# Et imprimer: [F06 migration] WARNING : 0 fund_applications n'ont pas pu être backfillées (si OK)
```

Vérifier en SQL :
```sql
-- Tables créées
SELECT count(*) FROM information_schema.tables WHERE table_name IN ('projects', 'project_documents');
-- Doit retourner 2

-- Colonne project_id ajoutée à fund_applications
SELECT column_name, is_nullable FROM information_schema.columns
WHERE table_name='fund_applications' AND column_name='project_id';
-- Doit retourner project_id, NO

-- RLS active
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class WHERE relname IN ('projects', 'project_documents');
-- Doit retourner relrowsecurity=t, relforcerowsecurity=t
```

## 2. Créer un projet via API REST

Récupérer un JWT :
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pme@example.com","password":"secret"}' \
  | jq -r .access_token)
```

Créer un projet :
```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Panneaux solaires usine principale",
    "description": "Installation de 50 kWc de panneaux PV.",
    "objective_env": ["renewable_energy", "mitigation"],
    "maturity": "pilot",
    "status": "draft",
    "target_amount": {"amount": "50000000", "currency": "XOF"},
    "expected_impact_tco2e": 120,
    "expected_jobs_created": 5,
    "location_country": "CI",
    "location_region": "Abidjan"
  }'
```

Lister les projets :
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/projects?status=draft&limit=10"
```

## 3. Vérifier l'audit log F03

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/audit/me?entity_type=projects&order=desc"
```

Doit afficher au moins :
```json
[
  {
    "action": "create",
    "source_of_change": "manual",
    "entity_type": "projects",
    "field": null,
    "new_value": {"name": "...", "status": "draft", ...},
    "timestamp": "..."
  }
]
```

## 4. Créer un projet via le LLM (chat)

Démarrer une conversation (via `POST /api/chat/messages` ou UI `/chat`) :

> « J'ai un atelier où on utilise des générateurs diesel pour pallier les coupures électriques. »

L'assistant détecte le potentiel projet et appelle `ask_interactive_question` (F18) avec :

- « Voulez-vous que je crée ce projet pré-rempli ? »
- Options : `["Oui, crée le projet pré-rempli", "Je veux ajuster d'abord", "Non, pas maintenant"]`

Cliquer « Oui ». Le LLM appelle ensuite :
1. `cite_source(source_id=<ADEME ou IEA Africa Energy Outlook>)` pour la valeur de réduction CO2e
2. `create_project(name="Remplacement générateurs diesel par énergie solaire", ...)`

Vérifier en SQL :
```sql
SELECT a.action, a.source_of_change, a.actor_metadata->>'tool_name'
FROM audit_log a
WHERE a.entity_type='projects'
ORDER BY a.timestamp DESC LIMIT 1;
```

Doit retourner : `create | llm | create_project`.

## 5. Tester la duplication

```bash
PROJECT_ID="<le projet précédemment créé>"
curl -X POST "http://localhost:8000/api/projects/$PROJECT_ID/duplicate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_name": "Panneaux solaires Site B"}'
```

Vérifier que le nouveau projet a `status='draft'` (forcé) et que tous les autres champs sont copiés.

## 6. Tester le garde-fou suppression

### Cas 1 : projet sans applications actives → soft-delete OK
```bash
curl -X DELETE "http://localhost:8000/api/projects/$PROJECT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

Réponse 200 : `{"ok": true, "blocked_by": [], "hint": null}`.

Vérifier que `status='cancelled'` :
```sql
SELECT status FROM projects WHERE id='<PROJECT_ID>';
-- cancelled
```

### Cas 2 : projet avec application active → blocage
1. Créer une `FundApplication` rattachée au projet (via `POST /api/applications` ou tool LLM `create_fund_application`).
2. Tenter `DELETE /api/projects/{id}?force=false`.
3. Réponse 409 :
```json
{
  "ok": false,
  "blocked_by": [{"application_id": "...", "fund_name": "...", "status": "submitted_to_fund"}],
  "hint": "force=true pour confirmer la suppression (les applications resteront liées)"
}
```
4. Confirmer avec `?force=true` → réponse 200, projet en `status='cancelled'`, application toujours liée.

## 7. UI

### Pages frontend
- `/profile` → page index avec onglets « Entreprise » et « Mes Projets »
- `/profile/company` → fiche entreprise (existante, déplacée)
- `/profile/projects` → liste avec filtres et pagination
- `/profile/projects/new` → formulaire création
- `/profile/projects/[id]` → édition
- `/profile/projects/[id]/duplicate` → duplication

### Composants Vue
- `ProjectCard.vue` : card avec badges objectif, montant Money (`<MoneyDisplay>` F04), compteur applications, bouton « Voir candidatures ».
- `ProjectForm.vue` : formulaire (mode `create | edit | duplicate`).
- `ProjectStatusSelector.vue` : sélecteur ARIA-conforme.
- `ProjectImpactBadges.vue` : badges visuels pour `objective_env` et impacts.
- `DuplicateProjectModal.vue` : modale avec focus trap.
- `ProjectFilters.vue` : filtres URL-synchronisés.
- `ProjectList.vue` : grid + pagination.

### Sidebar
Lien « Mes Projets » dans la sidebar avec badge count (projets actifs ≠ cancelled/closed).

## 8. Round-trip Alembic

```bash
cd backend && source venv/bin/activate
alembic upgrade head
# 025_create_projects appliquée

alembic downgrade -1
# Rollback : drop tables + drop colonne project_id

alembic upgrade head
# Réappliqué ; backfill se relance idempotent (les apps précédemment liées restent liées)
```

Vérifier que les `fund_applications` retrouvent leur `project_id` après round-trip.

## 9. Tests automatisés

### Backend
```bash
cd backend && source venv/bin/activate
pytest tests/unit/test_project_*.py tests/integration/test_project_*.py tests/migrations/test_alembic_f06.py -v --cov=app/modules/projects --cov=app/graph/tools/project_tools --cov=app/models/project --cov-report=term-missing
```

Cible : couverture ≥ 80 % sur le périmètre F06.

### Frontend
```bash
cd frontend && npm run test -- --coverage projects
```

### E2E
```bash
cd frontend && npx playwright test tests/e2e/F06-entite-projet-vert.spec.ts --reporter=html
```

## 10. Troubleshooting

### `RowLevelSecurityViolation` lors d'un INSERT
Vérifier que `set_rls_context(session, account_id, role, user_id)` est bien appelé dans `get_current_user` (héritage F02). Si vous écrivez un script CLI qui contourne FastAPI, exécuter manuellement :
```python
await session.execute(
    text("SET LOCAL app.current_account_id = :acc"), {"acc": str(account_id)}
)
await session.execute(text("SET LOCAL app.current_role = 'PME'"))
```

### Migration qui échoue sur PostgreSQL avec `duplicate key value violates unique constraint`
Indique que la migration a déjà partiellement tourné. Vérifier `alembic current` ; si `025_create_projects` est appliquée mais l'état est incohérent, contacter l'équipe (ne pas forcer downgrade en prod).

### `applications_count` toujours à 0
Vérifier que la requête de comptage est bien exécutée (`SELECT count(*) FROM fund_applications WHERE project_id=$1`). Le service utilise un sous-select dans la requête principale ; voir `app/modules/projects/service.py:_load_applications_count`.

### Tools LLM créent un projet avec `target_amount` non sourcé
Le validator `source_required.py` (F01) doit déclencher un retry. Vérifier dans les logs INFO :
```
source_required_retry_triggered tool=create_project field=target_amount_amount value=50000000
```
Si pas de retry, vérifier que le tool `cite_source` est bien dans la `GLOBAL_WHITELIST` du tool selector et que le LLM voit bien les 14 tools.
