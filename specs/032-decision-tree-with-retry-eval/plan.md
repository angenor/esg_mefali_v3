# Implementation Plan: F22 — Decision Tree + with_retry effectif + Golden Set 50 cas

**Branch**: `feat/F22-decision-tree-with-retry-eval` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/032-decision-tree-with-retry-eval/spec.md`

## Summary

F22 ajoute trois capacités fortement couplées au backend LLM :

1. **Arbre de décision explicite** dans le system prompt (`app/prompts/system.py`) : règles obligatoires `Question fermée → ask_*`, `Visualisation utile → tool typé`, `Mutation → tool action + confirmation destructive`, `Chiffre → cite_source`. Plus 5 anti-exemples explicites.
2. **`with_retry()` paramétrable et effectif** : ajout d'un paramètre `fallback_message`, application sur 11 tools de mutation critique. Logging étendu de `validation_error: jsonb` dans `tool_call_logs`.
3. **Golden Set 50 cas + test runner LLM eval** : nouveau fichier `backend/tests/llm_eval/golden_set.json` (distinct de F01) + runner `test_eval_runner.py` exécuté en CI conditionnel sur changement prompt/tools.

Inclut aussi : standardisation des docstrings (gabarit 5 sections sur tous les tools), extension du test conformity, migration Alembic 032, endpoint admin `/api/admin/metrics/validation-failures`, documentation `docs/llm-eval-loop.md`.

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend, peu impacté)
**Primary Dependencies** : FastAPI, LangGraph (>=0.2.0), LangChain (>=0.3.0), langchain-openai, SQLAlchemy async, pytest, Alembic, Pydantic v2 ; côté tests `pytest`, `pytest-asyncio`
**Storage** : PostgreSQL 16 + pgvector — extension de `tool_call_logs` (colonne nullable, zero-downtime)
**Testing** : pytest + pytest.mark.unit / .integration / .eval ; pytest-asyncio ; subset matching helper
**Target Platform** : Linux server (uvicorn) / GitHub Actions CI (Ubuntu 22.04)
**Project Type** : web-service (mono-repo backend/ + frontend/, modification quasi-exclusive backend)
**Performance Goals** :
- Endpoint admin `/api/admin/metrics/validation-failures` < 500ms P95 sur 100k logs
- Runner LLM eval : 50 cas en < 10 min (parallélisable, mais pas en phase 1)
- Token budget system prompt < 25 % d'augmentation
**Constraints** :
- Aucune régression sur 935+ tests backend existants
- CI conditionnel pour budget LLM (run uniquement sur changement prompts/tools)
- Coût ~$2/run, ~$50/mois max
**Scale/Scope** :
- 11 tools décorés `@with_retry`
- 39 tools couverts par test conformity (vs 26 actuels)
- 50 cas golden set
- 1 nouvelle migration Alembic
- 1 endpoint admin REST
- ~6 nouveaux fichiers, ~10 fichiers modifiés

## Constitution Check

Pas de fichier constitution dans ce projet (vérification : `/Users/mac/Documents/projets/2025/esg_mefali_v3/.specify/memory/` n'a pas de constitution active). Gates standards appliqués :

- **Test coverage** : 80 % minimum (rule globale) — couvert par les tests étendus
- **Sécurité** : endpoint admin protégé par dépendance FastAPI `require_admin_role` (F02)
- **Performance** : pas de N+1, agrégation SQL avec index sur `(created_at, status)` déjà présents
- **Immutabilité** : décorateur `with_retry` ne mute pas les arguments du tool, retourne nouvelles structures
- **Pas de mutation catalogue** : règle décrite dans `DECISION_TREE` (renforce contraintes existantes)

## Project Structure

### Documentation (this feature)

```text
specs/032-decision-tree-with-retry-eval/
├── spec.md                  # Spec finalisée avec clarifications
├── plan.md                  # Ce fichier
├── research.md              # Phase 0 — recherche tools existants, pattern with_retry
├── data-model.md            # Phase 1 — schémas golden_case, eval_report, tool_call_logs.validation_error
├── quickstart.md            # Phase 1 — comment lancer le runner, ajouter un cas, interpréter rapport
├── contracts/
│   ├── golden_case_schema.json     # JSON Schema des cas golden
│   ├── eval_report_schema.json     # JSON Schema du rapport
│   └── admin_metrics_endpoint.md   # Spec REST endpoint admin
└── tasks.md                 # Phase 2 — output /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── prompts/
│   │   └── system.py                              # MODIFIÉ — ajout DECISION_TREE + ANTI_PATTERNS
│   ├── graph/
│   │   └── tools/
│   │       ├── common.py                          # MODIFIÉ — with_retry étendu (fallback_message)
│   │       ├── profiling_tools.py                 # MODIFIÉ — @with_retry sur update_company_profile
│   │       ├── esg_tools.py                       # MODIFIÉ — @with_retry sur batch_save_esg_criteria, finalize_esg_assessment
│   │       ├── carbon_tools.py                    # MODIFIÉ — docstrings 5 sections + @with_retry sur finalize_carbon_assessment
│   │       ├── application_tools.py               # MODIFIÉ — @with_retry sur create_fund_application
│   │       ├── credit_tools.py                    # MODIFIÉ — docstrings 5 sections + @with_retry sur generate_credit_score, generate_credit_certificate
│   │       ├── action_plan_tools.py               # MODIFIÉ — docstrings 5 sections + @with_retry sur generate_action_plan, update_action_item
│   │       ├── financing_tools.py                 # MODIFIÉ — docstrings 5 sections (7 tools)
│   │       ├── chat_tools.py                      # MODIFIÉ — docstrings 5 sections (4 tools)
│   │       ├── document_tools.py                  # MODIFIÉ — docstrings 5 sections (3 tools)
│   │       ├── guided_tour_tools.py               # MODIFIÉ — docstring 5 sections (1 tool)
│   │       └── project_tools.py                   # MODIFIÉ — @with_retry sur update_project, delete_project (F06 déjà mergé)
│   ├── modules/
│   │   └── admin_metrics/                         # NOUVEAU
│   │       ├── __init__.py
│   │       ├── router.py                          # NOUVEAU — endpoint /api/admin/metrics/validation-failures
│   │       └── service.py                         # NOUVEAU — agrégation SQL
│   └── models/
│       └── tool_call_log.py                       # MODIFIÉ — ajout column validation_error: JSONB nullable
├── alembic/
│   └── versions/
│       └── 032_add_validation_error_tool_call_logs.py   # NOUVEAU — migration
└── tests/
    ├── graph/
    │   └── tools/
    │       └── test_tools_meta_conformity.py            # MODIFIÉ — extension scope tools
    ├── unit/
    │   ├── prompts/
    │   │   └── test_system_prompt_decision_tree.py      # NOUVEAU — vérifie présence DECISION_TREE/ANTI_PATTERNS, budget tokens
    │   └── graph/
    │       └── tools/
    │           └── test_with_retry_fallback.py          # NOUVEAU — teste retry+fallback
    ├── integration/
    │   └── admin_metrics/
    │       └── test_validation_failures_endpoint.py     # NOUVEAU — endpoint admin
    └── llm_eval/
        ├── __init__.py                                  # CONSERVÉ
        ├── golden_set.json                              # NOUVEAU — 50 cas (distinct de golden_set_50.json F01)
        ├── golden_set_50.json                           # CONSERVÉ — F01 (validator citation)
        ├── test_validator_golden_set.py                 # CONSERVÉ — F01
        ├── test_eval_runner.py                          # NOUVEAU — runner LLM eval
        └── conftest.py                                  # NOUVEAU — load_golden_set fixture, eval-report writer

