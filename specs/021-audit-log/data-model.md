# Data Model — F03 Audit Log Append-Only

## 1. Vue d'ensemble

Une seule nouvelle table : `audit_log`. Aucune modification structurelle des 9 tables auditables (les modèles SQLAlchemy se contentent d'ajouter `Auditable` comme classe parente). Deux nouveaux ENUMs PostgreSQL : `audit_action`, `audit_source`.

## 2. Table `audit_log`

### 2.1 Schéma SQL

```sql
CREATE TYPE audit_action AS ENUM ('create', 'update', 'delete', 'view_admin');
CREATE TYPE audit_source AS ENUM ('manual', 'llm', 'import', 'admin');

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    entity_type     VARCHAR(64) NOT NULL,
    entity_id       UUID NOT NULL,
    action          audit_action NOT NULL,
    field           VARCHAR(128),
    old_value       JSONB,
    new_value       JSONB,
    source_of_change audit_source NOT NULL,
    actor_metadata  JSONB
);

CREATE INDEX idx_audit_log_account_timestamp
    ON audit_log (account_id, timestamp DESC);
CREATE INDEX idx_audit_log_account_entity
    ON audit_log (account_id, entity_type, entity_id);
CREATE INDEX idx_audit_log_user_timestamp
    ON audit_log (user_id, timestamp DESC);
CREATE INDEX idx_audit_log_source_timestamp
    ON audit_log (source_of_change, timestamp DESC);
```

### 2.2 Triggers append-only (PL/pgSQL)

```sql
CREATE OR REPLACE FUNCTION raise_audit_log_no_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only ; UPDATE is forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION raise_audit_log_no_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only ; DELETE is forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_update();

CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_delete();
```

### 2.3 Permissions DB

```sql
-- Permettre INSERT et SELECT au rôle applicatif
GRANT INSERT, SELECT ON audit_log TO CURRENT_USER;
-- Retirer explicitement UPDATE et DELETE
REVOKE UPDATE, DELETE ON audit_log FROM CURRENT_USER;
```

Note : si `CURRENT_USER` est superuser/owner, le `REVOKE` est no-op (PostgreSQL ne peut pas restreindre un superuser). La migration Alembic journalise un `WARNING` dans ce cas. Le trigger reste la défense effective.

### 2.4 Row-Level Security (cohérent F02)

```sql
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;

-- Policy PME : voit ses propres événements
CREATE POLICY pme_access_own_account
    ON audit_log
    FOR SELECT
    USING (account_id = current_setting('app.current_account_id', true)::uuid);

CREATE POLICY pme_insert_own_account
    ON audit_log
    FOR INSERT
    WITH CHECK (account_id = current_setting('app.current_account_id', true)::uuid);

-- Policy Admin : voit tout
CREATE POLICY admin_full_access
    ON audit_log
    FOR SELECT
    USING (current_setting('app.current_role', true) = 'ADMIN');

CREATE POLICY admin_insert_anywhere
    ON audit_log
    FOR INSERT
    WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');
```

Aucune policy `UPDATE` ou `DELETE` n'est créée — les triggers et le REVOKE prévalent.

### 2.5 Sémantique des champs

| Champ | Quand peuplé | Exemple |
|---|---|---|
| `user_id` | Toujours (acteur ; pour `view_admin` c'est l'admin) | `<admin_uuid>` |
| `account_id` | Toujours (compte cible/propriétaire ; pour `view_admin` c'est le compte PME consulté) | `<pme_account_uuid>` |
| `entity_type` | Toujours | `"company_profile"`, `"fund_application"`, `"account"` (pour `view_admin`) |
| `entity_id` | Toujours | UUID de l'entité (ou de l'`Account` pour `view_admin`) |
| `action` | Toujours | `create`, `update`, `delete`, `view_admin` |
| `field` | NULL pour `create`/`delete`/`view_admin` ; nom du champ pour `update` | `"sector"`, NULL |
| `old_value` | NULL pour `create`/`view_admin` ; snapshot champ pour `update` ; snapshot complet pour `delete` | `"agriculture"`, NULL |
| `new_value` | NULL pour `delete`/`view_admin` ; snapshot champ pour `update` ; snapshot complet pour `create` | `"energie"`, NULL |
| `source_of_change` | Toujours | `manual`, `llm`, `import`, `admin` |
| `actor_metadata` | Optionnel ; toujours peuplé pour `llm` (`tool_name`, `conversation_id`) et pour `view_admin` (`endpoint`, `request_id`, `ip_address`, `user_agent`) | `{"tool_name": "create_fund_application", "conversation_id": "uuid"}` |

### 2.6 Troncature des valeurs > 10 KB

Côté Python (mixin `Auditable`), avant insertion :

```text
def _truncate_value(value: Any) -> dict | str | int | float | bool | None:
    serialized = json.dumps(value, default=_json_default)
    size = len(serialized.encode("utf-8"))
    if size <= 10 * 1024:
        return value
    preview = serialized[:8 * 1024]
    return {
        "_truncated": True,
        "_truncated_size": size,
        "_preview": preview,
    }
```

## 3. Modèle SQLAlchemy `AuditLog`

```text
class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    view_admin = "view_admin"


class AuditSourceOfChange(str, enum.Enum):
    manual = "manual"
    llm = "llm"
    import_ = "import"
    admin = "admin"


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_log"

    user_id: Mapped[UUID]              # FK users.id
    account_id: Mapped[UUID]           # FK accounts.id
    timestamp: Mapped[datetime]        # timestamptz default now()
    entity_type: Mapped[str]
    entity_id: Mapped[UUID]
    action: Mapped[AuditAction]
    field: Mapped[str | None]
    old_value: Mapped[dict | None]     # JSONB
    new_value: Mapped[dict | None]     # JSONB
    source_of_change: Mapped[AuditSourceOfChange]
    actor_metadata: Mapped[dict | None]  # JSONB
```

Note : `AuditLog` n'utilise PAS `TimestampMixin` (pas de `updated_at`, l'append-only le garantit). Le champ `timestamp` remplace `created_at` pour cohérence sémantique.

