# Contract: Admin Endpoints Overview

**Date** : 2026-05-07
**Total endpoints** : ~80 endpoints REST sous `/api/admin/*` + 1 endpoint public sous `/api/auth/reset-password`

Tous les endpoints sous `/api/admin/*` sont protégés par `Depends(get_current_admin)` (F02).
Les réponses suivent le format `{success: bool, data: T | null, error: str | null, meta: {...} | null}`.

## Conventions communes

### Pagination
- Query params : `page=1` (default), `limit=20` (default, max 100)
- Réponse : `meta: {total, page, limit, total_pages}`

### Filtres
- Query params spécifiques à chaque entité (ex `fund_type`, `theme`, `publication_status`)
- Recherche full-text via `q=...` (ILIKE sur title/name avec index trigram)

### Erreurs standardisées
- 400 : Bad Request (publish_blocked, has_dependents, 4_eyes_violation)
- 401 : Unauthorized (token JWT invalide/absent)
- 403 : Forbidden (user non admin)
- 404 : Not Found
- 422 : Unprocessable Entity (validation Pydantic)

## Sous-routers (15)

### 1. funds_router (`/api/admin/funds`)
- `GET /` : liste paginée filtrée
- `POST /` : création (status=draft)
- `GET /{id}` : détail avec sources liées + intermédiaires
- `PATCH /{id}` : édition (nouvelle version si published, F04)
- `POST /{id}/publish` : trigger gating
- `DELETE /{id}` : soft delete avec impact analysis

### 2. intermediaries_router (`/api/admin/intermediaries`)
Idem funds avec champs spécifiques.

### 3. offers_router (`/api/admin/offers`)
6 endpoints CRUD + `POST /{id}/compute-effective` (calcul auto via F07).

### 4. referentials_router (`/api/admin/referentials`)
CRUD standard + cascade indicators.

### 5. indicators_router (`/api/admin/indicators`)
CRUD standard + impact analysis sur criteria.

### 6. criteria_router (`/api/admin/criteria`)
CRUD standard.

### 7. templates_router (`/api/admin/templates`)
CRUD avec upload DOCX.

### 8. sources_router (`/api/admin/sources`)
- `GET /?status=&publisher=&q=&page=&limit=` : liste filtrée
- `POST /` : création (status=pending)
- `GET /{id}` : détail
- `GET /{id}/dependents` : impact analysis
- `PATCH /{id}` : édition + transitions verification_status (trigger 4-yeux)
- `DELETE /{id}` : soft delete avec impact analysis

### 9. emission_factors_router (`/api/admin/emission-factors`)
CRUD pour facteurs ADEME/IPCC.

### 10. simulation_factors_router (`/api/admin/simulation-factors`)
CRUD pour constantes simulateur.

### 11. users_router (`/api/admin/users`)
- `GET /?role=&is_active=&q=&page=&limit=` : liste paginée
- `GET /{id}` : détail user + account associé
- `POST /{id}/reset-password` : génère token + email
- `POST /{id}/toggle-active` : body `{reason}`

### 12. companies_router (`/api/admin/companies`)
- `GET /?account_status=&sector=&last_login_after=&page=&limit=` : liste PME
- `GET /{account_id}` : profil + projets + scores + attestations + audit_log (crée audit view_admin)

### 13. attestations_router (`/api/admin/attestations`)
- `GET /?status=&account_id=&page=&limit=` : liste
- `POST /{id}/revoke` : body `{reason}` (≥ 10 chars)

### 14. metrics_router (`/api/admin/metrics`)
- `GET /overview` : MetricsOverview (sources, accounts, applications, attestations, llm_costs)

### 15. audit_router (créé F03, validé F09)
Liste audit log global avec filtres.

### 16. skills_router (créé F23, validé F09)
8 endpoints CRUD skills avec eval gating.

## Endpoint public

### auth/router.py — POST /api/auth/reset-password
- Body : `{token: string, new_password: string (≥ 8 chars)}`
- Validation : token hash match + non utilisé + non expiré
- Effet : update users.password (bcrypt), set token.used_at
- Response : 200 `{success: true}` ou 400 `{error: "token_invalid|token_expired|token_already_used"}`

## Codes statut (résumé)

| Code | Cas |
|------|-----|
| 200 | OK (GET, PATCH, POST publish, etc.) |
| 201 | Created (POST création) |
| 400 | publish_blocked, has_dependents, 4_eyes_violation, token_invalid, token_expired |
| 401 | JWT manquant/invalide |
| 403 | user non admin |
| 404 | entité not found |
| 422 | validation Pydantic |
| 500 | erreur serveur (à éviter) |
