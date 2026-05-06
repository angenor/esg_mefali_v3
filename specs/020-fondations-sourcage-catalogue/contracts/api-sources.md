# Contract — API REST `/api/sources`

**Feature** : F01
**Path préfixe** : `/api/sources`
**Auth** : JWT (`get_current_user`) ; certaines routes nécessitent `require_admin`.

## Schémas Pydantic v2 (référence)

### `Source` (réponse complète)

```python
class Source(BaseModel):
    id: UUID
    url: HttpUrl
    title: str  # 1..500
    publisher: str  # 1..100
    version: str  # 1..50
    date_publi: date
    page: int | None  # >= 1 si non null
    section: str | None  # max 200
    captured_at: datetime
    captured_by: UUID
    verified_by: UUID | None
    verification_status: Literal["draft", "pending", "verified", "outdated"]
    verified_at: datetime | None
    outdated_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### `SourceCitation` (réponse compacte pour `cite_source`)

```python
class SourceCitation(BaseModel):
    id: UUID
    url: HttpUrl
    title: str
    publisher: str
    version: str
    date_publi: date
    page: int | None
```

### `SourceCreate` (entrée admin)

```python
class SourceCreate(BaseModel):
    url: HttpUrl
    title: str = Field(..., min_length=1, max_length=500)
    publisher: str = Field(..., min_length=1, max_length=100)
    version: str = Field(..., min_length=1, max_length=50)
    date_publi: date
    page: int | None = Field(None, ge=1)
    section: str | None = Field(None, max_length=200)
```

### `SourceUpdate` (entrée admin, draft seulement)

```python
class SourceUpdate(BaseModel):
    url: HttpUrl | None = None
    title: str | None = Field(None, min_length=1, max_length=500)
    publisher: str | None = Field(None, min_length=1, max_length=100)
    version: str | None = Field(None, min_length=1, max_length=50)
    date_publi: date | None = None
    page: int | None = Field(None, ge=1)
    section: str | None = Field(None, max_length=200)
```

### `SourceVerify` (entrée admin pour validation 4-yeux)

```python
class SourceVerify(BaseModel):
    """Pas de payload : la transition est déclenchée par l'identité de l'admin différente de captured_by."""
    pass
```

### `SourceMarkOutdated` (entrée admin)

```python
class SourceMarkOutdated(BaseModel):
    outdated_reason: str = Field(..., min_length=10, max_length=2000)
```

### `SourceListItem` (item de liste paginée)

```python
class SourceListItem(BaseModel):
    id: UUID
    title: str
    publisher: str
    version: str
    date_publi: date
    verification_status: Literal["draft","pending","verified","outdated"]
```

### `PaginatedSources`

```python
class PaginatedSources(BaseModel):
    items: list[SourceListItem]
    total: int
    page: int
    page_size: int
