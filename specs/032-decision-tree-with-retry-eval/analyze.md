# Cross-Artifact Analysis: F22 — Decision Tree + with_retry + Golden Set

**Date** : 2026-05-07
**Auteur** : SpecKit Phase A (autonome, post `/speckit.tasks`)
**Status** : OK — pas de blocage critique identifié

## Vue d'ensemble

| Artefact | Taille | Conformité |
|----------|--------|------------|
| spec.md | 5 user stories, 15 FR, 9 SC, 11 assumptions | ✓ Format respecté |
| plan.md | 8 phases logiques, technical context complet, structure projet | ✓ Format respecté |
| research.md | 10 décisions documentées (R1-R10) | ✓ Couvre toutes les ambiguïtés |
| data-model.md | 5 entités (validation_error, GoldenCase, EvalReport, DecisionTree, AdminResponse) | ✓ Schémas complets |
| quickstart.md | 8 sections (lancement, interprétation, ajout, debug, monitoring, process, refs) | ✓ Actionnable |
| contracts/ | 3 fichiers (golden_case_schema, eval_report_schema, admin_metrics_endpoint) | ✓ JSON Schema valides |
| tasks.md | 52 tâches en 8 phases, mapping US correct | ✓ Format respecté |

## Couverture FR → Tasks

| FR | Coverage | Tasks |
|----|----------|-------|
| FR-001 (DECISION_TREE in prompt) | ✓ | T010, T012, T009 (test) |
| FR-002 (ANTI_PATTERNS in prompt) | ✓ | T011, T012, T009 (test) |
| FR-003 (with_retry param fallback_message) | ✓ | T006, T008 (test) |
| FR-004 (11 tools décorés) | ✓ | T015-T021, T014 (test) |
| FR-005 (toutes docstrings 5 sections) | ✓ | T023-T033, T022 (test) |
| FR-006 (test conformity étendu) | ✓ | T022 |
| FR-007 (golden_set.json 50 cas) | ✓ | T036 |
| FR-008 (test_eval_runner.py) | ✓ | T037 |
| FR-009 (eval-report.json) | ✓ | T038 |
| FR-010 (migration 032) | ✓ | T004 |
| FR-011 (endpoint admin) | ✓ | T040-T044 |
| FR-012 (CI conditionnel) | ✓ | T046 |
| FR-013 (docs/llm-eval-loop.md) | ✓ | T045 |
| FR-014 (matching tolérant) | ✓ | T034, T037 |
| FR-015 (validation_error peuplé) | ✓ | T006, T007, T008 (test) |

**Conclusion** : 15/15 FR couverts par au moins une tâche.

## Couverture User Stories → Tasks

| US | Tasks | Tests inclus | Indépendant ? |
|----|-------|--------------|---------------|
| US1 (Decision Tree) | T009-T013 (5) | T009 (TDD) | ✓ Oui |
| US2 (with_retry) | T014-T021 (8) | T014 (TDD) | ✓ Oui (après Phase 2) |
| US3 (Docstrings) | T022-T033 (12) | T022 (TDD) | ✓ Oui |
| US4 (Golden Set) | T034-T039 (6) | T034, T035 (TDD) | ✓ Oui (après US1 idéal) |
| US5 (Endpoint admin) | T040-T044 (5) | T040 (TDD) | ✓ Oui (après Phase 2) |

**Conclusion** : Chaque US a sa story indépendamment livrable + tests TDD avant implémentation.

## Détection d'incohérences

### ✓ Cohérences vérifiées

