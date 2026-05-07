# Data Model — F09 Back-Office Admin Complet

**Date** : 2026-05-07

## 1. Colonne `publication_status` (sur 10 tables existantes)

### Schéma

```sql
ALTER TABLE <table>
ADD COLUMN publication_status VARCHAR(20)
NOT NULL DEFAULT 'draft'
CHECK (publication_status IN ('draft', 'published'));

CREATE INDEX ix_<table>_publication_status ON <table> (publication_status);
```

### Tables concernées (10)

| Table | Note |
|-------|------|
| `funds` | Catalogue principal côté PME |
| `intermediaries` | Liés aux funds |
| `offers` | Couples Fund + Intermediary (F07) |
| `referentials` | ESG Mefali, GCF, IFC, BOAD, GRI, ODD |
| `indicators` | Atomic indicators (e.g. % déchets recyclés) |
| `criteria` | Conditions logiques sur indicators |
| `templates` | Templates dossiers (F15/F23) |
| `emission_factors` | ADEME, IPCC (F17) |
| `simulation_factors` | Constants simulateur (F16) |
| `skills` | Playbooks métier (F23) — colonne déjà ajoutée par F23 si différente convention. Utiliser `ADD COLUMN IF NOT EXISTS`. |

### Transitions autorisées

```
draft → published  : via POST /api/admin/<entity>/{id}/publish (déclenche trigger)
published → draft  : via POST /api/admin/<entity>/{id}/unpublish (post-MVP)
draft → draft      : édition libre
published → published : édition crée nouvelle version (F04 VersioningMixin)
```

## 2. Table `password_reset_tokens` (NOUVELLE)

### Schéma

```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_password_reset_tokens_user_expires ON password_reset_tokens (user_id, expires_at);
CREATE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);
```

### Sécurité

- `token_hash` : sha256 du token URL-safe (jamais stocké en clair)
- `expires_at` : `now() + INTERVAL '1 hour'`
- `used_at` : NULL = token actif, set = token utilisé (impossible de réutiliser)
- ON DELETE CASCADE : si user supprimé, ses tokens aussi

### Validation à l'utilisation

```python
async def validate_reset_token(plain_token: str, db) -> User | None:
    token_hash = hash_token(plain_token)
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .where(PasswordResetToken.used_at == None)
        .where(PasswordResetToken.expires_at > datetime.now(timezone.utc))
    )
    return result.scalar_one_or_none()
```

## 3. Fonction PL/pgSQL `before_publish_check_sources_verified()`

### Logique

```sql
CREATE OR REPLACE FUNCTION before_publish_check_sources_verified()
RETURNS TRIGGER AS $$
DECLARE
    offending_source_id UUID;
    offending_status VARCHAR;
    entity_type VARCHAR;
BEGIN
    -- Only fire on draft -> published transition
    IF NOT (OLD.publication_status = 'draft' AND NEW.publication_status = 'published') THEN
        RETURN NEW;
    END IF;

    entity_type := TG_TABLE_NAME;

    -- Iterate sources via entity_sources (table polymorphe)
    SELECT s.id, s.verification_status
        INTO offending_source_id, offending_status
    FROM sources s
    JOIN entity_sources es ON es.source_id = s.id
    WHERE es.entity_type = entity_type
      AND es.entity_id = NEW.id
      AND s.verification_status != 'verified'
    LIMIT 1;

    IF offending_source_id IS NOT NULL THEN
        RAISE EXCEPTION
            'cannot publish: source % has verification_status=%',
            offending_source_id, offending_status
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Triggers (10 par table)

```sql
DROP TRIGGER IF EXISTS trg_<table>_before_publish ON <table>;
CREATE TRIGGER trg_<table>_before_publish
    BEFORE UPDATE ON <table>
    FOR EACH ROW
    EXECUTE FUNCTION before_publish_check_sources_verified();
```

### Cas limites

- **Première fois publish** : OLD.publication_status='draft', NEW.publication_status='published' → fire trigger.
- **Édition normale** : draft → draft → no fire.
- **Re-publish déjà published** : published → published → no fire (pas de transition).
- **Aucune source liée** : la requête ne retourne rien, autorise le UPDATE. Note : business rule = chaque entité catalogue doit avoir au moins 1 source verified avant publish (validation applicative supplémentaire dans le service `catalog_publish_helper`).

## 4. Fonction PL/pgSQL `before_verify_source_check_different_admin()`

### Logique

```sql
CREATE OR REPLACE FUNCTION before_verify_source_check_different_admin()
RETURNS TRIGGER AS $$
BEGIN
    -- Only fire on pending -> verified transition
    IF NOT (OLD.verification_status = 'pending' AND NEW.verification_status = 'verified') THEN
        RETURN NEW;
    END IF;

    IF NEW.verified_by_user_id IS NULL THEN
        RAISE EXCEPTION
            '4-eyes principle: verified_by_user_id required'
            USING ERRCODE = 'P0001';
    END IF;

    IF NEW.verified_by_user_id = OLD.captured_by_user_id THEN
        RAISE EXCEPTION
            '4-eyes principle violated: verifier (%) must differ from creator (%)',
            NEW.verified_by_user_id, OLD.captured_by_user_id
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Trigger (1 sur sources)

