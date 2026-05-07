# Contract — Admin Skills REST API (F23)

**Base URL** : `/api/admin/skills`
**Auth** : `Depends(require_admin_role)` (F02). Token Bearer JWT.

---

## `GET /api/admin/skills`

**Description** : Liste paginée des Skills, filtres optionnels.

**Query params** :

| Param | Type | Requis | Default | Description |
|---|---|---|---|---|
| `domain` | string (enum 7 valeurs) | NO | — | Filtre par domaine |
| `status` | string (`draft\|published`) | NO | — | Filtre par statut |
| `q` | string | NO | — | Recherche fuzzy sur `name` |
| `page` | int | NO | 1 | Pagination |
| `limit` | int | NO | 20 | Pagination (max 100) |

**Réponse 200** :

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "skill_esg_diagnostic",
      "domain": "diagnostic_esg",
      "version": "1.0.0",
      "status": "published",
      "valid_from": "2026-05-07",
      "valid_to": null,
      "created_at": "2026-05-07T10:00:00Z",
      "updated_at": "2026-05-07T10:00:00Z"
    }
  ],
  "total": 11,
  "page": 1,
  "limit": 20
}
```

**Erreurs** : `401`, `403`.

---

## `POST /api/admin/skills`

**Description** : Crée une nouvelle Skill (status=`draft`). Validator anti-injection + tokens limit + sources verified + tool names valides.

**Body** : `SkillCreate` (voir `skill_schema.json`).

**Réponse 201** : `SkillRead` complet.

**Erreurs** :

- `422 prompt_expert_too_long` : `{actual_tokens, max_tokens: 5000}`
- `422 procedure_too_long` : `{actual_tokens, max_tokens: 3000}`
- `422 detected_patterns` : `{detected_patterns: ["ignore_previous_instructions", ...]}`
- `422 source_not_found` : `{source_id: "uuid"}`
- `422 source_must_be_verified` : `{source_id: "uuid", current_status: "draft"}`
- `422 tool_name_unknown` : `{tool_name: "..."}`
- `422 name_already_exists` : `{name: "skill_xxx"}`
- `400 missing_fields`

---

## `GET /api/admin/skills/{id}`

**Description** : Détail d'une Skill avec sources résolues.

**Path** : `id: UUID`.

**Réponse 200** : `SkillReadDetailed` (Skill + sources résolues = title, url, publisher).

**Erreurs** : `404 skill_not_found`.

---

## `PATCH /api/admin/skills/{id}`

**Description** : Édition. Si `status=draft` → update in-place. Si `status=published` → crée nouvelle version `draft` (semver patch+1).

**Body** : `SkillUpdate` (tous champs optionnels). Re-validator si champs sensibles modifiés.

**Réponse 200** : `SkillRead` (nouvel id si versioning).

**Erreurs** :

- `422` (mêmes que POST si champs sensibles modifiés)
- `404 skill_not_found`
- `409 concurrent_edit_conflict` (optimistic locking si implémenté)

---

## `POST /api/admin/skills/{id}/publish`

**Description** : Déclenche eval gating. Si gate passé, transitionne `draft → published`.

**Body** : `{}` (vide).

**Comportement** :
1. Charge skill, vérifie `status=draft`.
2. Vérifie `len(golden_examples) >= 5`.
3. Exécute `run_skill_eval()` (parallèle, max 5 concurrent, timeout 60s).
4. Si `gate_passed=False` → 422 avec rapport.
5. Si `gate_passed=True` → mise à jour BDD + audit log + invalidation cache loader.

**Réponse 200 (gate passé)** :

```json
{
  "skill": { /* SkillRead status=published */ },
  "eval_report": { /* SkillEvalReport gate_passed=true */ }
}
```

**Erreurs** :

- `400 already_published` : skill déjà publiée.
- `422 insufficient_golden_examples` : `{actual: 3, minimum: 5}`.
- `422 gate_failed` : retourne `SkillEvalReport`.
- `504 eval_timeout` : eval > 60s.
- `404 skill_not_found`.

---

## `POST /api/admin/skills/{id}/test`

**Description** : Exécute golden_examples sans publier. Statut reste inchangé.

**Body** : `{}`.

**Réponse 200** : `SkillEvalReport`.

**Erreurs** : `404`, `504 eval_timeout`.

---

## `POST /api/admin/skills/{id}/unpublish`

**Description** : Rollback `published → draft`. Pas de suppression.

**Body** : `{}`.

**Réponse 200** : `SkillRead` (status=draft).

**Erreurs** :

- `400 already_draft`.
- `404 skill_not_found`.
- `409 has_supersession_chain` : ne peut pas unpublier une skill qui a déjà été remplacée par une nouvelle version.

---

## `DELETE /api/admin/skills/{id}`

**Description** : Soft delete. UNIQUEMENT si `status=draft`. Met `valid_to=today()`.

**Réponse 204** : succès.

**Erreurs** :

- `400 cannot_delete_published` : depubliér d'abord.
- `404 skill_not_found`.

---

## Audit log

Toutes les mutations (POST, PATCH, /publish, /unpublish, DELETE) ET les tentatives d'injection bloquées émettent une entrée dans `audit_log` (F03) :

| Action | Métadonnées |
|---|---|
| `skill_created` | `{name, domain, version}` |
| `skill_updated` | `{changes: {...}}` |
| `skill_published` | `{eval_report: {...}, version}` |
| `skill_unpublished` | `{previous_version}` |
| `skill_deleted` | `{name, version}` |
| `skill_superseded` | `{old_id, new_id, old_version, new_version}` |
| `injection_attempt_blocked` | `{detected_patterns, prompt_excerpt: "<truncated 200 chars>"}` |

---

## Headers communs

- `Authorization: Bearer <jwt>` — requis sur tous les endpoints.
- `Content-Type: application/json` — pour POST/PATCH.
- `X-Request-ID: <uuid>` — recommandé pour tracing.

---

## Performance cibles

| Endpoint | P95 |
|---|---|
| GET /skills | < 200ms (pagination 20) |
| GET /skills/{id} | < 100ms |
| POST /skills | < 300ms (incluant tokens count + injection check) |
| PATCH /skills/{id} | < 300ms |
| POST /skills/{id}/test | < 60s (eval gating, parallèle) |
| POST /skills/{id}/publish | < 90s (eval + commit) |
| POST /skills/{id}/unpublish | < 100ms |
| DELETE /skills/{id} | < 100ms |
