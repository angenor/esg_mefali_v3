# Contract — POST /api/extension/v1/auth/exchange

**Auth** : public (pas de bearer requis)

## Request

```http
POST /api/extension/v1/auth/exchange HTTP/1.1
Content-Type: application/json
Origin: chrome-extension://<extension-id>

{
  "email": "pme@example.com",
  "password": "Test123!"
}
```

## Response 200

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "scope": "extension",
  "expires_in": 2592000
}
```

- `access_token` : JWT TTL 24 h (réutilisation infra F02)
- `refresh_token` : JWT TTL 30 jours, scope `'extension'`, rotatif
- `scope` : toujours `"extension"`
- `expires_in` : durée validité refresh_token en secondes (30 jours = 2 592 000)

## Errors

- **401 Unauthorized** : credentials invalides — body `{"detail": "Identifiants invalides"}`
- **422 Unprocessable Entity** : payload mal formé — body Pydantic standard
- **429 Too Many Requests** : rate limit dépassé (≤ 5 tentatives/minute par IP) — body `{"detail": "Trop de tentatives, réessayez dans 60s"}`

## Side effects

- Insertion d'un row `refresh_tokens` avec `scope='extension'`, `account_id=<user.account_id>`
- Audit log entry `source_of_change='extension'`, `action='create'`, `entity_type='refresh_token'`
