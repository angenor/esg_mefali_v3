# API Contract — F03 PME endpoints

Routeur : `app/modules/audit/router.py`, monté sur `/api/audit`.
Auth : toutes les routes requièrent `Depends(get_current_user)` (token JWT valide).
RLS : positionne `app.current_account_id` (héritée F02) → policies `pme_access_own_account` filtrent côté PostgreSQL.

## `GET /api/audit/me`

### Description

Retourne les événements d'audit du compte de l'utilisateur courant, paginés et filtrables.

### Query params

| Paramètre | Type | Optional | Default | Description |
|---|---|---|---|---|
| `entity_type` | string | yes | — | Filtre par type d'entité (ex. `company_profile`, `fund_application`) |
| `entity_id` | UUID | yes | — | Filtre par identifiant d'entité spécifique |
| `action` | string | yes | — | `create` / `update` / `delete` / `view_admin` |
| `source_of_change` | string | yes | — | `manual` / `llm` / `import` / `admin` |
| `since` | datetime ISO 8601 | yes | — | Borne inférieure inclusive sur `timestamp` |
| `until` | datetime ISO 8601 | yes | — | Borne supérieure inclusive sur `timestamp` |
| `page` | int | yes | 1 | Numéro de page (≥ 1) |
| `limit` | int | yes | 50 | Taille de page (1 ≤ limit ≤ 200) |
| `order` | string | yes | `desc` | `asc` ou `desc` sur `timestamp` |

### Réponse 200

```json
{
  "events": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "timestamp": "2026-05-06T14:23:45.123Z",
      "user_id": "00000000-0000-0000-0000-000000000010",
      "user_email": "alice@example.com",
      "account_id": "00000000-0000-0000-0000-000000000020",
      "entity_type": "company_profile",
      "entity_id": "00000000-0000-0000-0000-000000000030",
      "action": "update",
      "field": "sector",
      "old_value": "agriculture",
      "new_value": "energie",
      "source_of_change": "manual",
      "actor_metadata": {
        "endpoint": "/api/companies/me",
        "request_id": "00000000-0000-0000-0000-000000000040"
      }
    }
  ],
  "total": 1234,
  "page": 1,
  "limit": 50
}
```

### Erreurs

| Code | Cas | Body |
|---|---|---|
| `401` | Non authentifié | `{"detail": "Token d'authentification manquant"}` |
| `400` | Paramètre invalide (ex. `limit > 200`) | `{"detail": "limit must be between 1 and 200"}` |
| `422` | Format paramètre invalide (ex. `since` mal formé) | `{"detail": [...]}` (Pydantic validation error) |

### Exemple `curl`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/audit/me?source_of_change=llm&page=1&limit=50"
```

---

## `GET /api/audit/me/export`

### Description

Exporte le log filtré (mêmes critères que `GET /api/audit/me`, sans pagination) au format CSV (UTF-8 BOM) ou JSON.

### Query params

Tous les paramètres de filtre de `GET /api/audit/me` (pas `page` ni `limit`) + :

| Paramètre | Type | Optional | Default | Description |
|---|---|---|---|---|
| `format` | string | yes | `csv` | `csv` ou `json` |

### Réponse 200 (format=csv)

- `Content-Type` : `text/csv; charset=utf-8`
- `Content-Disposition` : `attachment; filename="audit-log-<account_id>-<YYYYMMDD>.csv"`
- Body : streaming CSV. Première ligne contient le BOM UTF-8 (`﻿`) puis les en-têtes :
  ```
  id,timestamp,user_email,user_id,account_id,entity_type,entity_id,action,field,old_value,new_value,source_of_change,actor_metadata
  ```
  Suivies des lignes d'événements.

### Réponse 200 (format=json)

- `Content-Type` : `application/json`
- `Content-Disposition` : `attachment; filename="audit-log-<account_id>-<YYYYMMDD>.json"`
- Body : tableau JSON des événements (mêmes champs que `AuditEvent`).

### Erreurs

| Code | Cas | Body |
|---|---|---|
| `401` | Non authentifié | idem |
| `400` | `format` invalide | `{"detail": "format must be 'csv' or 'json'"}` |

### Exemple `curl`

```bash
# CSV
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/audit/me/export?format=csv&since=2026-04-01T00:00:00Z" \
  -o audit-log.csv

# JSON
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/audit/me/export?format=json" \
  -o audit-log.json
```

### Notes performance

- Streaming via `StreamingResponse` : le serveur n'accumule pas tout en mémoire.
- Cursor SQLAlchemy `yield_per(1000)` pour limiter le buffer DB.
- 100 000 lignes exportées en < 30 secondes (P95) en local.
