# Contract — GET /api/extension/v1/me/profile-snapshot

**Auth** : Bearer token extension (scope='extension') requis

## Request

```http
GET /api/extension/v1/me/profile-snapshot HTTP/1.1
Authorization: Bearer <access_token>
Origin: chrome-extension://<extension-id>
```

## Response 200

```json
{
  "sector": "agriculture",
  "country": "SN",
  "projects": [
    {"id": "uuid-1", "name": "Panneaux solaires", "status": "seeking_funding"},
    {"id": "uuid-2", "name": "Compostage industriel", "status": "in_execution"},
    {"id": "uuid-3", "name": "Reforestation", "status": "draft"}
  ]
}
```

- `sector` : secteur de l'entreprise (peut être null si non renseigné)
- `country` : code ISO 3166-1 alpha-2 (peut être null)
- `projects` : 3 derniers projets actifs (statuts hors `cancelled`/`closed`), tri date update desc

## Errors

- **401 Unauthorized** : token invalide ou scope incorrect — body `{"detail": "Token invalide"}`
- **404 Not Found** : aucun profil entreprise — body `{"detail": "Profil entreprise non trouvé"}`
