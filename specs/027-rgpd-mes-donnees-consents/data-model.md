# Phase 1 — Data Model : F05 RGPD Mes Données + Consentements + Export/Suppression

Date : 2026-05-07
Branche : `feat/F05-rgpd-mes-donnees-consents` (alias SpecKit `027-rgpd-mes-donnees-consents`)

## Vue d'ensemble

F05 introduit **une seule nouvelle table** (`consents`) et **étend la table `accounts`** (créée par F02) avec 3 nouvelles colonnes (`deletion_scheduled_at`, `deleted_at`, `purge_in_progress`). Aucun nouvel index hors les nécessités de lookups ciblés. Deux nouveaux types enum PostgreSQL : `consent_type_enum` et `legal_basis_enum`.

## Diagramme entité-relation simplifié

```
                ┌─────────────────────────────────────────┐
                │ accounts (étendue F05)                  │
                │─────────────────────────────────────────│
                │ id (UUID PK)                            │
                │ ... (colonnes F02)                      │
                │ + deletion_scheduled_at (timestamptz?)  │  ← F05
                │ + deleted_at (timestamptz?)             │  ← F05
                │ + purge_in_progress (bool, default false)│ ← F05
                └─────────────┬───────────────────────────┘
                              │ 1
                              │
                              │ N
                ┌─────────────┴───────────────────────────┐
                │ consents (nouvelle table F05)           │
                │─────────────────────────────────────────│
                │ id (UUID PK)                            │
                │ account_id (UUID FK accounts.id NN)     │
                │ user_id (UUID FK users.id NN)           │
                │ consent_type (consent_type_enum NN)     │
                │ granted (bool NN)                       │
                │ granted_at (timestamptz NN, def now())  │
                │ revoked_at (timestamptz?)               │
                │ legal_basis (legal_basis_enum NN)       │
                │ version (varchar(16) NN)                │
                │ metadata (jsonb NN, def '{}')           │
                │ created_at, updated_at (audit standard) │
                └─────────────────────────────────────────┘

                ┌─────────────────────────────────────────┐
                │ audit_log (étendue par F03 — pas modifiée│
                │ par F05 mais ANONYMISÉE à la purge)     │
                │─────────────────────────────────────────│
                │ ... (colonnes F03)                      │
                │ user_id (UUID, → SET NULL post-purge)   │
                │ account_id (UUID, → SET NULL post-purge)│
                │ payload (jsonb, → filtré post-purge)    │
                └─────────────────────────────────────────┘
```

## Types Enum

### `consent_type_enum`

```sql
CREATE TYPE consent_type_enum AS ENUM (
    'profile_analysis',
    'document_analysis_ai',
    'mobile_money_analysis',
    'photos_ia_analysis',
    'public_data_analysis',
    'credit_certificate_generation',
    'product_communications'
);
```

**Sémantique** :

| Valeur                         | Default | Use case                                                                  | Base légale par défaut |
|--------------------------------|---------|---------------------------------------------------------------------------|------------------------|
| `profile_analysis`             | `true`  | Analyse profil entreprise pour matching financements                      | `contract`             |
| `document_analysis_ai`         | `true`  | Analyse des documents uploadés par l'IA pour scoring ESG                  | `contract`             |
| `mobile_money_analysis`        | `false` | Analyse flux Mobile Money pour scoring crédit (F18)                       | `consent`              |
| `photos_ia_analysis`           | `false` | Analyse photos exploitation par IA pour scoring crédit (F18)              | `consent`              |
| `public_data_analysis`         | `false` | Analyse données publiques (réseaux sociaux, avis) pour scoring (F18)      | `consent`              |
| `credit_certificate_generation`| `true`  | Génération automatique d'attestation crédit transmissible (F08)           | `contract`             |
| `product_communications`       | `false` | Communications produit / newsletter                                       | `consent`              |

### `legal_basis_enum`

```sql
CREATE TYPE legal_basis_enum AS ENUM (
    'consent',
    'contract',
    'legal_obligation',
    'legitimate_interest'
);
```

**Sémantique** : conforme aux articles 6.1.a / 6.1.b / 6.1.c / 6.1.f du RGPD.

## Table `consents` (NOUVELLE)

### DDL SQL (référence — implémentée via Alembic)

