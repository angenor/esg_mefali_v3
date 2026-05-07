# Contract: `/api/me/data/*` — Inventaire & Export

Date : 2026-05-07
Branche : `feat/F05-rgpd-mes-donnees-consents`

## `GET /api/me/data/inventory`

### Description

Retourne les compteurs et dates de dernière modification pour toutes les catégories de données stockées sous le `account_id` du JWT courant.

### Auth

JWT requis. Filtrage strict par `account_id = current_user.account_id` (multi-tenant invariant F02).

### Request

Pas de query params. Pas de body.

### Response 200

```json
{
  "counts": {
    "profile": 1,
    "projects": 3,
    "applications": 5,
    "esg_assessments": 2,
    "carbon_assessments": 1,
    "credit_scores": 1,
    "documents": 12,
    "conversations": 8,
    "messages": 142,
    "attestations": 1,
    "consents": 7
  },
  "last_modified": {
    "profile": "2026-04-22T10:14:33Z",
    "projects": "2026-05-01T08:22:11Z",
    "applications": "2026-04-30T16:45:00Z",
    "esg_assessments": "2026-04-15T09:30:22Z",
    "carbon_assessments": "2026-03-20T14:12:55Z",
    "credit_scores": "2026-04-25T11:08:01Z",
    "documents": "2026-05-05T09:00:00Z",
    "conversations": "2026-05-06T18:30:00Z",
    "messages": "2026-05-06T18:35:12Z",
    "attestations": "2026-04-25T11:30:00Z",
    "consents": "2026-04-01T12:00:00Z"
  }
}
```

### Response 401 — non authentifié

Réponse standard FastAPI HTTPBearer.

### Performance

- Calcul des compteurs en parallèle via `asyncio.gather` sur 11 SELECT COUNT(*).
- p95 < 1 s.

---

## `GET /api/me/data/export?format=json`

### Description

Génère un export ZIP complet de toutes les données stockées sous `account_id`. Comportement adaptatif :
- **Si taille estimée ≤ 100 MB** : génération synchrone, retour direct du ZIP en `application/zip`.
- **Si taille estimée > 100 MB** : génération asynchrone via `BackgroundTasks`. Réponse 202 immédiate, email de notification envoyé quand prêt.

### Auth

JWT requis.

### Request

Query : `format=json` (seul format supporté en MVP).

Pas de body.

### Response 200 — synchrone

- Headers :
  - `Content-Type: application/zip`
  - `Content-Disposition: attachment; filename="esg-mefali-export-{account_id}-{date}.zip"`
- Body : bytes ZIP.

Structure du ZIP :

```
esg-mefali-export-{account_id}-{YYYYMMDD-HHmmss}.zip
├── README.md          # Description structure (texte fr)
├── data.json          # Toutes les tables account_id (voir schéma ci-dessous)
└── documents/
    └── manifest.json  # Liste {filename, signed_url, expires_at, original_path, mimetype, size}
```

Schéma de `data.json` :

```json
{
  "account": {
    "id": "uuid",
    "created_at": "...",
    "company_name": "...",
    "..."
  },
  "users": [
    {"id": "uuid", "email": "...", "role": "owner|collaborator|viewer", "..."}
  ],
  "profile": { "...": "..." },
  "projects": [ { "...": "..." } ],
  "applications": [ { "...": "..." } ],
  "esg_assessments": [ { "...": "..." } ],
  "carbon_assessments": [ { "...": "..." } ],
  "credit_scores": [ { "...": "..." } ],
  "documents": [
    { "id": "uuid", "filename": "...", "mimetype": "...", "size_bytes": 12345, "uploaded_at": "...", "signed_url_24h": "https://..." }
  ],
  "conversations": [ { "id": "uuid", "messages": [ ... ] } ],
  "messages": [ { "...": "..." } ],
  "attestations": [ { "...": "..." } ],
  "consents": [ { "type": "...", "granted": true, "granted_at": "...", "revoked_at": null, "version": "v1.0" } ],
  "audit_log_personnel": [ { "timestamp": "...", "action": "...", "entity_type": "...", "metadata": {} } ],
  "_meta": {
    "exported_at": "2026-05-07T10:00:00Z",
    "exported_by_user_id": "uuid",
    "schema_version": "1.0"
  }
}
```