```sql
DROP TRIGGER IF EXISTS trg_sources_before_verify ON sources;
CREATE TRIGGER trg_sources_before_verify
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION before_verify_source_check_different_admin();
```

### Cas limites

- **Verify par auteur** : verified_by = captured_by → exception.
- **Verify par autre admin** : verified_by ≠ captured_by → autorisé.
- **Pending → outdated** : transition ≠ verify → no fire.
- **Verified → outdated** : transition après verify → no fire (pas la transition pending→verified).

## 5. Schémas Pydantic (output API)

### `MetricsOverview`

```python
class SourcesMetrics(BaseModel):
    total: int
    pending: int
    verified: int
    outdated: int
    trend_30d: list[int]  # 30 ints, count par jour des transitions

class AccountsMetrics(BaseModel):
    total_active: int
    total_inactive: int
    new_30d: int

class ApplicationsMetrics(BaseModel):
    total: int = 0  # post-MVP placeholder
    by_status: dict[str, int] = Field(default_factory=dict)
    status: Literal["mvp", "post_mvp"] = "post_mvp"

class AttestationsMetrics(BaseModel):
    total_emitted: int
    total_revoked: int
    total_active: int

class LLMCostsMetrics(BaseModel):
    total_tokens_in: int = 0  # post-MVP placeholder
    total_tokens_out: int = 0
    total_cost_usd_estimated_30d: float = 0.0
    status: Literal["mvp", "post_mvp"] = "post_mvp"

class MetricsOverview(BaseModel):
    sources: SourcesMetrics
    accounts: AccountsMetrics
    applications: ApplicationsMetrics
    attestations: AttestationsMetrics
    llm_costs: LLMCostsMetrics
    generated_at: datetime
```

### `DependentsReport`

```python
class DependentEntity(BaseModel):
    id: UUID
    name: str
    publication_status: str
    type: str  # "indicator", "criterion", "formula", etc.

class DependentsReport(BaseModel):
    source_id: UUID
    indicators: list[DependentEntity]
    criteria: list[DependentEntity]
    formulas: list[DependentEntity]
    emission_factors: list[DependentEntity]
    simulation_factors: list[DependentEntity]
    skills: list[DependentEntity]
    total: int  # somme de toutes les listes
```

### `BlockingSourcesError` (réponse 400 publish gating)

```python
class BlockingSource(BaseModel):
    id: UUID
    title: str
    verification_status: Literal["pending", "outdated"]

class PublishBlockedError(BaseModel):
    error: Literal["publish_blocked"] = "publish_blocked"
    message: str
    blocking_sources: list[BlockingSource]
```

### `FourEyesViolationError` (réponse 400 trigger 4-yeux)

```python
class FourEyesViolationError(BaseModel):
    error: Literal["4_eyes_violation"] = "4_eyes_violation"
    message: str = "Cannot verify your own source. Another admin must verify it."
```

## 6. Audit Log Entries (subset F03)

### Actions admin