```sql
CREATE TABLE consents (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL,
    user_id         UUID            NOT NULL,
    consent_type    consent_type_enum NOT NULL,
    granted         BOOLEAN         NOT NULL,
    granted_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ     NULL,
    legal_basis     legal_basis_enum NOT NULL,
    version         VARCHAR(16)     NOT NULL,
    metadata        JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_consents_account
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    CONSTRAINT fk_consents_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_consents_revoked_after_granted
        CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

-- Index partial pour lookup « consentement actif »
CREATE INDEX idx_consents_active
    ON consents (account_id, consent_type)
    WHERE revoked_at IS NULL AND granted = true;

-- Unicité d'un consentement actif par (account_id, consent_type)
CREATE UNIQUE INDEX uq_consents_one_active
    ON consents (account_id, consent_type)
    WHERE revoked_at IS NULL AND granted = true;

-- Trigger pour mise à jour automatique de updated_at (réutilise pattern projet)
CREATE TRIGGER trg_consents_updated_at
    BEFORE UPDATE ON consents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Modèle SQLAlchemy (référence)

```python
# backend/app/models/consent.py
import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Column, Boolean, String, DateTime, Enum as SAEnum, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base


CONSENT_TYPE_VALUES = (
    'profile_analysis',
    'document_analysis_ai',
    'mobile_money_analysis',
    'photos_ia_analysis',
    'public_data_analysis',
    'credit_certificate_generation',
    'product_communications',
)

LEGAL_BASIS_VALUES = (
    'consent',
    'contract',
    'legal_obligation',
    'legitimate_interest',
)


class Consent(Base):
    __tablename__ = "consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    consent_type = Column(SAEnum(*CONSENT_TYPE_VALUES, name="consent_type_enum", create_type=False), nullable=False)
    granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    legal_basis = Column(SAEnum(*LEGAL_BASIS_VALUES, name="legal_basis_enum", create_type=False), nullable=False)
    version = Column(String(16), nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="chk_consents_revoked_after_granted"),
        Index("idx_consents_active", "account_id", "consent_type",
              postgresql_where="revoked_at IS NULL AND granted = true"),
        Index("uq_consents_one_active", "account_id", "consent_type",
              unique=True,
              postgresql_where="revoked_at IS NULL AND granted = true"),
    )
```

### Invariants métier

1. **Au plus un consentement actif** par couple `(account_id, consent_type)`. Garanti par `uq_consents_one_active`.
2. **`granted=true` + `revoked_at IS NULL`** = consentement actif. Toute autre combinaison = inactif.
3. **`revoked_at`** est strictement postérieure à `granted_at`. Garanti par `chk_consents_revoked_after_granted`.
4. **`metadata`** suit le schéma : `{"ip": "x.x.x.x", "user_agent": "...", "request_id": "uuid"}`. Validation côté Pydantic.
5. **`version`** suit le pattern semver simplifié : `vMAJOR.MINOR` (ex: `v1.0`, `v2.1`). Limité à 16 chars.

### Lookup principal — `require_consent`

```sql
SELECT 1 FROM consents
WHERE account_id = :account_id
  AND consent_type = :consent_type
  AND revoked_at IS NULL
  AND granted = true
LIMIT 1;
```

Utilise l'index `uq_consents_one_active` (B-tree partial). Performance : O(log n) avec n ≤ 100 PME × 7 types = 700 rows max.

## Table `accounts` (ÉTENDUE)

### Colonnes ajoutées par F05

| Colonne                | Type            | Nullable | Default | Index                                                   |
|-----------------------|-----------------|----------|---------|---------------------------------------------------------|
| `deletion_scheduled_at` | `TIMESTAMPTZ`   | YES      | NULL    | Partial: `WHERE deletion_scheduled_at IS NOT NULL`      |
| `deleted_at`            | `TIMESTAMPTZ`   | YES      | NULL    | Partial: `WHERE deleted_at IS NOT NULL`                 |
| `purge_in_progress`     | `BOOLEAN`       | NO       | false   | Partial: `WHERE purge_in_progress = true`               |

### DDL SQL (référence)

```sql
ALTER TABLE accounts
    ADD COLUMN deletion_scheduled_at TIMESTAMPTZ NULL,
    ADD COLUMN deleted_at TIMESTAMPTZ NULL,
    ADD COLUMN purge_in_progress BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX idx_accounts_deletion_scheduled
    ON accounts (deletion_scheduled_at)
    WHERE deletion_scheduled_at IS NOT NULL;

