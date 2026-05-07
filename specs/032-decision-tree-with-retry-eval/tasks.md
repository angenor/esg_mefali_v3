---
description: "Task list for F22 — Decision Tree + with_retry + Golden Set 50 cas"
---

# Tasks: F22 — Decision Tree dans System Prompt + with_retry Effectif + Golden Set 50 cas

**Input**: Design documents from `/specs/032-decision-tree-with-retry-eval/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: TDD obligatoire (rule globale projet, 80 % coverage min). Tests E2E + LLM eval golden set inclus.

**Organization**: Tasks groupées par user story pour permettre implémentation/test/livraison indépendants.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallèle (fichiers différents, aucune dépendance)
- **[Story]**: US1 / US2 / US3 / US4 / US5 (cf. spec.md)
- Chemins absolus des fichiers (par convention projet)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Préparer l'environnement et les outils de mesure communs.

- [ ] **T001** [P] Créer le dossier `backend/tests/llm_eval/` (déjà existant) et confirmer présence de `__init__.py`. Vérifier que `golden_set_50.json` (F01) reste intact.
- [ ] **T002** [P] Créer fichier `backend/tests/unit/prompts/test_system_prompt_decision_tree.py:_tokens_baseline.json` (sera créé par test bootstrap au premier run) — placeholder dans `.gitignore` ou commit baseline initial.
- [ ] **T003** [P] Ajouter le marker `eval` à `backend/pyproject.toml` (`[tool.pytest.ini_options].markers`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration BDD + extension `with_retry` (sans appliquer aux tools encore).

**CRITICAL**: Aucune US ne peut commencer avant Phase 2.

- [ ] **T004** Créer migration Alembic `backend/alembic/versions/032_add_validation_error_tool_call_logs.py` :
  - `revision = "032_add_validation_error_tool_call_logs"`
  - `down_revision = "031_extend_interactive_questions"`
  - `op.add_column("tool_call_logs", sa.Column("validation_error", JSONB, nullable=True, comment="..."))`
  - `downgrade()`: `op.drop_column("tool_call_logs", "validation_error")`
  - Tester la migration up/down sur SQLite (mock JSONB) et PostgreSQL.
- [ ] **T005** Étendre le modèle `backend/app/models/tool_call_log.py` : ajout `validation_error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)`.
- [ ] **T006** Étendre `backend/app/graph/tools/common.py:with_retry()` :
  - Signature : `def with_retry(func=None, *, max_retries=1, node_name="", fallback_message: str | None = None)`
  - Support double-syntaxe : `@with_retry(...)` (paramétré) et `@with_retry` (legacy, sans param) → utiliser pattern `if func is None: return decorator`.
  - Capturer `pydantic.ValidationError` séparément → sérialiser via `e.errors()` dans `validation_error` (JSONB).
  - Logger via `log_tool_call(..., validation_error=...)` (signature étendue).
  - Si retry échoue ET `fallback_message` fourni → retourner `json.dumps({"success": False, "fallback_message": fallback_message})`.
  - Sinon → comportement actuel (`f"Erreur : {e}"`).
- [ ] **T007** Étendre `log_tool_call()` dans `common.py` pour accepter `validation_error: list[dict] | None = None` et le persister.
- [ ] **T008** [P] Créer test unitaire `backend/tests/unit/graph/tools/test_with_retry_fallback.py` (TDD — écrire avant T006/T007 finalisés) :
  - Test : retry réussit au 2e essai → `retry_count=1`, `status="retry_success"`, `validation_error` non null.
  - Test : retry échoue, fallback_message fourni → retour JSON `{"success": False, "fallback_message": "..."}`.
  - Test : retry échoue, pas de fallback_message → retour `f"Erreur : {e}"` (legacy).
  - Test : ValidationError → `validation_error` peuplé avec `errors()`.
  - Test : exception runtime non-Pydantic → `error_message` peuplé, `validation_error` null.
  - Test : succès du premier coup → `validation_error` null, `retry_count=0`.
  - Test : passthrough du retour `requires_destructive_confirmation` (pas de retry inutile).

**Checkpoint**: Foundation prête — la migration et le décorateur fonctionnent. Aucun tool n'est encore décoré.

---

## Phase 3: User Story 1 - Decision Tree explicite (Priority: P1) MVP

**Goal**: Ajouter `DECISION_TREE` et `ANTI_PATTERNS` au system prompt.

**Independent Test**: Lancer le golden set et vérifier que le tool attendu est invoqué dans > 90 % des cas par rapport au baseline pré-decision-tree.

### Tests for User Story 1 (TDD)

> **Écrire ces tests AVANT implémentation, ils DOIVENT échouer initialement.**

- [ ] **T009** [P] [US1] Créer `backend/tests/unit/prompts/test_system_prompt_decision_tree.py` :
  - Test : `BASE_PROMPT` contient `## ARBRE DE DÉCISION TOOL — RÈGLES OBLIGATOIRES`.
  - Test : `BASE_PROMPT` contient `## ANTI-PATTERNS À ÉVITER`.
  - Test : `DECISION_TREE` contient les 5 sections (Question fermée, Visualisation utile, Mutation métier, Affirmation factuelle, Chaînage de tools).
  - Test : `ANTI_PATTERNS` contient au moins 5 anti-exemples explicites (`NE FAIS PAS`).
  - Test : budget tokens — `len(BASE_PROMPT)` < `baseline * 1.25` (créer baseline au premier run).