```python
class AdminAuditAction(str, Enum):
    # CRUD entités catalogue
    FUND_CREATED = "fund_created"
    FUND_UPDATED = "fund_updated"
    FUND_PUBLISHED = "fund_published"
    FUND_UNPUBLISHED = "fund_unpublished"
    FUND_DELETED = "fund_deleted"
    INTERMEDIARY_CREATED = "intermediary_created"
    INTERMEDIARY_UPDATED = "intermediary_updated"
    INTERMEDIARY_PUBLISHED = "intermediary_published"
    INTERMEDIARY_DELETED = "intermediary_deleted"
    OFFER_CREATED = "offer_created"
    OFFER_UPDATED = "offer_updated"
    OFFER_PUBLISHED = "offer_published"
    OFFER_DELETED = "offer_deleted"
    REFERENTIAL_CREATED = "referential_created"
    REFERENTIAL_UPDATED = "referential_updated"
    REFERENTIAL_PUBLISHED = "referential_published"
    REFERENTIAL_DELETED = "referential_deleted"
    INDICATOR_CREATED = "indicator_created"
    INDICATOR_UPDATED = "indicator_updated"
    INDICATOR_PUBLISHED = "indicator_published"
    INDICATOR_DELETED = "indicator_deleted"
    CRITERION_CREATED = "criterion_created"
    CRITERION_UPDATED = "criterion_updated"
    CRITERION_PUBLISHED = "criterion_published"
    CRITERION_DELETED = "criterion_deleted"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    TEMPLATE_PUBLISHED = "template_published"
    TEMPLATE_DELETED = "template_deleted"
    EMISSION_FACTOR_CREATED = "emission_factor_created"
    EMISSION_FACTOR_UPDATED = "emission_factor_updated"
    EMISSION_FACTOR_PUBLISHED = "emission_factor_published"
    EMISSION_FACTOR_DELETED = "emission_factor_deleted"
    SIMULATION_FACTOR_CREATED = "simulation_factor_created"
    SIMULATION_FACTOR_UPDATED = "simulation_factor_updated"
    SIMULATION_FACTOR_PUBLISHED = "simulation_factor_published"
    SIMULATION_FACTOR_DELETED = "simulation_factor_deleted"

    # Sources workflow
    SOURCE_CREATED = "source_created"
    SOURCE_UPDATED = "source_modified"
    SOURCE_VERIFIED = "source_verified"
    SOURCE_OUTDATED = "source_outdated"
    SOURCE_DELETED = "source_deleted"

    # Support PME
    VIEW_ADMIN = "view_admin"
    PASSWORD_RESET_INITIATED_BY_ADMIN = "password_reset_initiated_by_admin"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    USER_TOGGLED_ACTIVE = "user_toggled_active"
    ATTESTATION_REVOKED = "attestation_revoked"

    # Sécurité
    UNAUTHORIZED_ADMIN_ACCESS_ATTEMPT = "unauthorized_admin_access_attempt"
```

### Metadata structurées par action

```python
# fund_published
{"version": "1.0.0", "sources_count": 3}

# user_toggled_active
{"previous": True, "new": False, "reason": "fraud detected"}

# attestation_revoked
{"reason": "data error", "attestation_type": "esg_score"}

# view_admin
{"sections_loaded": ["profile", "projects", "scores", "attestations"]}

# password_reset_initiated_by_admin
{"target_user_id": "uuid", "expires_at": "2026-05-07T15:00:00Z"}
```

## 7. État LangGraph (impact)

F09 ne modifie pas directement l'état LangGraph (pas de nouveau champ ConversationState). Le workflow draft/published affecte le RAG et les tools (filtrage automatique sur `publication_status='published'` dans les services consommés).

## 8. Relations entre entités (résumé)

```
users
  ├── (created_by) →  funds, intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills, sources
  ├── (verified_by) → sources (4-yeux)
  ├── (target) ← password_reset_tokens
  └── (revoked_by) → attestations

sources
  ├── (captured_by) → users
  ├── (verified_by) → users
  └── (referenced_by) ← entity_sources → funds, intermediaries, indicators, criteria, etc.

funds, intermediaries, etc.
  └── publication_status = draft | published

audit_log (F03)
  └── action ∈ AdminAuditAction (subset)
```

## 9. Indexes de performance

### Existants (F01-F08)

- `users.is_active`
- `users.role`
- `sources.verification_status`
- `attestations.revoked_at`

### Ajoutés par F09

- `ix_<table>_publication_status` (sur 10 tables) — pour filtrage rapide
- `ix_password_reset_tokens_user_expires` (composite)
- `ix_password_reset_tokens_token_hash` (lookup unique)

### Recommandés (post-MVP)

- Index trigram (`pg_trgm`) sur `funds.name`, `intermediaries.name`, `sources.title` pour recherche full-text rapide
- Materialized view `metrics_overview_cache` rafraîchie toutes les 5 min (post-MVP)

## 10. Volumétrie attendue (MVP)

| Table | Volume MVP | Volume Post-MVP (1 an) |
|-------|------------|-------------------------|
| funds | 50 | 500 |
| intermediaries | 30 | 300 |
| offers | 100 | 2000 (50 × 30 = 1500 max) |
| sources | 200 | 2000 |
| indicators | 100 | 500 |
| criteria | 200 | 1000 |
| password_reset_tokens | ~50/mois | ~500/mois |
| audit_log entries (F03) | ~10k/mois | ~100k/mois |

Avec ces volumes, les performances cibles (P95 < 500ms metrics overview, < 200ms list catalogue) sont atteignables sans cache Redis.
