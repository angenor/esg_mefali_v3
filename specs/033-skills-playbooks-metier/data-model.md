# Phase 1 — Data Model: F23 Skills (Playbooks Métier)

## Entité 1 — Table `skills`

**Nouvelle table** créée par migration `033_create_skills.py` (down_revision=`032_add_validation_error_tool_call_logs`).

### Schéma SQLAlchemy

```python
# backend/app/models/skill.py
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.versioning_mixin import VersioningMixin


class SkillDomain(str, Enum):
    DIAGNOSTIC_ESG = "diagnostic_esg"
    SCORING_REFERENTIEL = "scoring_referentiel"
    CARBON_CALC = "carbon_calc"
    DOSSIER = "dossier"
    INTERMEDIAIRE = "intermediaire"
    ATTESTATION = "attestation"
    CREDIT_SCORE = "credit_score"


class SkillStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


JSONType = JSONB().with_variant(JSON(), "sqlite")


class Skill(UUIDMixin, TimestampMixin, VersioningMixin, Base):
    """Skill : bundle métier (prompt expert + procedure + tools + sources + golden_examples).

    Workflow :
    - draft : skill en cours de calibration, golden_examples possiblement < 5
    - published : skill validée par eval gating (taux ≥ 90 %), exposable au LLM
    - Versioning F04 : édition d'une skill `published` → nouvelle version `draft`
                       (semver patch+1) → eval gating → publication, ancienne version
                       reçoit `valid_to=today()` + `superseded_by=new_id`
    """

    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_expert: Mapped[str] = mapped_column(Text, nullable=False)
    procedure: Mapped[str] = mapped_column(Text, nullable=False)
    tool_whitelist: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    sources: Mapped[list[str]] = mapped_column(JSONType, nullable=False)  # liste UUIDs vers sources.id
    activation_rules: Mapped[dict] = mapped_column(JSONType, nullable=False)
    golden_examples: Mapped[list[dict]] = mapped_column(JSONType, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SkillStatus.DRAFT.value, server_default=SkillStatus.DRAFT.value,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "domain IN ('diagnostic_esg', 'scoring_referentiel', 'carbon_calc', "
            "'dossier', 'intermediaire', 'attestation', 'credit_score')",
            name="skills_domain_chk",
        ),
        CheckConstraint(
            "status IN ('draft', 'published')",
            name="skills_status_chk",
        ),
        CheckConstraint(
            "verified_by IS NULL OR verified_by != created_by",
            name="skills_four_eyes_chk",
        ),
        Index("ix_skills_domain_status_validto", "domain", "status", "valid_to"),
        Index("ix_skills_status", "status"),
        # Index GIN sur activation_rules — créé par migration en SQL natif (PG only)
    )
```

### Colonnes (récapitulatif)

| Colonne | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | uuid4 | PK (UUIDMixin) |
| `name` | VARCHAR(100) | NO | — | UNIQUE (ex: `skill_dossier_gcf_via_boad`) |
| `domain` | VARCHAR(50) | NO | — | Enum check (7 valeurs) |
| `version` | VARCHAR(50) | NO | "1.0.0" | semver (VersioningMixin F04) |
| `prompt_expert` | TEXT | NO | — | ≤ 5000 tokens (validator) |
| `procedure` | TEXT | NO | — | ≤ 3000 tokens (validator) |
| `tool_whitelist` | JSONB | NO | — | `["create_fund_application", ...]` |
| `sources` | JSONB | NO | — | `["uuid1", "uuid2"]` (FK Source) |
| `activation_rules` | JSONB | NO | — | Voir Entité 2 |
| `golden_examples` | JSONB | NO | — | Liste 5-15 cas, voir Entité 3 |
| `status` | VARCHAR(20) | NO | "draft" | Enum check (draft/published) |
| `created_by` | UUID | NO | — | FK users.id ON DELETE RESTRICT |
| `verified_by` | UUID | YES | NULL | FK users.id, 4-yeux check |
| `valid_from` | DATE | NO | today() | VersioningMixin F04 |
| `valid_to` | DATE | YES | NULL | VersioningMixin F04 |
| `superseded_by` | UUID | YES | NULL | self-FK skills.id ON DELETE SET NULL |
| `created_at` | TIMESTAMP TZ | NO | now() | TimestampMixin |
| `updated_at` | TIMESTAMP TZ | NO | now() | TimestampMixin (onupdate) |

