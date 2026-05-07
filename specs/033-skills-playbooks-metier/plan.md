# Implementation Plan: F23 — Skills (Playbooks Métier)

**Branch**: `feat/F23-skills-playbooks-metier` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/033-skills-playbooks-metier/spec.md`

## Summary

F23 introduit le concept de **Skill** : bundle métier réutilisable qui combine un prompt expert focalisé, une procédure pas-à-pas, un sous-ensemble de tools autorisés, des sources pré-résolues et des golden examples. Les Skills sont chargées dynamiquement par un loader contextuel dans 7 nœuds LangGraph, fusionnées dans le system prompt, et leur tool whitelist est intersectée avec les tools de la page.

3 capacités principales :

1. **Modèle BDD `skills`** : table complète avec versioning F04, domaine enum 7 valeurs, prompt_expert ≤ 5000 tokens, golden_examples (5-15 cas par skill), status draft/published, audit log F03.
2. **Loader + Fusion + Intersection tools** : `app/graph/skill_loader.py`, `app/graph/prompt_fusion.py`, helper intersection. Refactor 7 nœuds (`chat_node`, `esg_scoring_node`, `carbon_node`, `financing_node`, `application_node`, `credit_node`, `action_plan_node`).
3. **CRUD admin + Eval gating + Anti-injection + Seed 3 skills critiques** : router admin protégé, gating publication via runner F22 (seuil 90 %), détecteur d'injection, seed `skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad`.

Inclut aussi : schémas Pydantic, validator (tools whitelist + sources verified + tokens limit + anti-injection), frontend admin (8 onglets), documentation `docs/skills-playbooks.md`.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** : FastAPI, LangGraph (>=0.2.0), LangChain (>=0.3.0), langchain-openai, SQLAlchemy async, Pydantic v2, Alembic, tiktoken (comptage tokens) ; côté frontend Nuxt 4, Vue Composition API, Pinia, TailwindCSS
**Storage** : PostgreSQL 16 + pgvector — nouvelle table `skills` avec colonnes `JSONB` (5 colonnes JSONB : tool_whitelist, sources, activation_rules, golden_examples, et ad-hoc validation), index GIN sur `activation_rules`
**Testing** : pytest + pytest-asyncio ; markers `unit`, `integration`, `eval` (réutilise F22)
**Target Platform** : Linux server (uvicorn) / GitHub Actions CI (Ubuntu 22.04)
**Project Type** : web-service (mono-repo backend/ + frontend/)
**Performance Goals** :
- Skill loader (`load_skills_for_context`) : < 50ms P95 (1 requête SQL avec index GIN)
- Fusion prompt : < 100ms P95 (incluant chargement sources, ≤ 2 skills)
- Eval gating à la publication : < 60s P95 pour 10 golden_examples (~6s/cas LLM)
- Endpoint `POST /api/admin/skills/{id}/publish` : < 90s P95 (gating + commit)
**Constraints** :
- Budget tokens system prompt : skills + base ≤ 12 000 tokens (sinon charge 1 skill au lieu de 2)
- Aucune régression sur 935+ tests backend existants
- Zero-downtime : table `skills` nouvelle, déploiement progressif (DB → code → seed)
- LLM ne peut JAMAIS modifier les Skills (test conformity bloquant)
**Scale/Scope** :
- 1 nouvelle table BDD (`skills`) avec 18 colonnes + 4 indexes
- 1 nouvelle migration Alembic 033
- 3 skills MVP seedées (croissance prévue à 11 skills)
- Refactor 7 nœuds LangGraph (skill loader avant `bind_tools`)
- 8 endpoints REST admin
- 3 pages frontend admin (index, new, [id]) + 7 composants
- ~12 nouveaux fichiers backend, ~8 nouveaux fichiers frontend, ~10 fichiers modifiés

## Constitution Check

Pas de fichier constitution dans ce projet (vérification : `/Users/mac/Documents/projets/2025/esg_mefali_v3/.specify/memory/` n'a pas de constitution active). Gates standards appliqués :

- **Test coverage** : ≥ 80 % minimum (rule globale) — couvert par tests unit/integration/E2E + LLM eval
- **Sécurité** : router admin protégé par `Depends(require_admin_role)` (F02), anti-injection au save (F23 validator), audit log F03 sur toute mutation
- **Performance** : index GIN sur `activation_rules`, requête loader < 50ms P95, pagination liste Skills
- **Immutabilité** : édition skill `published` crée nouvelle version (pas de mutation in-place), state LangGraph snapshot immutable
- **Pas de mutation catalogue par LLM** : aucun tool `create_skill|update_skill|...` exposé, test conformity bloquant
- **Versioning F04** : table `skills` étend `VersioningMixin`, gestion semver patch incrément automatique

## Project Structure

### Documentation (this feature)

```text
specs/033-skills-playbooks-metier/
├── spec.md                  # Spec finalisée avec clarifications
├── plan.md                  # Ce fichier
├── research.md              # Phase 0 — recherche skills patterns, tiktoken, format golden examples
├── data-model.md            # Phase 1 — schéma table skills + relations + ActivationRules + GoldenExample
├── quickstart.md            # Phase 1 — créer une skill, la publier, la tester, la versionner
├── contracts/
│   ├── skill_schema.json                # JSON Schema d'une Skill (BDD + JSONB)
│   ├── activation_rules_schema.json     # JSON Schema d'ActivationRules (jsonb)
│   ├── golden_example_schema.json       # JSON Schema d'un GoldenExample (jsonb, aligné F22)
│   ├── skill_eval_report_schema.json    # JSON Schema du rapport eval gating
│   └── admin_skills_endpoints.md        # Spec REST des 8 endpoints admin
├── checklists/
│   └── quality.md           # Checklist qualité spec
└── tasks.md                 # Phase 2 — output /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   └── prompt_injection_detector.py            # NOUVEAU — patterns + detect_injection_patterns()
│   ├── prompts/
│   │   └── system.py                               # CONSERVÉ (F22 base, pas modifié)
│   ├── graph/
│   │   ├── skill_loader.py                         # NOUVEAU — load_skills_for_context()
│   │   ├── prompt_fusion.py                        # NOUVEAU — fuse_prompt() + select_tools_with_skills()
│   │   ├── nodes.py                                # MODIFIÉ — refactor 7 nœuds (chat, esg_scoring, carbon, financing, application, credit, action_plan)
│   │   └── state.py                                # MODIFIÉ — ajout `active_skills: list[dict] | None`
│   ├── modules/
│   │   ├── skills/                                 # NOUVEAU module métier
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py                          # SkillCreate, SkillUpdate, SkillRead, GoldenExample, ActivationRules, SkillEvalReport
│   │   │   ├── service.py                          # CRUD + query_skills_matching + publish_skill
│   │   │   ├── validator.py                        # tool_whitelist + sources verified + token limit + anti-injection
│   │   │   ├── eval_runner.py                     # run_skill_eval() — réutilise F22 test_eval_runner
│   │   │   └── seed.py                             # Seed 3 skills MVP (idempotent)
│   │   └── admin/
│   │       └── skills_router.py                    # NOUVEAU — 8 endpoints REST admin protégés
│   └── models/
│       └── skill.py                                # NOUVEAU — Skill SQLAlchemy model (UUIDMixin + TimestampMixin + VersioningMixin)
├── alembic/
│   └── versions/
│       └── 033_create_skills.py                    # NOUVEAU — migration table skills + indexes + CheckConstraints
└── tests/
    ├── graph/
    │   ├── tools/
    │   │   └── test_no_skill_mutation_tool.py      # NOUVEAU — conformity : aucun tool LLM ne mute Skills
    │   ├── test_skill_loader.py                    # NOUVEAU — unit tests loader
    │   ├── test_prompt_fusion.py                   # NOUVEAU — unit tests fusion + intersection
    │   ├── test_chat_node_with_skill.py            # NOUVEAU — integration node avec skill chargée
    │   ├── test_application_node_dossier_gcf.py    # NOUVEAU — E2E dossier GCF/BOAD vocabulaire métier
    │   └── test_esg_scoring_node_with_skill.py     # NOUVEAU — integration esg avec skill_esg_diagnostic
    ├── unit/
    │   ├── core/
    │   │   └── test_prompt_injection_detector.py   # NOUVEAU — patterns détectés vs benins
    │   ├── models/
    │   │   └── test_skill_model.py                 # NOUVEAU — model + constraints + 4-yeux
    │   └── modules/
    │       └── skills/
    │           ├── test_skill_validator.py         # NOUVEAU — validator unit
    │           ├── test_skill_service.py           # NOUVEAU — CRUD + query + versioning
    │           ├── test_skill_eval_runner.py       # NOUVEAU — eval runner gating (mock LLM)
    │           └── test_skill_seed.py              # NOUVEAU — idempotence seed
    ├── integration/
    │   └── admin/
    │       ├── test_admin_skills_router.py         # NOUVEAU — 8 endpoints CRUD + auth
    │       └── test_admin_skills_publish_e2e.py    # NOUVEAU — eval gating bloquant si failing
    └── llm_eval/
        └── (réutilise F22 test_eval_runner.py comme librairie)

