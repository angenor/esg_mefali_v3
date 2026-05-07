# Phase 1 : Data Model — F08 Attestation Vérifiable Ed25519

**Spec** : [spec.md](./spec.md)
**Plan** : [plan.md](./plan.md)
**Date** : 2026-05-07

## Schéma SQL

### Table `attestations`

```sql
CREATE TABLE attestations (
    id                       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id               UUID            NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    user_id                  UUID            NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    attestation_type         VARCHAR(32)     NOT NULL,
    payload                  JSONB           NOT NULL,
    referential_snapshot     JSONB           NOT NULL DEFAULT '[]'::jsonb,
    pdf_path                 VARCHAR(500)    NOT NULL,
    pdf_hash_sha256          CHAR(64)        NOT NULL,
    signature_ed25519        VARCHAR(255)    NOT NULL,
    public_key_id            VARCHAR(50)     NOT NULL DEFAULT 'v1',
    qr_code_path             VARCHAR(500)    NOT NULL,
    valid_from               TIMESTAMPTZ     NOT NULL DEFAULT now(),
    valid_until              TIMESTAMPTZ     NOT NULL,
    revoked_at               TIMESTAMPTZ,
    revoked_reason           VARCHAR(500),
    revoked_by_user_id       UUID            REFERENCES users(id) ON DELETE SET NULL,
    verification_url         VARCHAR(500)    NOT NULL,
    display_id               VARCHAR(20)     NOT NULL,  -- "ATT-YYYY-NNNNN" affiché
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),

    -- Contraintes CHECK
    CONSTRAINT attestation_type_chk CHECK (
        attestation_type IN ('credit_score', 'esg_assessment', 'combined')
    ),
    CONSTRAINT pdf_hash_sha256_format_chk CHECK (
        pdf_hash_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT valid_until_after_from_chk CHECK (
        valid_until > valid_from
    ),
    CONSTRAINT revoked_consistency_chk CHECK (
        (revoked_at IS NULL AND revoked_reason IS NULL AND revoked_by_user_id IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL AND revoked_by_user_id IS NOT NULL)
    ),
    CONSTRAINT display_id_format_chk CHECK (
        display_id ~ '^ATT-[0-9]{4}-[0-9]{5}$'
    ),
    CONSTRAINT public_key_id_format_chk CHECK (
        public_key_id ~ '^v[0-9]+$'
    )
);

-- Indexes
CREATE INDEX idx_attestations_account_valid_until ON attestations(account_id, valid_until);
CREATE INDEX idx_attestations_revoked_at ON attestations(revoked_at) WHERE revoked_at IS NOT NULL;
CREATE INDEX idx_attestations_user_id ON attestations(user_id);
CREATE INDEX idx_attestations_account_year ON attestations(account_id, EXTRACT(year FROM valid_from));
CREATE UNIQUE INDEX idx_attestations_display_id ON attestations(display_id);

-- RLS PostgreSQL (héritée F02)
ALTER TABLE attestations ENABLE ROW LEVEL SECURITY;
ALTER TABLE attestations FORCE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account ON attestations
    FOR ALL
    USING (account_id = current_setting('app.current_account_id')::uuid);

CREATE POLICY admin_full_access ON attestations
    FOR ALL
    TO authenticated
    USING (current_setting('app.is_admin', true)::boolean = true);
```

### Description des colonnes

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant unique exposé publiquement (= `attestation_id` dans les URLs `/verify/{id}`) |
| `account_id` | UUID | Multi-tenant F02. Sans ce champ, RLS PostgreSQL bloque la lecture cross-tenant |
| `user_id` | UUID | Identité de la personne ayant déclenché la génération (PME ou admin) |
| `attestation_type` | VARCHAR(32) | Enum applicatif : `credit_score`, `esg_assessment`, `combined` |
| `payload` | JSONB | Snapshot complet : `{scores: {combined, solvability, green_impact, esg_global}, projects_summary: [...], etc.}`. Inclus dans la signature canonique |
| `referential_snapshot` | JSONB | Snapshot des référentiels utilisés avec versions : `[{name: "ESG Mefali", version: "1.2", published_at: "2026-03-15"}, {name: "GCF", version: "2.3", published_at: "2025-11-01"}]` |
| `pdf_path` | VARCHAR(500) | Chemin local du PDF généré (ex. `/uploads/attestations/pdfs/{id}.pdf`). Post-MVP : URL S3 |
| `pdf_hash_sha256` | CHAR(64) | Hash SHA-256 hexadécimal lowercase du PDF généré (calcul après écriture finale du fichier) |
| `signature_ed25519` | VARCHAR(255) | Signature Ed25519 base64 du payload canonique (longueur signature Ed25519 = 64 bytes → base64 ~88 chars + padding). VARCHAR(255) avec marge confortable. |
| `public_key_id` | VARCHAR(50) | Identifiant de la clé publique utilisée (`v1` pour le MVP, `v2`, `v3`, ... pour les rotations post-MVP). Permet la vérification des anciennes attestations après rotation. |
| `qr_code_path` | VARCHAR(500) | Chemin local du PNG du QR (ex. `/uploads/attestations/qr/{id}.png`) |
| `valid_from` | TIMESTAMPTZ | Date de début de validité (= `now()` à la création) |
| `valid_until` | TIMESTAMPTZ | Date de fin de validité (= `valid_from + ATTESTATION_VALIDITY_DAYS` (365 par défaut)) |
| `revoked_at` | TIMESTAMPTZ | NULL tant que non révoquée. `now()` à la révocation. |
| `revoked_reason` | VARCHAR(500) | NULL tant que non révoquée. Raison fournie par PME ou admin (min 10 chars). |
| `revoked_by_user_id` | UUID | NULL tant que non révoquée. FK vers `users(id)`. La page publique expose seulement le `role` (pme/admin) pas l'identité. |
| `verification_url` | VARCHAR(500) | URL complète de vérification (= `{ATTESTATION_VERIFICATION_BASE_URL}/verify/{id}`). Stockée pour faciliter la régénération du QR si besoin. |
| `display_id` | VARCHAR(20) | Identifiant lisible humain `ATT-YYYY-NNNNN` (calcul scopé `account_id + année`). UNIQUE car il apparaît sur le PDF visible. |
| `created_at` / `updated_at` | TIMESTAMPTZ | Audit standard. `created_at` = date de génération ; `updated_at` mis à jour à chaque revocation |