### Indexes

| Nom | Type | Colonnes | Justification |
|---|---|---|---|
| `skills_pkey` | PK | id | — |
| `skills_name_key` | UNIQUE | name | Empêche doublons |
| `ix_skills_domain_status_validto` | BTREE | (domain, status, valid_to) | Filtre liste admin par domain + status |
| `ix_skills_status` | BTREE | status | Filtre rapide `WHERE status='published'` (loader) |
| `ix_skills_activation_rules_gin` | GIN | activation_rules | Matching rapide loader (PG only) |

### Contraintes

| Nom | Type | Description |
|---|---|---|
| `skills_domain_chk` | CHECK | Domain dans liste enum (7 valeurs) |
| `skills_status_chk` | CHECK | Status dans (draft, published) |
| `skills_four_eyes_chk` | CHECK | `verified_by IS NULL OR verified_by != created_by` |

## Entité 2 — `ActivationRules` (jsonb dict)

**Format** :

```typescript
type ActivationRules = {
  page_slugs?: string[];          // ["/esg", "/financing"]
  intent_keywords?: string[];     // ["dossier", "candidature", "GCF"]
  active_module?: string[];       // ["esg_scoring", "application"]
  offer_id?: string | null;       // UUID si lié à offre spécifique
  fund_id?: string | null;        // UUID si lié à fonds spécifique
  intermediary_id?: string | null; // UUID si lié à intermédiaire spécifique
};
```

**Exemple `skill_dossier_gcf_via_boad`** :

```json
{
  "page_slugs": ["/applications"],
  "intent_keywords": ["dossier", "candidature", "GCF", "BOAD"],
  "active_module": ["application"],
  "offer_id": null,
  "fund_id": "550e8400-e29b-41d4-a716-446655440000",
  "intermediary_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Score de spécificité** : voir `research.md` R1.

## Entité 3 — `GoldenExample` (jsonb list)

**Format** (aligné F22) :

```typescript
type GoldenExample = {
  id: string;                    // ex: "gcf-boad-init-01"
  category: SkillDomain;
  context: {
    current_page: string | null;
    active_module: string | null;
    user_profile?: object;
    offer_id?: string | null;
    fund_id?: string | null;
    intermediary_id?: string | null;
  };
  user_message: string;
  expected: {
    tool_called: string | string[];   // une whitelist accepté
    payload_contains?: object;        // subset attendu dans tool_args
    fallback_acceptable?: boolean;
  };
  tags?: string[];
};
```

**Exemple** :

```json
{
  "id": "gcf-boad-init-01",
  "category": "dossier",
  "context": {
    "current_page": "/applications",
    "active_module": "application",
    "fund_id": "GCF_UUID",
    "intermediary_id": "BOAD_UUID"
  },
  "user_message": "Je veux préparer mon dossier GCF via BOAD pour mon projet solaire",
  "expected": {
    "tool_called": "create_fund_application",
    "payload_contains": {
      "fund_id": "GCF_UUID",
      "intermediary_id": "BOAD_UUID"
    }
  },
  "tags": ["initialisation", "GCF", "BOAD"]
}
```

**Contraintes** :

- Minimum 5 exemples requis pour publier (validator).
- Maximum 15 exemples par skill (raison performance eval gating ≤ 60s P95 avec parallélisation).

## Entité 4 — `SkillEvalReport` (Pydantic output)

**Format** :

```python
class FailedCase(BaseModel):
    case_id: str
    expected_tool: str | list[str]
    actual_tool: str | None
    payload_diff: dict | None
    latency_ms: int
    error: str | None = None