### Implementation for User Story 1

- [ ] **T010** [US1] Ajouter constante `DECISION_TREE: str` dans `backend/app/prompts/system.py` après `BASE_PROMPT` actuel (avec les 5 sections du spec, ordres et règles exacts).
- [ ] **T011** [US1] Ajouter constante `ANTI_PATTERNS: str` dans `backend/app/prompts/system.py` (5 anti-exemples : chiffre sans cite_source, question fermée en texte, delete sans confirmation, radar pour 1 chiffre, modification du catalogue).
- [ ] **T012** [US1] Refactorer `BASE_PROMPT = f"""{base_existant}\n\n{DECISION_TREE}\n\n{ANTI_PATTERNS}"""`. Garder `SYSTEM_PROMPT = BASE_PROMPT` pour compat.
- [ ] **T013** [US1] Régénérer baseline `_tokens_baseline.json` si croissance < 25 % (sinon refuser et raffiner).

**Checkpoint**: US1 fonctionnel et testable indépendamment. Le system prompt contient les règles décisionnelles.

---

## Phase 4: User Story 2 - `with_retry` effectif sur 11 tools (Priority: P1)

**Goal**: Décorer 11 tools de mutation critique avec `@with_retry(fallback_message=...)`.

**Independent Test**: Pour chaque tool, simuler échec Pydantic → vérifier retry + fallback structuré.

### Tests for User Story 2 (TDD)

- [ ] **T014** [P] [US2] Créer test paramétré `backend/tests/unit/graph/tools/test_with_retry_applied_tools.py` :
  - Liste : `[update_company_profile, batch_save_esg_criteria, finalize_esg_assessment, finalize_carbon_assessment, create_fund_application, generate_credit_score, generate_action_plan, update_action_item, update_project, delete_project, generate_credit_certificate]`.
  - Test : chaque tool est décoré (vérifier via `inspect.unwrap` ou attribut `__wrapped__`).
  - Test : chaque tool a un `fallback_message` non vide.
  - Test : `update_company_profile` simulate ValidationError → retour `{"success": False, "fallback_message": "Je n'arrive pas à formaliser cette mise à jour de profil. Pouvez-vous me reformuler ?"}`.

### Implementation for User Story 2