frontend/
├── app/
│   ├── pages/
│   │   └── admin/
│   │       └── skills/
│   │           ├── index.vue                       # NOUVEAU — liste skills, filtres
│   │           ├── new.vue                         # NOUVEAU — formulaire création (8 onglets)
│   │           └── [id].vue                        # NOUVEAU — édition + Publier + Tester
│   ├── components/
│   │   └── admin/
│   │       └── skills/
│   │           ├── SkillList.vue                   # NOUVEAU — table liste avec filtres
│   │           ├── SkillForm.vue                   # NOUVEAU — formulaire 8 onglets
│   │           ├── ToolWhitelistPicker.vue         # NOUVEAU — multi-select tools depuis catalogue
│   │           ├── SourceMultiPicker.vue           # NOUVEAU — multi-select sources verified
│   │           ├── ActivationRulesEditor.vue       # NOUVEAU — page_slugs + intent + offer/fund/intermediary
│   │           ├── GoldenExamplesEditor.vue        # NOUVEAU — éditeur JSON guidé pour 5-15 cas
│   │           └── SkillEvalRunner.vue             # NOUVEAU — bouton "Tester" + affichage rapport
│   └── composables/
│       └── useAdminSkills.ts                       # NOUVEAU — CRUD + publish + test wrapper API
└── tests/
    └── e2e/
        └── admin/
            └── skills.spec.ts                      # NOUVEAU — Playwright : créer, publier, golden failing