### Modèle SQLAlchemy

`backend/app/models/attestation.py` :

```python
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Char, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auditable import Auditable
from app.core.base import Base
from app.core.mixins import TimestampMixin, UUIDMixin
from app.core.config import settings


class Attestation(Base, UUIDMixin, TimestampMixin, Auditable):
    __tablename__ = "attestations"

    account_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    attestation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    referential_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_hash_sha256: Mapped[str] = mapped_column(Char(64), nullable=False)
    signature_ed25519: Mapped[str] = mapped_column(String(255), nullable=False)
    public_key_id: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    qr_code_path: Mapped[str] = mapped_column(String(500), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    revoked_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verification_url: Mapped[str] = mapped_column(String(500), nullable=False)
    display_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    # Relationships (lazy/eager non chargés par défaut, on n'a pas besoin de fetch automatique)
    user = relationship("User", foreign_keys=[user_id], lazy="noload")
    revoked_by_user = relationship("User", foreign_keys=[revoked_by_user_id], lazy="noload")
    account = relationship("Account", lazy="noload")
```

### Pattern Auditable (héritage F03)

`Auditable` mixin déclenche un listener `before_flush` qui inspecte `INSERT`/`UPDATE`/`DELETE` sur `Attestation` et crée des entrées `AuditLog` :
- À la création : `action='create'`, `entity_type='attestations'`, `entity_id=attestation.id`, `actor_user_id=user.id`, `actor_role='pme' | 'admin'`, `source_of_change ∈ {'manual', 'llm'}`, `new_value={attestation_type, valid_from, valid_until, public_key_id}`
- À la révocation : `action='revoke'`, `field='revoked_at'`, `old_value=null`, `new_value={revoked_at, revoked_reason}`, `actor_role='pme' | 'admin'`

## Modifications structurelles requises

### 1. Migration Alembic `026_create_attestations.py`

```python
"""Create attestations table for F08 verifiable attestation feature

Revision ID: 026_create_attestations
Revises: <conditional>  # 025_create_projects si F06 mergé, sinon 024_carbone_mix_uemoa
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "026_create_attestations"
down_revision = "025_create_projects"  # ajusté au merge si F06 pas encore mergé
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attestation_type", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("referential_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("pdf_path", sa.String(500), nullable=False),
        sa.Column("pdf_hash_sha256", sa.CHAR(64), nullable=False),
        sa.Column("signature_ed25519", sa.String(255), nullable=False),
        sa.Column("public_key_id", sa.String(50), nullable=False, server_default="v1"),
        sa.Column("qr_code_path", sa.String(500), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(500), nullable=True),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verification_url", sa.String(500), nullable=False),
        sa.Column("display_id", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "attestation_type IN ('credit_score', 'esg_assessment', 'combined')",
            name="attestation_type_chk",
        ),
        sa.CheckConstraint(
            "pdf_hash_sha256 ~ '^[0-9a-f]{64}$'",
            name="pdf_hash_sha256_format_chk",
        ),
        sa.CheckConstraint(
            "valid_until > valid_from",
            name="valid_until_after_from_chk",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL AND revoked_by_user_id IS NULL) "
            "OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL AND revoked_by_user_id IS NOT NULL)",
            name="revoked_consistency_chk",
        ),
        sa.CheckConstraint(
            "display_id ~ '^ATT-[0-9]{4}-[0-9]{5}$'",
            name="display_id_format_chk",
        ),
        sa.CheckConstraint(
            "public_key_id ~ '^v[0-9]+$'",
            name="public_key_id_format_chk",
        ),
    )
    op.create_index("idx_attestations_account_valid_until", "attestations", ["account_id", "valid_until"])
    op.create_index(
        "idx_attestations_revoked_at",
        "attestations",
        ["revoked_at"],
        postgresql_where=sa.text("revoked_at IS NOT NULL"),
    )
    op.create_index("idx_attestations_user_id", "attestations", ["user_id"])
    op.create_index(
        "idx_attestations_account_year",
        "attestations",
        ["account_id", sa.text("EXTRACT(year FROM valid_from)")],
    )
    op.create_index("idx_attestations_display_id", "attestations", ["display_id"], unique=True)

    # RLS PostgreSQL (réutilise les helpers F02)
    op.execute("ALTER TABLE attestations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE attestations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY pme_access_own_account ON attestations
        FOR ALL
        USING (account_id = current_setting('app.current_account_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY admin_full_access ON attestations
        FOR ALL
        USING (current_setting('app.is_admin', true)::boolean = true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS admin_full_access ON attestations")
    op.execute("DROP POLICY IF EXISTS pme_access_own_account ON attestations")
    op.drop_index("idx_attestations_display_id", table_name="attestations")
    op.drop_index("idx_attestations_account_year", table_name="attestations")
    op.drop_index("idx_attestations_user_id", table_name="attestations")
    op.drop_index("idx_attestations_revoked_at", table_name="attestations", postgresql_where=sa.text("revoked_at IS NOT NULL"))
    op.drop_index("idx_attestations_account_valid_until", table_name="attestations")
    op.drop_table("attestations")
```