- [ ] **T015** [P] [US2] Décorer `update_company_profile` dans `backend/app/graph/tools/profiling_tools.py` :
  - `@with_retry(max_retries=1, fallback_message="Je n'arrive pas à formaliser cette mise à jour de profil. Pouvez-vous me reformuler ?")`.
- [ ] **T016** [P] [US2] Décorer `batch_save_esg_criteria` et `finalize_esg_assessment` dans `backend/app/graph/tools/esg_tools.py`.
- [ ] **T017** [P] [US2] Décorer `finalize_carbon_assessment` dans `backend/app/graph/tools/carbon_tools.py`.
- [ ] **T018** [P] [US2] Décorer `create_fund_application` dans `backend/app/graph/tools/application_tools.py`.
- [ ] **T019** [P] [US2] Décorer `generate_credit_score` et `generate_credit_certificate` dans `backend/app/graph/tools/credit_tools.py`.
- [ ] **T020** [P] [US2] Décorer `generate_action_plan` et `update_action_item` dans `backend/app/graph/tools/action_plan_tools.py`.
- [ ] **T021** [P] [US2] Décorer `update_project` et `delete_project` dans `backend/app/graph/tools/project_tools.py` (F06) — vérifier passthrough du `requires_destructive_confirmation`.

**Checkpoint**: US2 fonctionnel. 11 tools de mutation ont retry+fallback.

---

## Phase 5: User Story 3 - Standardisation docstrings (Priority: P2)

**Goal**: Aligner toutes les docstrings sur le gabarit 5 sections.

**Independent Test**: `pytest backend/tests/graph/tools/test_tools_meta_conformity.py -v` passe pour tous les tools.

### Tests for User Story 3 (TDD)

- [ ] **T022** [US3] Étendre `backend/tests/graph/tools/test_tools_meta_conformity.py` :
  - Importer tous les groupes : `INTERACTIVE_TOOLS, PROFILING_TOOLS, ESG_TOOLS, APPLICATION_TOOLS, CHAT_TOOLS, CARBON_TOOLS, FINANCING_TOOLS, CREDIT_TOOLS, ACTION_PLAN_TOOLS, DOCUMENT_TOOLS, GUIDED_TOUR_TOOLS, SOURCING_TOOLS, PROJECT_TOOLS, VISUALIZATION_TOOLS, MEMORY_TOOLS`.
  - `SCOPE_TOOLS = [*INTERACTIVE_TOOLS, ..., *MEMORY_TOOLS]`.
  - Mettre à jour `test_scope_count` avec le nouveau total attendu.
  - Tests existants (`test_description_min_length`, `test_description_has_5_sections`, `test_args_schema_extra_forbid`, `test_closed_choices_are_enum`) appliqués au nouveau scope.

### Implementation for User Story 3 (par groupe, ordre incrémental)

- [ ] **T023** [P] [US3] Réécrire docstrings 5 sections pour `carbon_tools.py` (4 tools : `create_carbon_assessment`, `save_emission_entry`, `finalize_carbon_assessment`, `get_carbon_summary`).
- [ ] **T024** [P] [US3] Réécrire docstrings 5 sections pour `chat_tools.py` (4 tools : `get_user_dashboard_summary`, `get_company_profile_chat`, `get_esg_assessment_chat`, `get_carbon_summary_chat`).
- [ ] **T025** [P] [US3] Réécrire docstrings 5 sections pour `document_tools.py` (3 tools : `analyze_uploaded_document`, `get_document_analysis`, `list_user_documents`).
- [ ] **T026** [P] [US3] Réécrire docstrings 5 sections pour `credit_tools.py` (3 tools : `generate_credit_score`, `get_credit_score`, `generate_credit_certificate`).
- [ ] **T027** [P] [US3] Réécrire docstrings 5 sections pour `action_plan_tools.py` (3 tools : `generate_action_plan`, `update_action_item`, `get_action_plan`).
- [ ] **T028** [P] [US3] Réécrire docstrings 5 sections pour `financing_tools.py` (7 tools : `search_compatible_funds`, `save_fund_interest`, `get_fund_details`, `create_fund_application`, `list_offers`, `get_offer`, `compare_offers_for_fund`).
- [ ] **T029** [P] [US3] Réécrire docstring 5 sections pour `guided_tour_tools.py` (1 tool : `trigger_guided_tour`).
- [ ] **T030** [P] [US3] Vérifier `sourcing_tools.py` (F01 — 3 tools : `cite_source`, `search_source`, `flag_unsourced`) — déjà conforme ou à réécrire.
- [ ] **T031** [P] [US3] Vérifier `project_tools.py` (F06) — déjà conforme ou à réécrire.
- [ ] **T032** [P] [US3] Vérifier `visualization_tools.py` (F11) — déjà conforme ou à réécrire.
- [ ] **T033** [P] [US3] Vérifier `memory_tools.py` (F12 — 1 tool : `recall_history`) — déjà conforme ou à réécrire.