```

## Routes

### 1. `GET /api/sources`

**Description** : liste paginée des sources, filtrable.

**Auth** : utilisateur connecté.

**Query params** :

| Paramètre | Type | Défaut | Notes |
|-----------|------|--------|-------|
| `search` | `str` | None | Recherche full-text + embeddings (combinée par rrf). Nécessite ≥ 3 caractères. |
| `publisher` | `str` | None | Filtre exact. |
| `status` | `str` | None | Filtre `verification_status`. **Réservé admin** : un user PME ne peut spécifier que `status=verified` ou rien (forcé à `verified` côté backend). |
| `page` | `int` | 1 | Pagination. |
| `page_size` | `int` | 20 | Max 100. |

**Réponses** :

- `200 OK` → `PaginatedSources`
- `403 Forbidden` si l'utilisateur PME tente `status=draft|pending|outdated`.

**Comportement par rôle** :

- **PME** : la liste retournée est filtrée à `verification_status = 'verified'` (backend force le filtre, ignore tout `status` non-verified).
- **Admin** : peut consulter tous les statuts.

### 2. `GET /api/sources/{source_id}`

**Description** : détail d'une source.

**Auth** : utilisateur connecté.

**Réponses** :

- `200 OK` → `Source`
- `404 Not Found` si :
  - la source n'existe pas, OU
  - l'utilisateur PME demande une source dont `verification_status != 'verified'` (404 et non 403 pour ne pas révéler son existence — cf. FR-023).

### 3. `POST /api/sources`

**Description** : création d'une source (statut initial `draft`).

**Auth** : `require_admin`.

**Body** : `SourceCreate`.

**Réponses** :

- `201 Created` → `Source` (avec `verification_status = 'draft'`, `captured_by = current_user.id`).
- `409 Conflict` si l'URL existe déjà (UNIQUE constraint).
- `422 Unprocessable Entity` si validation Pydantic échoue.

### 4. `POST /api/sources/{source_id}/request-verification`

**Description** : transition `draft → pending` (le créateur ou tout autre admin peut déclencher).

**Auth** : `require_admin`.

**Body** : aucun.

**Réponses** :

- `200 OK` → `Source` mise à jour.
- `404` si source inexistante.
- `422` si la source n'est pas en `draft`.

### 5. `POST /api/sources/{source_id}/verify`

**Description** : transition `pending → verified`. Workflow 4-yeux : `current_user.id != captured_by`.

**Auth** : `require_admin`.

**Body** : `SourceVerify` (vide).

**Réponses** :

- `200 OK` → `Source` mise à jour avec `verified_by = current_user.id`, `verified_at = now()`.
- `403 Forbidden` si `current_user.id == captured_by` (workflow 4-yeux).
- `404` si source inexistante.
- `422` si la source n'est pas en `pending`.

### 6. `POST /api/sources/{source_id}/mark-outdated`

**Description** : transition `verified → outdated`.

**Auth** : `require_admin`.

**Body** : `SourceMarkOutdated`.

**Réponses** :

- `200 OK` → `Source` mise à jour.
- `404` si source inexistante.
- `422` si la source n'est pas en `verified`.

### 7. `PATCH /api/sources/{source_id}`

**Description** : modification d'une source en `draft` uniquement (avant validation).

**Auth** : `require_admin`.

**Body** : `SourceUpdate`.

**Réponses** :

- `200 OK` → `Source` mise à jour.
- `403` si la source n'est pas en `draft` (modification post-validation interdite ; il faut marquer `outdated` puis recréer une nouvelle entrée).
- `404` si source inexistante.

## Codes d'erreur unifiés

Format `application/problem+json` (cf. RFC 7807) ou format ESG Mefali existant (`{"detail": "..."}`). À aligner avec la convention déjà en vigueur dans `backend/app/api/`.

| HTTP | Code | Message FR |
|------|------|-----------|
| 401 | `unauthorized` | « Authentification requise » |
| 403 | `four_eyes_violation` | « Un administrateur ne peut pas valider sa propre source » |
| 403 | `pme_status_forbidden` | « Filtrage par statut réservé aux administrateurs » |
| 404 | `source_not_found` | « Source introuvable » |
| 409 | `url_already_exists` | « Une source avec cette URL existe déjà » |
| 422 | `invalid_state_transition` | « Transition d'état invalide depuis « {current_status} » » |
| 422 | `validation_error` | (détails Pydantic en français) |

## Tests d'intégration prévus

Fichier `backend/tests/integration/test_sources_api.py` :

1. `test_list_sources_pme_sees_only_verified` — PME voit uniquement `verified`.
2. `test_list_sources_admin_sees_all` — admin voit tous les statuts.
3. `test_get_source_pme_404_on_non_verified` — PME reçoit 404 sur `pending`.
4. `test_create_source_admin_only` — non-admin → 403.
5. `test_create_source_url_unique` — doublon URL → 409.
6. `test_request_verification_transition` — `draft → pending`.
7. `test_verify_source_four_eyes_violation` — créateur essaie de valider → 403.
8. `test_verify_source_success_by_other_admin` — autre admin → 200.
9. `test_mark_outdated_requires_reason` — sans `outdated_reason` → 422.
10. `test_search_sources_full_text` — recherche « ADEME » retourne sources ADEME.
11. `test_search_sources_publisher_filter` — `publisher=UEMOA` retourne uniquement UEMOA.
12. `test_patch_source_blocked_after_verification` — PATCH sur `verified` → 403.