### Response 202 — asynchrone

```json
{
  "job_id": "uuid-from-audit-log-event",
  "status": "pending",
  "estimated_completion_at": "2026-05-07T10:05:00Z",
  "message": "Export en préparation, vous recevrez un email avec le lien quand il sera prêt"
}
```

### Audit log

À chaque appel (sync ou async start) :

```json
{
  "entity_type": "account",
  "entity_id": "{account_id}",
  "action": "data_exported" | "data_export_requested",
  "metadata": {
    "format": "json",
    "size_bytes": 12345,
    "mode": "sync" | "async",
    "job_id": "uuid",
    "ip": "...",
    "user_agent": "..."
  }
}
```

À la finalisation async :

```json
{
  "entity_type": "data_export",
  "entity_id": "{job_id}",
  "action": "data_export_ready",
  "metadata": {
    "size_bytes": 567890123,
    "signed_url": "https://app.../api/me/data/export/download?token=xxx",
    "expires_at": "2026-05-14T10:05:00Z"
  }
}
```

### Response 429 — rate limited

Si la PME a déjà exporté dans les 5 dernières minutes :

```json
{
  "detail": "Un export récent est encore disponible",
  "previous_export_url": "https://...",
  "previous_export_expires_at": "..."
}
```

---

## `GET /api/me/data/export/download?token={signed}`

### Description

Endpoint de téléchargement protégé par URL signée pour les exports asynchrones.

### Auth

**Pas de JWT requis** (le token signé authentifie). Vérifie la signature `itsdangerous` et l'expiration (7j).

### Request

Query : `token` (string signé).

### Response 200

- Headers : `Content-Type: application/zip`, `Content-Disposition: attachment; ...`
- Body : bytes ZIP.

### Response 410 — expiré

```json
{ "detail": "Lien expiré, veuillez demander un nouvel export" }
```

### Response 401 — signature invalide

```json
{ "detail": "Lien invalide" }
```

---

## Schémas Pydantic correspondants

Voir [data-model.md](../data-model.md) — section « Schémas Pydantic (référence) ».

## Tests de contrat

### Backend (pytest)

1. `test_inventory_returns_counts_for_authenticated_account` : crée un account avec 1 projet + 2 assessments + 3 documents, appelle `GET /api/me/data/inventory`, vérifie les compteurs.
2. `test_inventory_isolates_by_account_id` : crée 2 accounts (A, B), connecte avec A, vérifie que les compteurs ne reflètent que les données de A.
3. `test_export_sync_returns_zip_for_small_account` : crée un small account (~10 MB estimés), `GET /api/me/data/export`, vérifie Content-Type + structure ZIP (data.json + README + manifest).
4. `test_export_async_returns_202_for_large_account` : mock un large account (estimation > 100 MB), `GET /api/me/data/export`, vérifie 202 + job_id retourné.
5. `test_export_audit_log_logged` : appel sync, vérifie qu'un événement `data_exported` est inséré dans audit_log avec metadata correcte.
6. `test_export_rate_limited_within_5_minutes` : 2 appels successifs en < 5 minutes, vérifie 429 sur le 2ᵉ.
7. `test_export_download_token_signed_valid` : génère un token via `sign_export_url`, appelle `GET /api/me/data/export/download?token=xxx`, vérifie 200.
8. `test_export_download_token_expired` : token > 7j, vérifie 410.
9. `test_export_download_token_invalid` : token corrompu, vérifie 401.

### Frontend (Vitest)

1. `useDataPrivacy.useInventory` charge les compteurs et les expose via `ref`.
2. `<DataInventoryTable>` rend les 11 lignes avec le bon format.
3. `<DataExportButton>` affiche un spinner pendant la requête, change de texte selon sync/async.