**Checkpoint**: US3 fonctionnel. Tous les tools (39 estimés) passent le test conformity.

---

## Phase 6: User Story 4 - Golden Set 50 cas + test runner (Priority: P1)

**Goal**: Créer 50 cas + test runner avec gates métriques.

**Independent Test**: `pytest backend/tests/llm_eval/ -m eval --golden-report=eval-report.json -v` produit un rapport avec `tool_match_rate >= 0.90`.

### Tests for User Story 4 (TDD pour helpers, runner final)

- [ ] **T034** [P] [US4] Créer `backend/tests/llm_eval/conftest.py` avec :
  - Fixture `load_golden_set()` : lit `golden_set.json`, valide via JSON Schema (`contracts/golden_case_schema.json`).
  - Fixture `eval_report_writer(request)` : à la fin de la session pytest, écrit `eval-report.json` si `--golden-report` passé.
  - Helper `subset_match(actual: dict, expected: dict) -> bool`.
- [ ] **T035** [P] [US4] Créer test du helper `backend/tests/unit/test_subset_match.py` :
  - `subset_match({"a": 1, "b": 2}, {"a": 1}) == True`.
  - `subset_match({"a": 1}, {"a": 2}) == False`.
  - `subset_match({}, {"a": 1}) == False`.
  - `subset_match({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}}) == True` (récursif).

### Implementation for User Story 4

- [ ] **T036** [US4] Créer `backend/tests/llm_eval/golden_set.json` avec **50 cas** (NON `golden_set_50.json` qui appartient à F01) :
  - 10 cas profilage (entreprise + projets F06)
  - 8 cas ESG (saisie indicateur, finalize, multi-référentiels F13)
  - 6 cas carbone (saisie emission, choix catégorie, F17)
  - 6 cas financement (matching F14, simulateur F16, comparateur)
  - 6 cas applications (création F15, génération section, statut)
  - 5 cas crédit (Mobile Money F18, photos, attestation F08)
  - 4 cas plan d'action (création, update, badges)
  - 5 cas conversationnels (oui/non, recall_history F12, greeting, ambigu, fallback)
  - Format conforme à `contracts/golden_case_schema.json`.
- [ ] **T037** [US4] Créer `backend/tests/llm_eval/test_eval_runner.py` :
  - `pytestmark = pytest.mark.eval`
  - `@pytest.mark.parametrize("case", load_golden_set(), ids=lambda c: c["id"])`
  - `async def test_golden_case(case, db_session, eval_report_writer):`
  - Invoquer le graph LangGraph avec le contexte (current_page, active_module, user_message).
  - Capturer le tool invoqué (via `tool_call_logs` ou trace LangGraph).
  - Comparer `actual_tool` vs `expected.tool_called` (whitelist tolérée).
  - Comparer `actual_payload` vs `expected.payload_contains` via `subset_match`.
  - Enregistrer résultat dans `eval_report_writer`.