## 4. Mixin `Auditable`

### 4.1 Définition (marqueur)

```text
class Auditable:
    """Marqueur appliqué aux modèles métier capturés automatiquement par le listener before_flush.

    Ne définit aucune colonne ni méthode. Sert uniquement d'introspection typée
    pour le listener et pour le test CI test_auditable_models_whitelist_complete.
    """
    pass
```

### 4.2 Listener `before_flush`

```text
@event.listens_for(Session, "before_flush")
def capture_audit_log(session: Session, flush_context, instances) -> None:
    """Capture toutes les mutations sur les instances Auditable et insère audit_log."""
    audit_rows: list[dict] = []
    for obj in session.new:
        if isinstance(obj, AuditLog):
            continue  # anti-récursion
        if isinstance(obj, Auditable):
            audit_rows.append(_make_create_row(obj))
    for obj in session.dirty:
        if isinstance(obj, AuditLog):
            continue
        if isinstance(obj, Auditable):
            audit_rows.extend(_make_update_rows(obj))
    for obj in session.deleted:
        if isinstance(obj, AuditLog):
            continue
        if isinstance(obj, Auditable):
            audit_rows.append(_make_delete_row(obj))
    if audit_rows:
        session.execute(insert(AuditLog), audit_rows)
```

### 4.3 `AUDITABLE_MODELS` (whitelist)

```text
AUDITABLE_MODELS = frozenset({
    "CompanyProfile",
    "FundApplication",
    "ESGAssessment",
    "ESGCriterionScore",
    "CarbonAssessment",
    "CarbonEmissionEntry",
    "CreditScore",
    "ActionPlan",
    "ActionItem",
})

EXEMPT_MODELS = frozenset({
    # Catalogue F01 (pas de capture)
    "Source", "Indicator", "Criterion", "Formula", "Threshold", "Referential",
    "ReferentialIndicator", "EmissionFactor", "RequiredDocument",
    "SimulationFactor", "UnsourcedFlag",
    # Infrastructure (pas de capture)
    "User", "Account", "AccountInvitation", "RefreshToken",
    "Conversation", "Message", "InteractiveQuestion", "ToolCallLog",
    "Document", "Report",
    # Audit lui-même (anti-récursion)
    "AuditLog",
})
```

## 5. ContextVar `current_source_of_change`

```text
# app/core/audit_context.py
import contextlib
from contextvars import ContextVar
from typing import Literal

current_source_of_change: ContextVar[str] = ContextVar(
    "current_source_of_change", default="manual"
)


@contextlib.contextmanager
def source_of_change_scope(value: Literal["manual", "llm", "import", "admin"]):
    token = current_source_of_change.set(value)
    try:
        yield
    finally:
        current_source_of_change.reset(token)
```

## 6. Schémas Pydantic

```text
# app/modules/audit/schemas.py

class AuditEvent(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: UUID
    user_email: str | None
    account_id: UUID
    entity_type: str
    entity_id: UUID
    action: AuditAction
    field: str | None
    old_value: Any | None
    new_value: Any | None
    source_of_change: AuditSourceOfChange
    actor_metadata: dict[str, Any] | None


class AuditEventList(BaseModel):
    events: list[AuditEvent]
    total: int
    page: int
    limit: int


class AuditFilters(BaseModel):
    entity_type: str | None = None
    entity_id: UUID | None = None
    action: AuditAction | None = None
    source_of_change: AuditSourceOfChange | None = None
    since: datetime | None = None
    until: datetime | None = None
    page: int = 1
    limit: int = 50
    order: Literal["asc", "desc"] = "desc"

    # Admin-specific (utilisé sur GET /api/admin/audit) :
    account_id: UUID | None = None
    user_id: UUID | None = None
```

## 7. Diagramme relationnel