1. **Migration Alembic** — `down_revision="031_extend_interactive_questions"` cohérent avec dernière migration 031 confirmée par `ls alembic/versions/`.
2. **Spec number 032** — disponible (specs/ contient jusqu'à 031).
3. **Tools décorés** — 11 tools (pas 12 comme fiche F22) car `update_application_status` est service-only, et `generate_attestation` n'est pas encore tool LangChain. Documenté dans clarifications.
4. **Golden set fichier distinct** — `golden_set.json` (F22) vs `golden_set_50.json` (F01) — pas de conflit, pas d'écrasement.
5. **Test conformity** — extension du scope déjà couverte par T022, signature compatible avec test existant.

### ⚠ Points d'attention (non-bloquants)

1. **`update_application_status` mentionné dans la fiche F22** mais n'est pas un tool LangChain dans le code actuel. Décision : NON inclus dans la liste des 11 tools décorés. À ajouter quand le tool sera promu.

2. **`generate_attestation` (F08)** — pareil, fonction service uniquement. La fiche F22 le liste, mais on a substitué `generate_credit_certificate` (qui existe déjà comme tool dans `credit_tools.py`) pour atteindre les 11 tools de mutation critique. Documenté dans clarifications.

3. **CI path-filter** — la syntaxe exacte `dorny/paths-filter@v3` doit être vérifiée selon la config CI actuelle. Couvert par T046 + research R3.

4. **Token budget gate** — le baseline `_tokens_baseline.json` n'existe pas encore. T002 prévoit le bootstrap au premier run. Non bloquant.

5. **Coût LLM** — golden set à $2/run × 10-20 runs/mois = $20-40/mois. Acceptable pour CI conditionnel. Cassettes hors-scope phase 1 (R7).

### ✓ Risques mitigés

| Risque | Mitigation |
|--------|------------|
| Régression tests existants | T047 (run pytest complet) |
| Token budget exceeded | T013 (régénérer baseline si OK) + gate test (T009) |
| Golden set drift | T045 (process docs) + review obligatoire (mentionné spec) |
| Fallback masque bugs | `validation_error` jsonb + endpoint admin (US5) |
| Faux positifs eval | Whitelist tools dans `expected.tool_called` (FR-014) |

## Conformité Architecture

- **Modules existants modifiés** : 11 fichiers tools (décorations + docstrings), 1 fichier prompt, 1 fichier modèle SQL, 1 test conformity.
- **Modules nouveaux** : `admin_metrics/` (router + service), `tests/llm_eval/` (golden_set, runner, conftest), 1 migration Alembic, 1 doc.
- **Pas de changement** : frontend (juste optionnel pour l'affichage fallback), API contrats existants, table `tool_call_logs` (extension nullable seulement).

## Conformité Sécurité

- ✓ Endpoint admin protégé par `require_admin_role` (F02, déjà en place).
- ✓ Pas de retour de `validation_error` brut dans l'endpoint (peut contenir données sensibles via Pydantic `input` field).
- ✓ Pas de hardcoded secret. `OPENROUTER_API_KEY` via env.
- ✓ Validation Pydantic sur query params endpoint (FastAPI).

## Conformité Performance

- ✓ Endpoint admin < 500ms P95 (index existant `idx_tool_call_logs_created_at_status`).
- ✓ Migration zero-downtime (colonne nullable, default null).
- ✓ Golden set runner ~5-10 min (acceptable pour CI conditionnel).
- ✓ Token budget < +25 % gate testable.

## Conformité Tests

- ✓ TDD obligatoire (test avant impl) — T008, T009, T014, T022, T034, T035, T040.
- ✓ Couverture ≥ 80 % (rule globale) — T049.
- ✓ Tests E2E inclus (golden set 50 cas).
- ✓ 0 régression — T047.

## Statut

**ANALYZE STATUS: OK** — aucun blocage critique. Le feature est prêt pour `/speckit.implement`.

Points mineurs à confirmer en implémentation :
1. Confirmer la liste finale exacte des 11 tools (vs 12 fiche F22) avec l'équipe.
2. Bootstrap `_tokens_baseline.json` lors du premier run de T009.
3. Vérifier la disponibilité de `dorny/paths-filter@v3` dans le runner GitHub Actions actuel.

## Prochaines étapes

1. Commit SpecKit artifacts (`chore(F22): SpecKit artifacts (spec/plan/tasks/analyze)`).
2. `/speckit.implement` ou implémentation manuelle dans une session dédiée.
3. Run `pytest tests/llm_eval/ -m eval` localement avant push.
4. PR avec test plan détaillé.