class SkillEvalReport(BaseModel):
    skill_id: UUID
    run_id: UUID
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    total_cases: int
    passed: int
    failed: int
    success_rate: float
    threshold: float = 0.9
    gate_passed: bool
    failed_cases: list[FailedCase]
```

**Exemple réponse `POST /api/admin/skills/{id}/publish`** (gate failed) :

```json
{
  "skill_id": "uuid-skill",
  "run_id": "uuid-run",
  "started_at": "2026-05-07T10:00:00Z",
  "completed_at": "2026-05-07T10:00:42Z",
  "duration_seconds": 42.3,
  "total_cases": 5,
  "passed": 2,
  "failed": 3,
  "success_rate": 0.4,
  "threshold": 0.9,
  "gate_passed": false,
  "failed_cases": [
    {
      "case_id": "gcf-boad-init-01",
      "expected_tool": "create_fund_application",
      "actual_tool": "search_funds",
      "payload_diff": {"missing": ["fund_id"]},
      "latency_ms": 5800
    }
  ]
}
```

Statut HTTP : 422 (validation failed). Skill reste `draft`.

## Entité 5 — Extension `ConversationState["active_skills"]`

**Modification** `app/graph/state.py` :

```python
class ConversationState(TypedDict):
    # ... champs existants (messages, active_module, etc.) ...
    active_skills: list[dict] | None  # [{id: str, name: str, version: str}]
```

**Lifecycle** :

| Étape | Valeur |
|---|---|
| Début tour | `[{"id": "...", "name": "skill_dossier_gcf_via_boad", "version": "1.0.0"}]` |
| Pendant tool calls | inchangé |
| Fin tour (checkpoint) | sérialisé en BDD via LangGraph checkpointer |
| Reprise (next user message) | restauré ; rappel `load_skills_for_context()` peut renvoyer une nouvelle version |

## Entité 6 — Endpoint réponses (admin skills)

### `GET /api/admin/skills`

**Query params** :
- `domain: str | None` — filtre par domaine
- `status: str | None` — filtre `draft|published`
- `q: str | None` — recherche fuzzy sur name
- `page: int = 1`, `limit: int = 20`

**Réponse** :

```python
class SkillListItem(BaseModel):
    id: UUID
    name: str
    domain: str
    version: str
    status: str
    valid_from: date
    valid_to: date | None
    created_at: datetime
    updated_at: datetime


class SkillListResponse(BaseModel):
    items: list[SkillListItem]
    total: int
    page: int
    limit: int
```

### `POST /api/admin/skills`

**Body** :

```python
class SkillCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, pattern=r"^skill_[a-z][a-z0-9_]*$")
    domain: SkillDomain
    prompt_expert: str = Field(..., min_length=50)
    procedure: str = Field(..., min_length=50)
    tool_whitelist: list[str]
    sources: list[UUID]
    activation_rules: ActivationRules
    golden_examples: list[GoldenExample]