```text
+-----------+         +-------------+        +---------+
|   users   |         |   accounts  |        | (autre  |
|           |         |             |        | métier) |
+-----+-----+         +------+------+        +----+----+
      |                      |                    |
      | user_id              | account_id         |
      |                      |                    |
      v                      v                    v
 +---------------------------------------------------+
 |                  audit_log (append-only)          |
 +---------------------------------------------------+
 | id (PK), user_id (FK), account_id (FK),          |
 | timestamp, entity_type, entity_id, action,        |
 | field, old_value, new_value, source_of_change,    |
 | actor_metadata                                    |
 +---------------------------------------------------+
   - Triggers BEFORE UPDATE/DELETE → RAISE EXCEPTION
   - REVOKE UPDATE, DELETE ON audit_log FROM <role>
   - RLS : pme_access_own_account, admin_full_access
   - Indexes : (account_id, timestamp DESC) +3 autres
```

## 8. Migration Alembic `021_create_audit_log.py`

```text
revision: str = "021_audit_log"
down_revision: str = "020_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ENUMs
    op.execute("CREATE TYPE audit_action AS ENUM ('create','update','delete','view_admin')")
    op.execute("CREATE TYPE audit_source AS ENUM ('manual','llm','import','admin')")

    # 2. Table
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", postgresql.ENUM(name="audit_action", create_type=False), nullable=False),
        sa.Column("field", sa.String(128), nullable=True),
        sa.Column("old_value", postgresql.JSONB, nullable=True),
        sa.Column("new_value", postgresql.JSONB, nullable=True),
        sa.Column("source_of_change",
                  postgresql.ENUM(name="audit_source", create_type=False), nullable=False),
        sa.Column("actor_metadata", postgresql.JSONB, nullable=True),
    )

    # 3. Indexes
    op.create_index("idx_audit_log_account_timestamp", "audit_log",
                    ["account_id", sa.text("timestamp DESC")])
    op.create_index("idx_audit_log_account_entity", "audit_log",
                    ["account_id", "entity_type", "entity_id"])
    op.create_index("idx_audit_log_user_timestamp", "audit_log",
                    ["user_id", sa.text("timestamp DESC")])
    op.create_index("idx_audit_log_source_timestamp", "audit_log",
                    ["source_of_change", sa.text("timestamp DESC")])

    # 4. Triggers append-only
    op.execute("""
        CREATE OR REPLACE FUNCTION raise_audit_log_no_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only ; UPDATE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION raise_audit_log_no_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only ; DELETE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_update();
    """)
    op.execute("""
        CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_delete();
    """)

    # 5. Permissions (best-effort, no-op si superuser)
    try:
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM CURRENT_USER")
    except Exception as exc:
        op.get_context().impl.dialect.logger.warning(
            f"REVOKE UPDATE, DELETE failed: {exc}. Trigger remains effective."
        )

    # 6. RLS
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY pme_access_own_account ON audit_log FOR SELECT
            USING (account_id = current_setting('app.current_account_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY pme_insert_own_account ON audit_log FOR INSERT
            WITH CHECK (account_id = current_setting('app.current_account_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY admin_full_access ON audit_log FOR SELECT
            USING (current_setting('app.current_role', true) = 'ADMIN');
    """)
    op.execute("""
        CREATE POLICY admin_insert_anywhere ON audit_log FOR INSERT
            WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');
    """)


def downgrade() -> None:
    # Inverse exact, ordre inverse
    op.execute("DROP POLICY IF EXISTS admin_insert_anywhere ON audit_log")
    op.execute("DROP POLICY IF EXISTS admin_full_access ON audit_log")
    op.execute("DROP POLICY IF EXISTS pme_insert_own_account ON audit_log")
    op.execute("DROP POLICY IF EXISTS pme_access_own_account ON audit_log")
    op.execute("ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS raise_audit_log_no_delete")
    op.execute("DROP FUNCTION IF EXISTS raise_audit_log_no_update")
    op.drop_index("idx_audit_log_source_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_user_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_account_entity", table_name="audit_log")
    op.drop_index("idx_audit_log_account_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
    op.execute("DROP TYPE IF EXISTS audit_source")
    op.execute("DROP TYPE IF EXISTS audit_action")
```

## 9. Sécurité — modèle de menaces (synthèse)

| Menace | Vecteur | Mitigation F03 |
|---|---|---|
| Mutation silencieuse non tracée | Tool LangChain `db.commit()` direct sans service | Mixin global `before_flush` capte la mutation tant que l'instance passe par la Session ; audit du code identifie et migre les bypass restants. |
| Falsification d'une trace existante | `UPDATE audit_log SET ...` par un attaquant DB | Trigger `BEFORE UPDATE` + REVOKE UPDATE ; double barrière. |
| Effacement d'une trace | `DELETE FROM audit_log` par un attaquant DB | Trigger `BEFORE DELETE` + REVOKE DELETE. |
| Fuite inter-comptes | PME A voit audit_log de PME B | RLS `pme_access_own_account` (héritée F02). |
| Surveillance admin masquée | Admin consulte un compte PME sans laisser de trace | `record_admin_view` automatique sur endpoints admin sensibles ; visible côté PME. |
| Volume DoS | 100 000+ insertions audit_log/jour saturent la DB | Indexes ciblés ; pagination ; partitionnement post-MVP si nécessaire. |
| Données personnelles dans le log (RGPD) | `old_value`/`new_value` peuvent contenir des PII | Limitation MVP documentée ; mécanisme DPO post-MVP (anonymisation tombstone). |
