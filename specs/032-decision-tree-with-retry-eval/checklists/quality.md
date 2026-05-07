# Quality Checklist — F22

## Pre-implementation

- [ ] Spec.md relue, clarifications complètes
- [ ] Plan.md aligne sur architecture projet (FastAPI + LangGraph)
- [ ] Migration Alembic 032 numéro disponible
- [ ] Branch `feat/F22-decision-tree-with-retry-eval` créée
- [ ] Aucun conflit avec features mergées (F01, F02, F03, F04, F05, F06, F07, F08, F10, F11, F12, F13, F17)

## During implementation

- [ ] TDD strict : tests écrits avant impl, doivent FAIL initialement
- [ ] Commit après chaque task ou groupe logique
- [ ] Run pytest local après chaque modification de tool
- [ ] Vérifier docstrings 5 sections respectent gabarit
- [ ] Vérifier logs `tool_call_logs.validation_error` peuplés correctement

## Post-implementation

- [ ] Run pytest complet — 0 régression sur ~935 tests existants
- [ ] Run `pytest tests/llm_eval/ -m eval` — gates respectés
  - [ ] `tool_match_rate >= 0.90`
  - [ ] `payload_valid_rate >= 0.95`
  - [ ] `hallucination_rate < 0.01`
  - [ ] `fallback_rate < 0.05`
- [ ] Couverture `app/graph/tools/common.py:with_retry` >= 90 %
- [ ] Couverture `app/modules/admin_metrics/` >= 80 %
- [ ] Couverture `tests/llm_eval/test_eval_runner.py` >= 80 %
- [ ] Token budget system prompt < +25 % vs baseline
- [ ] Test conformity passe pour tous les tools (39 estimés)
- [ ] Endpoint admin testable manuellement avec admin JWT

## Pre-PR

- [ ] Documentation `docs/llm-eval-loop.md` complète
- [ ] CLAUDE.md mis à jour (Recent Changes)
- [ ] Workflow CI `.github/workflows/ci.yml` ajouté avec path-filter
- [ ] Variable secret `OPENROUTER_API_KEY` configurée dans GitHub
- [ ] Branche rebasée sur main, sans conflit

## PR review

- [ ] Code review (code-reviewer agent)
- [ ] Security review (endpoint admin)
- [ ] Tests E2E + LLM eval verts en CI
- [ ] Pas de fichiers sensibles commités (.env, etc.)
- [ ] Gates CI tous verts (golden set, conformity, test complet)

## Merge criteria

- [ ] All checks green
- [ ] Reviewer approval
- [ ] Branch up-to-date with main
- [ ] No merge conflicts
- [ ] Documentation reviewed
- [ ] Migration Alembic testée up/down sur staging