docs/
└── skills-playbooks.md                             # NOUVEAU — process : créer skill, calibrer golden, publier, versionner
```

**Structure Decision** : architecture modulaire conforme aux conventions du projet. F23 est ~80 % backend (loader, fusion, validator, eval runner, CRUD, seed) + ~20 % frontend (3 pages admin + 7 composants). La majorité des modifications portent sur 5 zones :

1. `app/models/skill.py` (nouveau modèle SQLAlchemy)
2. `app/modules/skills/*` (nouveau module métier complet)
3. `app/graph/skill_loader.py` + `prompt_fusion.py` (nouveaux helpers LangGraph)
4. `app/graph/nodes.py` (refactor 7 nœuds — minimal : 3-5 lignes par nœud)
5. `app/modules/admin/skills_router.py` (nouveau router F09)

Plus migration Alembic 033, seed des 3 skills critiques, frontend admin pages + composants, documentation, ~30 nouveaux fichiers de test.

## Phases

### Phase 0 — Research

Sortie : `research.md`. Sujets :

- **Pattern skill loading runtime** : approches comparées (Anthropic skills, OpenAI assistants tools, fonctions plugin LangChain). Choix : matching multi-critères avec score de spécificité (analogue à CSS specificity).
- **Format `golden_examples`** : aligner sur F22 (`tests/llm_eval/golden_set.json`) pour réutiliser le runner. Confirmer que `expected.tool_called` accepte string OR list.
- **Anti-injection patterns** : revue OWASP LLM Top 10 (LLM01:2023 Prompt Injection). Liste de regex pragmatique vs ML-based detector. Choix : regex first, évolutif.
- **Token counting** : `tiktoken cl100k_base` (compatible Claude/GPT-4). Performance : ~1ms par 1000 tokens.
- **JSONB GIN index PostgreSQL** : performance pour matching `activation_rules->page_slugs ? 'esg'`. Compatible avec SQLite (tests) via JSON column avec opérateurs JSON.
- **Versioning semver auto-incrément** : `semver` Python lib. Patch incrément automatique sur édition `published`.
- **Eval gating timeout** : 60s pour 10 cas. Si dépassé, retourne 504 et garde `draft`. Solutions : parallélisation cas (asyncio.gather, max 5 concurrent pour limiter coût).

### Phase 1 — Design

Sortie : `data-model.md` + `contracts/`.

**`data-model.md`** documente :

- Table `skills` complète (18 colonnes + indexes + CheckConstraints)
- Schéma `ActivationRules` (jsonb dict) avec score de spécificité
- Schéma `GoldenExample` (jsonb list, aligné F22)
- Schéma `SkillEvalReport` (Pydantic output)
- Relations : `created_by → users`, `verified_by → users`, `superseded_by → skills.id`, `sources` jsonb stocke des UUIDs vers `sources.id`
- État `active_skills` dans `ConversationState`

**`contracts/`** :

- `skill_schema.json` : JSON Schema strict de Skill (entrée admin)
- `activation_rules_schema.json` : JSON Schema strict (page_slugs/intent_keywords/active_module/offer_id/fund_id/intermediary_id, types, exemples)
- `golden_example_schema.json` : JSON Schema strict (réutilise F22 `golden_case_schema.json` avec ajout `category` énuméré)
- `skill_eval_report_schema.json` : JSON Schema du rapport retourné par `/publish` et `/test`
- `admin_skills_endpoints.md` : OpenAPI-like spec des 8 endpoints (params, body, réponses, codes statut, exemples)

**`quickstart.md`** :

- Comment créer une skill via curl + payload exemple
- Comment ajouter golden_examples calibrés
- Comment publier (eval gating)
- Comment versionner (édition publiée → nouvelle version)
- Comment debugger un skill loader (logs, tracing)

### Phase 2 — Tasks (NOT created by /speckit.plan)

Voir `tasks.md` (généré par `/speckit.tasks`).

## Migration Alembic 033

```python
"""F23 — Create skills table

Revision ID: 033_create_skills
Revises: 032_add_validation_error_tool_call_logs
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "033_create_skills"
down_revision = "032_add_validation_error_tool_call_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # JSONB pour PG, JSON pour SQLite (tests)
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0.0"),
        sa.Column("prompt_expert", sa.Text(), nullable=False),
        sa.Column("procedure", sa.Text(), nullable=False),
        sa.Column("tool_whitelist", json_type, nullable=False),
        sa.Column("sources", json_type, nullable=False),
        sa.Column("activation_rules", json_type, nullable=False),
        sa.Column("golden_examples", json_type, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36),
                  sa.ForeignKey("skills.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, onupdate=sa.func.now()),
        sa.CheckConstraint(
            "domain IN ('diagnostic_esg', 'scoring_referentiel', 'carbon_calc', 'dossier', 'intermediaire', 'attestation', 'credit_score')",
            name="skills_domain_chk",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published')",
            name="skills_status_chk",
        ),
        sa.CheckConstraint(
            "verified_by IS NULL OR verified_by != created_by",
            name="skills_four_eyes_chk",
        ),
    )

    op.create_index("ix_skills_domain_status_validto", "skills", ["domain", "status", "valid_to"])
    op.create_index("ix_skills_status", "skills", ["status"])

    # GIN index sur activation_rules pour matching rapide (PostgreSQL uniquement)
    if is_postgres:
        op.execute("CREATE INDEX ix_skills_activation_rules_gin ON skills USING gin (activation_rules)")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_skills_activation_rules_gin")
    op.drop_index("ix_skills_status", table_name="skills")
    op.drop_index("ix_skills_domain_status_validto", table_name="skills")
    op.drop_table("skills")
```

Note : la table est nouvelle, aucune migration de données. Déploiement : `alembic upgrade head` → seed des 3 skills critiques via `app/modules/skills/seed.py` exécuté par script `scripts/seed_skills.py` ou hook startup dev.

## Endpoints admin (résumé)

| Méthode | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/admin/skills` | Admin | Liste paginée, filtres `domain`, `status`, `q` |
| POST | `/api/admin/skills` | Admin | Création (status=`draft`), validator anti-injection, audit log |
| GET | `/api/admin/skills/{id}` | Admin | Détail avec sources résolues |
| PATCH | `/api/admin/skills/{id}` | Admin | Édition. Si skill `published`, crée nouvelle version `draft` (semver patch+1) |
| POST | `/api/admin/skills/{id}/publish` | Admin | Déclenche eval gating, transitionne `draft → published` si gate_passed |
| POST | `/api/admin/skills/{id}/unpublish` | Admin | Transition `published → draft` (rollback) |
| POST | `/api/admin/skills/{id}/test` | Admin | Exécute golden_examples sans publier (rapport retourné) |
| DELETE | `/api/admin/skills/{id}` | Admin | Soft delete (`valid_to=today()`) uniquement si `draft` |

## Skills MVP seedées

### `skill_esg_diagnostic`

- **Domain** : `diagnostic_esg`
- **Activation** : `page_slugs=["/esg"]`, `active_module=["esg_scoring"]`
- **Tool whitelist** : `["batch_save_esg_criteria", "finalize_esg_assessment", "get_esg_assessment", "ask_yes_no", "ask_qcu", "ask_qcm", "ask_number", "cite_source", "show_kpi_card", "show_comparison_table"]`
- **Sources** : grilles E-S-G UEMOA, BCEAO, Gold Standard
- **Prompt expert** : vocabulaire ESG Afrique francophone, contextualisation secteur informel
- **Golden examples** : 8 cas (saisie critère, finalisation, refus de critère hors-scope, etc.)

### `skill_score_gcf`

- **Domain** : `scoring_referentiel`
- **Activation** : `page_slugs=["/financing"]`, `fund_id=GCF_UUID`
- **Tool whitelist** : `["search_funds", "get_fund_details", "show_match_card", "cite_source", "ask_yes_no", "show_comparison_table"]`
- **Sources** : GCF Investment Framework, GCF Country Programmes
- **Prompt expert** : critères d'éligibilité GCF (impact climat, additionalité, cofinancement), seuils MWh et tCO2e
- **Golden examples** : 6 cas (matching projet GCF, refus si sectoriel hors-scope, montant trop faible)

### `skill_dossier_gcf_via_boad`

- **Domain** : `dossier`
- **Activation** : `page_slugs=["/applications"]`, `active_module=["application"]`, `fund_id=GCF_UUID`, `intermediary_id=BOAD_UUID`
- **Tool whitelist** : `["create_fund_application", "get_fund_details", "get_intermediary_details", "ask_file_upload", "ask_yes_no", "ask_qcu", "cite_source", "show_kpi_card"]`
- **Sources** : GCF Funding Proposal Template, BOAD Procédures Climat
- **Prompt expert** : sections obligatoires GCF, ton institutionnel BOAD, FR/EN, vocabulaire métier ("réplication", "additionalité", "MRV", "trajectoire low-carbon")
- **Golden examples** : 5 cas (initialisation dossier, demande document, finalisation, refus si projet hors-éligibilité)

## CI Configuration

### GitHub Actions (extrait `.github/workflows/ci.yml`)

```yaml
  skill-eval:
    name: Skill Eval Gating Test
    runs-on: ubuntu-22.04
    if: |
      github.event_name == 'pull_request' && (
        contains(toJson(github.event.pull_request.changed_files), 'app/modules/skills/') ||
        contains(toJson(github.event.pull_request.changed_files), 'app/graph/skill_loader.py') ||
        contains(toJson(github.event.pull_request.changed_files), 'app/graph/prompt_fusion.py')
      )
    steps:
      - uses: actions/checkout@v4
      - name: Run skill eval tests
        run: pytest tests/graph/test_skill_loader.py tests/graph/test_prompt_fusion.py tests/integration/admin/test_admin_skills_publish_e2e.py -v
```

Le test E2E `test_admin_skills_publish_e2e.py` mocke le LLM (cassette ou stub) pour ne pas consommer le budget LLM en CI.

## Risks & Mitigations

| Risque | Mitigation |
|---|---|
| Skill mal écrite cause hallucinations LLM | Eval gating obligatoire taux ≥ 90 %, audit log F03 sur édition, revue 4-yeux (`verified_by != created_by`) |
| Conflit entre 2 skills activées (instructions contradictoires) | Max 2 skills + tri par spécificité, documentation guideline, test unitaire pour vérifier l'absence de directives contradictoires |
| Prompt injection via `prompt_expert` | Détecteur anti-injection au save (10 patterns initiaux), refus 422 + audit log entry |
| Explosion budget tokens si plusieurs skills longues | Limit `prompt_expert` ≤ 5000 tokens (test au save), cap total 12 000 tokens (charge 1 skill au lieu de 2) |
| Conversations en cours cassent quand skill éditée | Snapshot version dans `state["active_skills"]`, conserve l'ancienne version pour conversations actives ; switch au prochain tour |
| LLM compromis modifie ses propres skills | Aucun tool LLM exposé pour mutation Skill, test conformity bloquant CI |
| Eval gating timeout (LLM lent) | Timeout 60s + retry 1x ; en cas d'échec, garde skill en `draft` et retourne 504 explicite |
| Migration 033 + déploiement progressif | Table nouvelle, zero-downtime. Code lit `[]` si table vide → fallback gracieux ; déploiement DB → code → seed |