```

**Réponse** : `201 Created` avec `SkillRead` (Skill complet sérialisé).

**Erreurs** :
- `422` : validation Pydantic, anti-injection (`detected_patterns`), token limit, source non verified, tool name inconnu.

### `PATCH /api/admin/skills/{id}`

**Body** : `SkillUpdate` (tous champs optionnels sauf id implicite).

**Comportement** :
- Si skill `status=draft` : update in-place.
- Si skill `status=published` : crée nouvelle version `draft` (semver patch+1), retourne le nouvel `id`.

**Réponse** : `200 OK` avec `SkillRead`.

### `POST /api/admin/skills/{id}/publish`

**Body** : `{}` (aucun param).

**Comportement** :
1. Charge skill par id.
2. Si `status != draft` → `400 Bad Request` (`already_published`).
3. Si `len(golden_examples) < 5` → `422` (`insufficient_golden_examples`).
4. Exécute `run_skill_eval(skill, db)` (parallèle, max 5 concurrent, timeout 60s).
5. Si `gate_passed=False` → `422` avec `SkillEvalReport`. Skill reste `draft`.
6. Si `gate_passed=True` → mise à jour : `status=published`. Si `superseded_by` est référencé par une ancienne version, ancienne reçoit `valid_to=today()`. Audit log.

**Réponse succès** : `200 OK` avec `SkillRead` (status published) + `eval_report`.

### `POST /api/admin/skills/{id}/test`

**Body** : `{}`.

**Comportement** : exécute `run_skill_eval()` mais ne change PAS le status. Retourne `SkillEvalReport`.

### `POST /api/admin/skills/{id}/unpublish`

**Body** : `{}`.

**Comportement** : `status=published → draft`. Audit log.

### `DELETE /api/admin/skills/{id}`

**Comportement** : soft delete (`valid_to=today()`) UNIQUEMENT si `status=draft`. Sinon `400`.

## Relations

```text
[skills]
  ├── created_by → [users]
  ├── verified_by → [users]   (4-yeux : != created_by)
  ├── superseded_by → [skills]  (self-FK)
  └── sources (jsonb list of UUIDs)
       └── chaque UUID → [sources]  (vérifié au save : verification_status='verified')

[skills.golden_examples] (jsonb list)
  └── chaque example.expected.tool_called → tool name
       └── vérifié au save : ∈ ALL_TOOL_NAMES (collecté au module load)

[skills.tool_whitelist] (jsonb list of strings)
  └── chaque tool name → vérifié au save : ∈ ALL_TOOL_NAMES

[ConversationState]
  └── active_skills : list[{id, name, version}]  (snapshot au début du tour)

[audit_log] (F03)
  └── entries : skill_created, skill_updated, skill_published, skill_unpublished,
                skill_deleted, injection_attempt_blocked
```

## Lifecycle complet d'une Skill

```text
[Admin] CRÉATION
  POST /api/admin/skills
  → validator (anti-injection, tokens, sources verified, tool names)
  → audit log skill_created
  → réponse 201 (status=draft, version=1.0.0)

[Admin] CALIBRATION GOLDEN_EXAMPLES
  PATCH /api/admin/skills/{id} (golden_examples=[...5-15 cas])
  → audit log skill_updated

[Admin] TEST À BLANC
  POST /api/admin/skills/{id}/test
  → eval runner exécute golden_examples
  → retourne SkillEvalReport
  → pas de mutation status

[Admin] PUBLICATION
  POST /api/admin/skills/{id}/publish
  → eval runner exécute golden_examples
  → si gate_passed=True : status=published, audit log skill_published
  → si gate_passed=False : 422 avec rapport, status reste draft

[Runtime LLM] CHARGEMENT
  → load_skills_for_context(...) au début de chaque tour
  → SELECT skills WHERE status='published' AND (valid_to IS NULL OR valid_to > today)
  → score de spécificité, top 2
  → fuse_prompt(base, skills)
  → select_tools_with_skills(base_tools, skills)
  → bind_tools(intersection)
  → state["active_skills"] = snapshot

[Admin] ÉDITION SKILL PUBLISHED
  PATCH /api/admin/skills/{id} (modifications)
  → service détecte status=published
  → crée nouvelle ligne (id=uuid4(), version=1.0.1, status=draft)
  → ancienne ligne intacte (reste published)
  → réponse 200 avec nouvel id

[Admin] PUBLICATION NOUVELLE VERSION
  POST /api/admin/skills/{new_id}/publish
  → eval runner
  → si gate_passed : 
      - new : status=published
      - old : valid_to=today(), superseded_by=new_id
  → audit log skill_published (new) + skill_superseded (old)

[Conversations en cours] PROTECTION
  → state["active_skills"] gardé tel quel pendant le tour
  → au prochain tour utilisateur : nouveau load_skills_for_context()
  → renvoie la nouvelle version published (l'ancienne a valid_to défini)
```
