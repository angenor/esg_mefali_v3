# Contract — GET /api/extension/v1/applications/active

**Auth** : Bearer token extension requis

## Request

```http
GET /api/extension/v1/applications/active HTTP/1.1
Authorization: Bearer <access_token>
Origin: chrome-extension://<extension-id>
```

## Response 200

```json
[
  {
    "id": "uuid-app-1",
    "offer_name": "SUNREF Ecobank — Programme efficacité énergétique",
    "status": "submitted_to_intermediary",
    "status_label_fr": "Soumise à l'intermédiaire",
    "updated_at": "2026-05-07T14:32:11Z",
    "deep_link": "https://app.esg-mefali.com/applications/uuid-app-1"
  },
  {
    "id": "uuid-app-2",
    "offer_name": "GCF — Readiness Programme",
    "status": "draft",
    "status_label_fr": "Brouillon",
    "updated_at": "2026-05-05T09:12:00Z",
    "deep_link": "https://app.esg-mefali.com/applications/uuid-app-2"
  }
]
```

- Maximum 50 entrées
- Tri : `updated_at DESC`
- Filtre : statut hors `approved`, `rejected`, `disbursed`, `cancelled`
- Isolation : RLS PostgreSQL par `account_id` (multi-tenant F02)

## Errors

- **401 Unauthorized** : token invalide

## status_label_fr — Mapping

| status                          | status_label_fr                |
|---------------------------------|--------------------------------|
| `draft`                         | Brouillon                      |
| `preparing`                     | Préparation                    |
| `submitted_to_intermediary`     | Soumise à l'intermédiaire      |
| `under_review_intermediary`     | En revue intermédiaire         |
| `submitted_to_fund`             | Soumise au fonds               |
| `under_review_fund`             | En revue fonds                 |

## Side effects

- Aucun (read-only)