CREATE INDEX idx_accounts_deleted
    ON accounts (deleted_at)
    WHERE deleted_at IS NOT NULL;

CREATE INDEX idx_accounts_purge_in_progress
    ON accounts (purge_in_progress)
    WHERE purge_in_progress = true;
```

### Lookup principal — Cron purge

```sql
SELECT id FROM accounts
WHERE deletion_scheduled_at IS NOT NULL
  AND deletion_scheduled_at < now()
  AND deleted_at IS NULL
ORDER BY deletion_scheduled_at ASC;
```

Utilise l'index `idx_accounts_deletion_scheduled`. Volume attendu : ≤ 10 lignes par exécution quotidienne.

## Table `audit_log` — modifications via purge (PAS DE DDL)

F05 ne modifie pas le schéma de `audit_log` (créé par F03). Lors de la purge, l'audit_log est **modifié en place** :

```sql
UPDATE audit_log
SET user_id = NULL,
    account_id = NULL,
    payload = jsonb_strip_pii(payload, '<list_of_pii_fields>')
WHERE account_id = :account_id_being_purged;
```

Une fonction Python `anonymize_payload(payload: dict, pii_fields: set) -> dict` est définie côté `app/modules/me/purge.py` qui retire les champs whitelistés. Liste actuelle de champs PII connus :
- `email`, `phone`, `mobile_number`, `name`, `first_name`, `last_name`
- `address`, `street`, `city`, `country`
- `ip`, `ip_address`, `user_agent`
- `bank_account`, `bank_iban`, `mobile_money_number`
- `signature`, `signed_by`, `gps_lat`, `gps_lng`
- Tout champ se terminant par `_email`, `_phone`, `_name`

Les autres champs (`entity_type`, `action`, `entity_id`, `status`, `error_code`, etc.) sont conservés.

## Schémas Pydantic (référence)

### Inputs

```python
# backend/app/modules/me/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


class ConsentGrantRequest(BaseModel):
    """Body de POST /api/me/consents/{type}/grant — vide, métadonnées dérivées du request."""
    model_config = ConfigDict(extra="forbid")


class ConsentRevokeRequest(BaseModel):
    """Body de POST /api/me/consents/{type}/revoke — vide."""
    model_config = ConfigDict(extra="forbid")


class VerifyPasswordRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class ScheduleDeletionRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)
    confirmation_text: Literal["SUPPRIMER"] = Field(..., description="Doit être exactement 'SUPPRIMER'")


class CancelDeletionRequest(BaseModel):
    """Body de POST /api/me/account/cancel-deletion — vide (auth ou token email)."""
    token: Optional[str] = Field(None, description="Token signé optionnel pour annulation no-auth via lien email")


class RegisterRequest(BaseModel):
    """Extension RegisterRequest (existant) avec privacy_policy_accepted."""
    email: str
    password: str
    company_name: str
    privacy_policy_accepted: bool = Field(..., description="Doit être true. Required par RGPD.")
    privacy_policy_version: str = Field(default="v1.0", max_length=16)
```

### Outputs

```python
class InventoryCounts(BaseModel):
    profile: int = 0
    projects: int = 0
    applications: int = 0
    esg_assessments: int = 0
    carbon_assessments: int = 0
    credit_scores: int = 0
    documents: int = 0
    conversations: int = 0
    messages: int = 0
    attestations: int = 0
    consents: int = 0


class InventoryLastModified(BaseModel):
    profile: Optional[datetime] = None
    projects: Optional[datetime] = None
    # ... etc


class InventoryResponse(BaseModel):
    counts: InventoryCounts
    last_modified: InventoryLastModified


class ConsentItem(BaseModel):
    type: Literal[
        "profile_analysis", "document_analysis_ai", "mobile_money_analysis",
        "photos_ia_analysis", "public_data_analysis", "credit_certificate_generation",
        "product_communications"
    ]
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    legal_basis: Literal["consent", "contract", "legal_obligation", "legitimate_interest"]
    version: str
    label: str        # libellé français, dérivé du type
    description: str  # description française, dérivée du type


class ScheduleDeletionResponse(BaseModel):
    deletion_scheduled_at: datetime
    cancel_url: Optional[str] = None  # URL signée 7j si retournée


