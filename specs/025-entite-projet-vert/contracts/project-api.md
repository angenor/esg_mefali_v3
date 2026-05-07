# Contract — API REST Projects (F06)

**Module** : `backend/app/modules/projects/router.py`
**Préfixe** : `/api/projects`
**Tags OpenAPI** : `["projects"]`
**Auth** : `Depends(get_current_user)` sur tous les endpoints (PME ou ADMIN)
**RLS** : héritée F02 via `app.current_account_id` ; aucun bypass possible.

## 1. `GET /api/projects` — Liste paginée

**Query params** : `status`, `maturity`, `objective_env`, `auto_generated`, `page`, `limit`

**Response 200** : `ProjectListResponse`

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "name": "Panneaux solaires usine principale",
      "status": "seeking_funding",
      "maturity": "pilot",
      "objective_env": ["renewable_energy", "mitigation"],
      "target_amount": {"amount": "50000000", "currency": "XOF"},
      "expected_impact_tco2e": "120.0000",
      "auto_generated": false,
      "applications_count": 2,
      "created_at": "2026-05-07T10:30:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "limit": 25
}
```

**Codes** : 200 OK ; 401 Unauthorized si pas connecté.

**Exemple curl** :
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/projects?status=seeking_funding&limit=10"
```

## 2. `GET /api/projects/{project_id}` — Détail

**Path param** : `project_id` UUID