- [ ] **T038** [US4] Étendre `backend/conftest.py` ou créer hook pytest pour calculer les métriques agrégées (`tool_match_rate`, etc.) et les écrire dans `eval-report.json` à la fin de la session.
- [ ] **T039** [US4] Ajouter gates métriques en post-processing (`pytest_sessionfinish` ou test dédié) :
  - `tool_match_rate >= 0.90` → fail si non respecté.
  - `payload_valid_rate >= 0.95`.
  - `hallucination_rate < 0.01`.
  - `fallback_rate < 0.05` (warning, non bloquant).

**Checkpoint**: US4 fonctionnel. Golden set 50 cas exécutable, métriques rapportées.

---

## Phase 7: User Story 5 - Endpoint admin metrics (Priority: P2)

**Goal**: Endpoint `/api/admin/metrics/validation-failures` agrégeant les échecs.

**Independent Test**: `curl -H "Authorization: Bearer <admin_jwt>" "...?period=7d"` retourne JSON conforme au contrat.

### Tests for User Story 5 (TDD)

- [ ] **T040** [P] [US5] Créer `backend/tests/integration/admin_metrics/test_validation_failures_endpoint.py` :
  - Test : Admin peut appeler l'endpoint, reçoit 200 + JSON conforme.
  - Test : User non-admin reçoit 403.
  - Test : `period=24h|7d|30d` filtre correctement la fenêtre temporelle.
  - Test : `failure_rate` calculé correctement (mock 100 logs dont 5 avec validation_error → 0.05).
  - Test : `top_tools` agrégé par tool_name, ordre desc.
  - Test : `alert=true` si `failure_rate > 0.05`.
  - Test : 0 logs → `failure_rate=0.0`, `top_tools=[]`, `alert=false`.

### Implementation for User Story 5

- [ ] **T041** [US5] Créer `backend/app/modules/admin_metrics/__init__.py`.
- [ ] **T042** [US5] Créer `backend/app/modules/admin_metrics/service.py` :
  - `async def get_validation_failures(db, period: str, limit: int) -> ValidationFailuresResponse`.
  - SQL agrégation conforme à `contracts/admin_metrics_endpoint.md`.
  - Calcul `alert = failure_rate > 0.05`.
- [ ] **T043** [US5] Créer `backend/app/modules/admin_metrics/router.py` :
  - `GET /api/admin/metrics/validation-failures?period=7d&limit=10`
  - `Depends(require_admin_role)` (de F02)
  - Response Pydantic `ValidationFailuresResponse`
  - Query validation : `period: Literal["24h", "7d", "30d"] = "7d"`, `limit: int = Field(10, ge=1, le=50)`.
- [ ] **T044** [US5] Enregistrer le router dans `backend/app/main.py` ou `app/api/v1.py` (selon convention).

**Checkpoint**: US5 fonctionnel. Endpoint admin retourne agrégation.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, CI, finitions.

- [ ] **T045** [P] Créer `docs/llm-eval-loop.md` (process eval, métriques, ajout cas, troubleshooting) — utiliser le contenu de `quickstart.md` comme base.
- [ ] **T046** [P] Modifier `.github/workflows/ci.yml` :
  - Ajouter job `llm-eval` avec `needs: changes` et path-filter via `dorny/paths-filter@v3` sur `backend/app/prompts/**`, `backend/app/graph/tools/**`, `backend/tests/llm_eval/**`.
  - Step : `pytest tests/llm_eval/ -m eval --golden-report=eval-report.json`.
  - Upload artifact `eval-report.json`.
  - Variable secret `OPENROUTER_API_KEY` configurée.
