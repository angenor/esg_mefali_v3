# Data Model — F24 Extension Chrome MVP P1

**Migration Alembic** : `042_extension_url_patterns` (down_revision = `041_dossiers_offre`)

## Entités modifiées

### Fund (existante F07)

Ajout de la colonne :

| Field          | Type    | Nullable | Default | Description |
|----------------|---------|----------|---------|-------------|
| `url_patterns` | `JSONB` | YES      | `'[]'`  | Liste d'objets `{pattern: string, scope: "homepage" \| "submission_portal"}` |

**Validation Pydantic v2** : `list[FundUrlPattern]` avec `pattern` regex valide (compilable Python `re.compile`), `scope` enum strict.

**Index** : aucun (volume faible, scan séquentiel acceptable MVP).

### Intermediary (existante F07)

Ajout de la colonne `url_patterns` JSONB identique à `Fund`.

### RefreshToken (existante F02)

Ajout de la colonne :

| Field   | Type            | Nullable | Default | Description |
|---------|-----------------|----------|---------|-------------|
| `scope` | `VARCHAR(20)`   | NO       | `'web'` | Scope du token : `'web'` ou `'extension'`. CHECK constraint applicative. |

**Backfill** : tous les tokens existants reçoivent `scope='web'`.

**Index** : aucun supplémentaire (les requêtes filtrent déjà par `account_id` + `jti`).

### audit_source (enum F03)

Ajout de la valeur `'extension'` à l'ENUM PostgreSQL `audit_source` (existant : `'manual'`, `'llm'`, `'admin'`, `'import'`).

**Migration** : `ALTER TYPE audit_source ADD VALUE 'extension'` (PostgreSQL ≥ 9.1, atomique). En SQLite (tests), pas d'opération nécessaire (varchar libre).

## Seed (data migration)

Insertion idempotente dans la migration `042` (UPSERT par identifiant Fund/Intermediary) :

```python
SEED_URL_PATTERNS = {
    # Mapping fund.code/name → liste de patterns
    "BOAD": [
        {"pattern": r"^https://(www\.)?boad\.org/.*", "scope": "homepage"},
        {"pattern": r"^https://sunref\.boad\.org/.*", "scope": "submission_portal"},
    ],
    "GCF": [
        {"pattern": r"^https://(www\.)?greenclimate\.fund/.*", "scope": "homepage"},
    ],
    "AFD": [
        {"pattern": r"^https://(www\.)?afd\.fr/.*", "scope": "homepage"},
    ],
    "PNUD_AFRICA": [
        {"pattern": r"^https://(www\.)?undp\.org/africa.*", "scope": "homepage"},
    ],
}
SEED_INTERMEDIARY_URL_PATTERNS = {
    "ECOBANK_SUNREF": [
        {"pattern": r"^https://ecobank\.com/.*sunref.*", "scope": "submission_portal"},
    ],
}
```

Si un fonds/intermédiaire n'existe pas en BDD au moment du seed (environnement test vide), l'insertion est silencieusement skipée (idempotence).

## State transitions

Aucune nouvelle entité avec cycle de vie complexe. Les transitions impactées :

- `RefreshToken.scope` est immuable (créée avec une valeur, jamais modifiée).
- `Fund.url_patterns` et `Intermediary.url_patterns` sont éditables par admin (post-MVP via UI F09 ; MVP via SQL/seed).

## Validation rules

- Chaque `pattern` DOIT être une expression régulière compilable côté serveur (Python `re.compile`). Un échec de compilation lève une 422 lors de l'insertion/mise à jour admin (post-MVP F09).
- Le champ `scope` est un enum strict (`homepage` | `submission_portal`).
- La liste `url_patterns` peut être vide (équivalent : « aucun pattern saisi »).

## Index & Performance

- Endpoint `/detect` : SELECT all funds + intermediaries `WHERE publication_status='published'` puis matching regex en Python (volume MVP ≤ 50 entités, p95 < 200 ms confirmé). Cache mémoire process en post-MVP si nécessaire.

## Round-trip Alembic

- `up()` : ALTER TABLE funds + intermediaries (ADD COLUMN), ALTER TABLE refresh_tokens (ADD COLUMN + CHECK), ALTER TYPE audit_source ADD VALUE (PG only), seed UPSERT.
- `down()` : DROP COLUMN sur les 3 tables. Pas de DROP enum value (PostgreSQL ne le supporte pas nativement) — documenté en commentaire de migration : la valeur `'extension'` reste dans l'enum, sans impact car non utilisée après rollback applicatif.

## Schémas Pydantic (résumé)

```python
class FundUrlPattern(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    pattern: str = Field(min_length=1, max_length=500)
    scope: Literal["homepage", "submission_portal"]

class DetectRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    url: str = Field(min_length=1, max_length=2000)

class DetectResponse(BaseModel):
    offer_id: UUID
    offer_name: str
    source_id: UUID | None = None
    confidence: float = Field(ge=0.0, le=1.0)

class ProfileSnapshot(BaseModel):
    sector: str | None
    country: str | None
    projects: list[ProjectSnapshotItem]  # max 3

class ActiveApplicationItem(BaseModel):
    id: UUID
    offer_name: str
    status: str
    status_label_fr: str
    updated_at: datetime
    deep_link: str

class AuthExchangeRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)

class AuthExchangeResponse(BaseModel):
    access_token: str
    refresh_token: str
    scope: Literal["extension"]
    expires_in: int  # seconds, 30 days
```