**Response 200** : `ProjectDetail`

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "account_id": "00000000-0000-0000-0000-000000000010",
  "name": "Panneaux solaires usine principale",
  "description": "Installation de 50 kWc de panneaux photovoltaïques sur le toit de l'usine principale...",
  "objective_env": ["renewable_energy", "mitigation"],
  "maturity": "pilot",
  "status": "seeking_funding",
  "target_amount": {"amount": "50000000", "currency": "XOF"},
  "duration_months": 18,
  "financing_structure": "blending",
  "expected_impact_tco2e": "120.0000",
  "expected_jobs_created": 5,
  "expected_beneficiaries": null,
  "expected_hectares_restored": null,
  "expected_other_impacts": null,
  "location_country": "CI",
  "location_region": "Abidjan",
  "auto_generated": false,
  "created_at": "2026-05-07T10:30:00Z",
  "updated_at": "2026-05-07T11:00:00Z",
  "project_documents": [
    {
      "id": "00000000-0000-0000-0000-0000000000aa",
      "project_id": "00000000-0000-0000-0000-000000000001",
      "document_id": "00000000-0000-0000-0000-0000000000bb",
      "doc_type": "feasibility_study",
      "created_at": "2026-05-07T10:45:00Z"
    }
  ],
  "applications_count": 2
}
```

**Codes** : 200 OK ; 401 Unauthorized ; 404 Not Found (ou retourné par RLS comme 0 ligne).

## 3. `POST /api/projects` — Création

**Body** : `ProjectCreate`

```json
{
  "name": "Panneaux solaires usine principale",
  "description": "Installation de 50 kWc...",
  "objective_env": ["renewable_energy", "mitigation"],
  "maturity": "pilot",
  "status": "draft",
  "target_amount": {"amount": "50000000", "currency": "XOF"},
  "duration_months": 18,
  "financing_structure": "blending",
  "expected_impact_tco2e": 120,
  "expected_jobs_created": 5,
  "location_country": "CI",
  "location_region": "Abidjan"
}
```

**Response 201 Created** : `ProjectDetail`

**Codes** : 201 ; 400 si validation Pydantic échoue ; 401 Unauthorized.

**Audit log F03** : insère `audit_log.action='create' source_of_change='manual' entity_type='projects' entity_id=<new_id>`.

## 4. `PATCH /api/projects/{project_id}` — Mise à jour partielle

**Body** : `ProjectUpdate` (tous champs optionnels)

```json
{
  "expected_jobs_created": 8,
  "status": "seeking_funding"
}
```

**Response 200** : `ProjectDetail` mis à jour.

**Codes** : 200 ; 400 ; 401 ; 404.

**Audit log F03** : insère 1 ligne `audit_log` PAR champ effectivement modifié.

## 5. `DELETE /api/projects/{project_id}?force=false` — Suppression

**Query param** : `force` (boolean, default `false`)

### Cas 1 : `force=false` ET applications actives existantes

**Response 409 Conflict** : `DeleteResult`

```json
{
  "ok": false,
  "blocked_by": [
    {
      "application_id": "00000000-0000-0000-0000-0000000000cc",
      "fund_name": "Green Climate Fund",
      "status": "submitted_to_fund"
    }
  ],
  "hint": "force=true pour confirmer la suppression (les applications resteront liées)"
}
```

### Cas 2 : `force=false` SANS applications actives (ou toutes en `rejected`/`accepted`/`cancelled`)

**Response 200** : `DeleteResult`

```json
{
  "ok": true,
  "blocked_by": [],
  "hint": null
}
```

Le projet passe en `status='cancelled'` (soft-delete). Audit log F03 : `update field='status' old_value=<...> new_value='cancelled'`.

### Cas 3 : `force=true` (avec ou sans applications actives)

Identique au cas 2 ; ignore les blocages, soft-delete.

**Codes** : 200 ; 401 ; 404 ; 409.

## 6. `POST /api/projects/{project_id}/duplicate` — Duplication

**Body** : `DuplicateProjectRequest`

```json
{
  "new_name": "Panneaux solaires Site B"
}
```

**Response 201 Created** : `ProjectDetail` (le nouveau projet)

```json
{
  "id": "00000000-0000-0000-0000-0000000000dd",
  "account_id": "00000000-0000-0000-0000-000000000010",
  "name": "Panneaux solaires Site B",
  "description": "...",
  "objective_env": ["renewable_energy", "mitigation"],
  "maturity": "pilot",
  "status": "draft",
  "target_amount": {"amount": "50000000", "currency": "XOF"},
  "auto_generated": false,
  "project_documents": [],
  "applications_count": 0,
  "created_at": "2026-05-07T11:30:00Z",
  "updated_at": "2026-05-07T11:30:00Z"
}
```

**Codes** : 201 ; 401 ; 404.

**Comportements** :
- Si `new_name` absent → `name` source + suffixe `' (copie)'` (tronqué à 200).
- `status` forcé à `'draft'` (clarification Q4).
- `auto_generated` forcé à `false`.
- `project_documents` NON copiés.
- Audit log F03 : `actor_metadata={'duplicated_from': '<source_id>'}`.

## 7. `GET /api/projects/{project_id}/applications` — Liste candidatures rattachées

**Response 200** : `list[ApplicationSummary]`

```json
[
  {
    "id": "00000000-0000-0000-0000-0000000000ee",
    "fund_id": "00000000-0000-0000-0000-0000000000ff",
    "fund_name": "Green Climate Fund",
    "intermediary_id": null,
    "target_type": "fund_direct",
    "status": "submitted_to_fund",
    "created_at": "2026-05-07T12:00:00Z",
    "submitted_at": "2026-05-07T13:00:00Z"
  }
]
```

**Codes** : 200 ; 401 ; 404.

## Codes d'erreur communs

| Code | Cas | Body |
|------|-----|------|
| 400 | Validation Pydantic | `{"detail": [{"type": "...", "loc": [...], "msg": "...", ...}]}` |
| 401 | Pas authentifié | `{"detail": "Not authenticated"}` |
| 403 | Authentifié mais RLS bloque (rare, généralement 404) | `{"detail": "Forbidden"}` |
| 404 | Ressource non trouvée (RLS ou ID invalide) | `{"detail": "Project not found"}` |
| 409 | Suppression bloquée par applications actives | `DeleteResult` (cf § 5) |
| 422 | Body invalide (FastAPI/Pydantic) | `{"detail": [...]}` |

## Headers communs

- `Authorization: Bearer <jwt>` (obligatoire)
- `Content-Type: application/json` (sur POST/PATCH/DELETE)

## RLS et isolation tenant

Toutes les opérations passent par le helper `set_rls_context(session, account_id, role, user_id)` (F02) appelé dans `get_current_user`. Aucune requête ne nécessite de filtre `WHERE account_id=...` explicite — c'est PostgreSQL RLS qui filtre.

Test cross-tenant `test_project_rls_cross_tenant.py` couvre :
- PME-A liste : ne voit que ses projets.
- PME-A crée avec `account_id=PME-B` : RowLevelSecurityViolation.
- PME-A modifie projet de PME-B : 0 row updated → 404.
- PME-A duplique projet de PME-B : 0 row found → 404.
- PME-A supprime projet de PME-B : 0 row deleted → 404.