frontend/
└── (Pas de changement majeur — fallback géré côté tool)

docs/
└── llm-eval-loop.md                                     # NOUVEAU — process eval, métriques, ajout cas

.github/
└── workflows/
    └── ci.yml                                           # MODIFIÉ — ajout step pytest tests/llm_eval/ avec path-filter
```

**Structure Decision** : structure web-service classique (backend FastAPI, frontend Nuxt 4). F22 est ~95 % backend. La majorité des modifications portent sur 3 zones :

1. `app/prompts/system.py` (constantes DECISION_TREE, ANTI_PATTERNS injectées dans BASE_PROMPT)
2. `app/graph/tools/` (décorateur `@with_retry` + standardisation docstrings)
3. `tests/llm_eval/` (nouveau golden set + runner)

Plus une nouvelle migration Alembic 032, un module admin metrics, et un step CI conditionnel.

## Phases

### Phase 0 — Research

Sortie : `research.md`. Sujets :

- Pattern `@with_retry` LangChain : comment intercepter `pydantic.ValidationError` dans le décorateur sans casser le retour `requires_destructive_confirmation` ?
- Format `eval-report.json` : aligner sur conventions LangSmith/promptfoo si applicable, ou format custom ?
- Path-filter GitHub Actions : syntaxe pour ne déclencher le job eval que sur certains chemins.
- Calibrage golden set : quels cas vraiment représentatifs ? Échantillonnage des conversations existantes.
- Token counting : utiliser `tiktoken` ? Ou comparaison brute longueur ?

### Phase 1 — Design

Sortie : `data-model.md` + `contracts/`.

**`data-model.md`** documente :
- Extension `tool_call_logs.validation_error: jsonb | null`
- Schéma `golden_case` (JSON)
- Schéma `eval_report` (JSON)

**`contracts/`** :
- `golden_case_schema.json` : JSON Schema strict
- `eval_report_schema.json` : JSON Schema strict
- `admin_metrics_endpoint.md` : OpenAPI-like spec de `GET /api/admin/metrics/validation-failures`

**`quickstart.md`** :
- Comment exécuter le golden set en local (`pytest tests/llm_eval/ -m eval`)
- Comment ajouter un cas (process review)
- Comment interpréter `eval-report.json`
- Comment déclencher manuellement la CI eval

### Phase 2 — Tasks (NOT created by /speckit.plan)

Voir `tasks.md` (généré par `/speckit.tasks`).

## Migration Alembic 032

```python
"""F22 — Add validation_error column to tool_call_logs

Revision ID: 032_add_validation_error_tool_call_logs
Revises: 031_extend_interactive_questions
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "032_add_validation_error_tool_call_logs"
down_revision = "031_extend_interactive_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tool_call_logs",
        sa.Column(
            "validation_error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Détails Pydantic ValidationError (errors() liste) en cas d'échec",
        ),
    )


def downgrade() -> None:
    op.drop_column("tool_call_logs", "validation_error")
```

Note : la colonne est nullable, default null → migration zero-downtime, pas de backfill nécessaire.

## CI Configuration

### GitHub Actions step (extrait `.github/workflows/ci.yml`)

```yaml
  llm-eval:
    name: LLM Eval (Golden Set 50 cas)
    runs-on: ubuntu-22.04
    if: |
      github.event_name == 'pull_request' && (
        contains(github.event.pull_request.changed_files, 'app/prompts/') ||
        contains(github.event.pull_request.changed_files, 'app/graph/tools/') ||
        contains(github.event.pull_request.changed_files, 'tests/llm_eval/')
      )
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r backend/requirements.txt
      - env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          cd backend
          pytest tests/llm_eval/ -m eval --golden-report=eval-report.json -v
      - uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: backend/eval-report.json
```

(Note : la syntaxe `changed_files` est simplifiée — implémentation réelle utilisera `dorny/paths-filter@v3` ou équivalent, voir `research.md`.)

## Risques & Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Decision tree fait exploser tokens prompt | Moyenne | Moyen | `_tokens_baseline.json` gate +25 % max ; mesure dans `test_system_prompt_decision_tree.py` |
| `with_retry` masque bugs réels | Faible | Moyen | `retry_count` loggé ; alerte admin si >5 % retry sur un tool |
| Golden set se désaligne avec évolutions tools | Élevée | Faible | Process documenté `docs/llm-eval-loop.md` ; review obligatoire à chaque PR tool/prompt |
| Coût LLM CI excessif | Moyenne | Faible | Path-filter ; cassette cache (phase 2 hors-scope) |
| Faux positifs eval (LLM choisit tool synonyme) | Élevée | Faible | Whitelist par cas, matching tolérant `subset_match` |
| Régression sur tests existants | Faible | Élevé | Run pytest complet en CI obligatoire avant merge |
| Endpoint admin lent sur gros volumes | Faible | Moyen | Index sur `(created_at, status, validation_error IS NOT NULL)` ; pagination |

## Complexity Tracking

Aucune violation du Constitution Check. La complexité ajoutée est justifiée :
- **Décorateur `with_retry` étendu** : nécessaire pour fallback structuré, alternative rejetée (try/except dans chaque tool) car violerait DRY sur 11+ tools.
- **Module admin_metrics dédié** : nécessaire pour isoler la logique d'agrégation et permettre futures métriques (retry rate, latency par tool, etc.). Alternative rejetée (route inline dans `chat/router.py`) car mélange responsabilités.
- **Test runner LLM eval séparé** : nécessaire pour marker `pytest.mark.eval` et gestion budget LLM. Alternative rejetée (intégrer dans tests/integration/) car couperait le run par défaut.