- [ ] **T047** Run pytest complet (sans `-m eval`) → vérifier 0 régression sur les ~935 tests existants.
- [ ] **T048** Run `pytest tests/llm_eval/ -m eval` localement → vérifier rapport `eval-report.json` et gates.
- [ ] **T049** Vérifier couverture >= 80 % sur les nouveaux modules (`with_retry` extension, `test_eval_runner`, `admin_metrics`) via `pytest --cov`.
- [ ] **T050** [P] Mettre à jour `CLAUDE.md` (Active Technologies, Recent Changes) avec entrée F22.
- [ ] **T051** Vérifier la couverture de `app/graph/tools/common.py:with_retry` >= 90 % (cœur critique).
- [ ] **T052** [P] (Optionnel/UX) Frontend : afficher message dégradé "Je n'arrive pas à formaliser, pouvez-vous reformuler ?" quand le tool retourne `{"success": False, "fallback_message": "..."}` — déjà géré au niveau frontend si pattern existant.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001-T003 indépendants.
- **Foundational (Phase 2)**: T004-T008 — bloquent toutes les US (sauf US3 qui peut commencer en parallèle).
- **US1 (P1)**: T009-T013, indépendant des autres US (modifie uniquement `system.py`).
- **US2 (P1)**: T014-T021, dépend de Phase 2 (T006 `with_retry` étendu).
- **US3 (P2)**: T022-T033, indépendant des autres US (modifie docstrings).
- **US4 (P1)**: T034-T039, dépend idéalement d'US1 (decision tree dans le prompt). Peut commencer dès Phase 2 mais résultats meilleurs après US1.
- **US5 (P2)**: T040-T044, dépend de Phase 2 (T004-T005 colonne validation_error).
- **Polish (Phase 8)**: T045-T052, dépend de toutes les phases précédentes.

### User Story Dependencies

- US1 + US3 sont indépendants (différents fichiers).
- US2 dépend de Phase 2 (with_retry étendu).
- US4 utilise US1 (golden set teste les effets du decision tree).
- US5 dépend de Phase 2 (colonne validation_error).

### Within Each User Story

- Tests AVANT implémentation (TDD obligatoire).
- Modèles avant services.
- Services avant endpoints.
- Documentation après implémentation.

### Parallel Opportunities

- T001, T002, T003 en parallèle.
- T009 (test US1) en parallèle avec T014 (test US2) en parallèle avec T022 (test US3) en parallèle avec T040 (test US5).
- T015-T021 peuvent tous être faits en parallèle (différents fichiers tools).
- T023-T033 peuvent tous être faits en parallèle (différents fichiers tools).

---

## Implementation Strategy

### MVP First (US1 + US2 + US4)

1. Phase 1 + Phase 2 (Foundation : migration, with_retry étendu).
2. US1 (Decision Tree) — texte injecté dans prompt.
3. US2 (with_retry sur 11 tools) — décorateurs.
4. US4 (Golden Set + runner) — mesure quantitative.
5. **STOP & VALIDATE** : run golden set, vérifier gates `>= 0.90`.
6. Demo / merge gate.

### Incremental Delivery

1. US3 (docstrings) — peut être livré après MVP, en parallèle.
2. US5 (endpoint admin) — visibilité monitoring, peut être livré après.
3. Polish (CI, docs) — finalisation.

### Parallel Team Strategy

Avec plusieurs développeurs :

1. Dev A : Phase 2 (T004-T008).
2. Une fois Phase 2 prête :
   - Dev A : US1 + US2 + US4 (chaîne MVP).
   - Dev B : US3 (docstrings standardisation).
   - Dev C : US5 (endpoint admin).
3. Polish : tous en parallèle (docs, CI, regression check).

---

## Notes

- [P] tasks = fichiers différents, sans dépendance.
- TDD strict : tests AVANT implémentation, doivent FAIL initialement.
- Commit après chaque task ou groupe logique (`chore(F22): T0XX <description>`).
- Stop à chaque checkpoint pour valider la story indépendamment.
- Couverture ≥ 80 % obligatoire (rule globale).
- 0 régression sur tests existants (gate CI).