class ExportSyncResponse(BaseModel):
    """Renvoyé en cas d'export synchrone (≤100 MB) — body est en réalité bytes ZIP."""
    pass


class ExportAsyncResponse(BaseModel):
    job_id: UUID  # UUID dérivé de l'audit_log event
    status: Literal["pending", "ready"]
    estimated_completion_at: Optional[datetime] = None
    message: str
```

## Mapping vers FastAPI dependencies

```python
# backend/app/core/consent.py

from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_current_user
from typing import Callable


CONSENT_TYPE_LABELS = {
    "mobile_money_analysis": "Mobile Money",
    "photos_ia_analysis": "Photos IA",
    "public_data_analysis": "Données publiques",
    "credit_certificate_generation": "Génération attestation crédit",
    "product_communications": "Communications produit",
    "profile_analysis": "Analyse profil",
    "document_analysis_ai": "Analyse documents IA",
}


async def require_consent(
    db: AsyncSession,
    account_id: UUID,
    consent_type: str,
) -> None:
    """Vérifie qu'un consentement actif existe ; lève HTTPException(403) sinon."""
    result = await db.execute(
        select(Consent).where(
            Consent.account_id == account_id,
            Consent.consent_type == consent_type,
            Consent.revoked_at.is_(None),
            Consent.granted.is_(True),
        ).limit(1)
    )
    consent = result.scalar_one_or_none()
    if not consent:
        label = CONSENT_TYPE_LABELS.get(consent_type, consent_type)
        raise HTTPException(
            status_code=403,
            detail={
                "detail": f"Consentement {label} requis pour cette analyse",
                "consent_type": consent_type,
                "settings_url": "/mes-donnees/consentements",
            },
        )


def consent_dependency(consent_type: str) -> Callable:
    """Factory pour dépendance FastAPI déclarative."""
    async def _dep(
        db: AsyncSession = Depends(get_db),
        user = Depends(get_current_user),
    ):
        await require_consent(db, user.account_id, consent_type)
    return _dep
```

## Stratégie d'évolution

- **Ajouter un 8ᵉ consent_type** : migration Alembic dédiée `op.execute("ALTER TYPE consent_type_enum ADD VALUE 'xxx_yyy'")`. Côté Python : ajouter à `CONSENT_TYPE_VALUES` + `CONSENT_TYPE_LABELS`. Aucune mutation des données existantes.
- **Migration vers Celery/RQ pour exports asynchrones** : créera la table `data_export_jobs(id, account_id, status, ...)` post-MVP en même temps que F19.
- **Suppression de `purge_in_progress`** : envisageable post-MVP si le cron migre vers Celery (lock distribué plus propre). Pour le MVP, conservé pour idempotence simple.

## Volumétrie estimée

| Table        | Lignes attendues post-MVP (100 PME pilote) | Croissance attendue (1 an post-MVP) |
|--------------|---------------------------------------------|-------------------------------------|
| `consents`   | ~700 (100 × 7)                              | × 10 (1000 PME → 7000 lignes)       |
| `accounts`   | (étendue) ~100 lignes                       | × 10 (1000 PME)                     |
| `audit_log`  | ~50000 lignes (pas modifiées par F05)       | × 100 (5M lignes — anonymisation par batch lors de la purge ; pas d'impact significatif) |

## Tests d'invariants BDD (référence — implémentés en pytest)

1. **Test : un seul consent actif** : insérer 2 rows `consents` avec même `(account_id, consent_type)` et `granted=true, revoked_at=NULL` → la 2ᵉ doit échouer avec `IntegrityError` (violation `uq_consents_one_active`).
2. **Test : revoked_at >= granted_at** : insérer un row avec `revoked_at < granted_at` → doit échouer avec `IntegrityError` (violation `chk_consents_revoked_after_granted`).
3. **Test : cascade FK accounts → consents** : supprimer un `accounts` row → tous les `consents` liés doivent être supprimés (ON DELETE CASCADE).
4. **Test : SET NULL FK users → consents** : supprimer un `users` row → les `consents.user_id` correspondants doivent passer à NULL (l'historique est conservé).
5. **Test : enum check** : INSERT avec `consent_type='invalid_type'` → doit échouer avec `InvalidTextRepresentation`.
6. **Test : index partial actif** : EXPLAIN ANALYZE sur la requête `require_consent` doit montrer un Index Scan sur `uq_consents_one_active`.