### 2. Configuration `core/config.py`

Ajouter 4 nouvelles variables d'environnement :

```python
class Settings(BaseSettings):
    # ... existant ...

    # F08 — Attestation
    ATTESTATION_PRIVATE_KEY_PEM: str = ""  # Doit être renseignée en prod (sinon l'app refuse de démarrer)
    ATTESTATION_PUBLIC_KEY_ID: str = "v1"
    ATTESTATION_VALIDITY_DAYS: int = 365
    ATTESTATION_VERIFICATION_BASE_URL: str = "https://esg-mefali.com"

    @field_validator("ATTESTATION_PRIVATE_KEY_PEM", mode="after")
    @classmethod
    def validate_attestation_key(cls, v: str, info) -> str:
        if info.data.get("ENV") == "production" and not v:
            raise ValueError(
                "ATTESTATION_PRIVATE_KEY_PEM is required in production. "
                "Run scripts/generate_attestation_keypair.py to bootstrap."
            )
        return v
```

### 3. Helpers de Auditable

`app/core/auditable.py` :
- Ajouter `Attestation` à `AUDITABLE_MODELS`.
- Le listener `before_flush` capture automatiquement les `INSERT`/`UPDATE` sur la table.

## Vérifications post-migration

- `SELECT * FROM pg_indexes WHERE tablename='attestations'` → 5 indexes attendus + 1 unique sur `display_id`.
- `SELECT * FROM pg_policies WHERE tablename='attestations'` → 2 policies (`pme_access_own_account`, `admin_full_access`).
- `\d+ attestations` → 21 colonnes, 6 contraintes CHECK.
- Test `up/down/up` réversible : `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` produit la même structure (validé via test `test_alembic_f08.py`).

## Schémas Pydantic (extrait — voir contracts/ pour le détail)

```python
# AttestationCreate (input POST /api/attestations)
class AttestationCreate(BaseModel):
    attestation_type: Literal["credit_score", "esg_assessment", "combined"]

# AttestationRevoke (input POST /api/attestations/{id}/revoke)
class AttestationRevoke(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)

# VerificationResult — discriminated union public DTO
class _VerificationBase(BaseModel):
    status: str
    verified_at: datetime
    message: str

class AuthenticVerification(_VerificationBase):
    status: Literal["authentic"]
    attestation_id: UUID
    attestation_type: Literal["credit_score", "esg_assessment", "combined"]
    valid_from: datetime
    valid_until: datetime
    issued_at: datetime
    scores: dict[str, int]  # {combined, solvability, green_impact, esg_global}
    referentials: list[dict[str, str]]  # [{name, version, published_at}]
    pdf_hash_sha256: str
    public_key_id: str

class RevokedVerification(_VerificationBase):
    status: Literal["revoked"]
    attestation_id: UUID
    revoked_at: datetime
    revoked_reason: str
    revoked_by_role: Literal["pme", "admin"]
    # ... champs de AuthenticVerification (sauf signature) ...

class ExpiredVerification(_VerificationBase):
    status: Literal["expired"]
    attestation_id: UUID
    expired_since: datetime
    # ... champs de AuthenticVerification ...

class InvalidVerification(_VerificationBase):
    status: Literal["invalid"]

VerificationResult = Annotated[
    Union[AuthenticVerification, RevokedVerification, ExpiredVerification, InvalidVerification],
    Field(discriminator="status"),
]
```
