# Quality Checklist — F23 Skills (Playbooks Métier)

## Pre-implementation

- [ ] Spec.md relue, clarifications complètes (anti-injection, eval gating, versioning, snapshot conversations)
- [ ] Plan.md aligne sur architecture projet (FastAPI + LangGraph + Nuxt 4 admin)
- [ ] Migration Alembic 033 numéro disponible (down_revision=`032_add_validation_error_tool_call_logs`)
- [ ] Branch `feat/F23-skills-playbooks-metier` créée à partir de main
- [ ] Aucun conflit avec features mergées (F01-F08, F10-F13, F17, F22)
- [ ] Vérifier que `tiktoken` est dans `backend/requirements.txt` (sinon ajouter)
- [ ] Vérifier que `semver` est dans `backend/requirements.txt` (utilisé par F04 ; sinon ajouter)
- [ ] F22 (test_eval_runner.py) effectivement réutilisable comme librairie
- [ ] 3 sources MVP existent en BDD (GCF Investment Framework, GCF Funding Proposal Template, BOAD Procédures Climat) ou créées dans le seed

## During implementation

- [ ] TDD strict : tests écrits avant impl, doivent FAIL initialement
- [ ] Commit après chaque task ou groupe logique
- [ ] Run pytest local après chaque modification de modèle ou nœud LangGraph
- [ ] Vérifier `state["active_skills"]` est bien snapshoté (test integration)
- [ ] Vérifier audit log F03 entries pour chaque mutation skill
- [ ] Anti-injection patterns testés sur 50 textes (50/50 attaques + benins)
- [ ] Test conformity `test_no_skill_mutation_tool` exécuté à chaque ajout de tool

## Post-implementation

- [ ] Run pytest complet — 0 régression sur ~935 tests existants
- [ ] Run `pytest tests/graph/test_skill_loader.py tests/graph/test_prompt_fusion.py tests/integration/admin/test_admin_skills_*.py` → tous verts
- [ ] Couverture `app/models/skill.py` >= 80 %
- [ ] Couverture `app/modules/skills/*` >= 80 %
- [ ] Couverture `app/graph/skill_loader.py` >= 90 %
- [ ] Couverture `app/graph/prompt_fusion.py` >= 90 %
- [ ] Couverture `app/core/prompt_injection_detector.py` >= 95 % (sécurité)
- [ ] 3 skills MVP seedées et `published` dans la BDD
- [ ] Test E2E publish gating échec (golden_examples failing) → 422 + skill reste draft
- [ ] Test E2E dossier GCF/BOAD → state["active_skills"] contient skill_dossier_gcf_via_boad
- [ ] Test E2E versioning : édition skill published → nouvelle version draft, ancienne intacte
- [ ] Token budget system prompt avec 2 skills chargées < 12k tokens
- [ ] Test conformity passe (aucun tool LLM mute Skills)

## Pre-PR

- [ ] Documentation `docs/skills-playbooks.md` complète (process créer/calibrer/publier/versionner)
- [ ] CLAUDE.md mis à jour (Recent Changes section)
- [ ] Frontend admin pages `/admin/skills/*` fonctionnelles, dark mode complet
- [ ] Composants `ToolWhitelistPicker`, `SourceMultiPicker`, `GoldenExamplesEditor` testés unitairement
- [ ] Composable `useAdminSkills.ts` typé strict
- [ ] Branche rebasée sur main, sans conflit
- [ ] Workflow CI `.github/workflows/ci.yml` ajouté avec path-filter (skill-eval job)

## PR review

- [ ] Code review (code-reviewer agent)
- [ ] Security review (validator anti-injection, endpoint admin protection)
- [ ] Tests E2E + skill eval verts en CI
- [ ] Pas de fichiers sensibles commités (.env, etc.)
- [ ] Gates CI tous verts (test conformity, eval gating, test complet)
- [ ] Revue 4-yeux : 2 reviewers minimum, dont 1 sécurité (impact sur prompt LLM)

## Merge criteria

- [ ] All checks green
- [ ] Reviewer approval (≥ 2 reviewers)
- [ ] Branch up-to-date with main
- [ ] No merge conflicts
- [ ] Documentation reviewed
- [ ] Migration Alembic testée up/down sur staging
- [ ] 3 skills MVP créées en staging et chargées par le loader (smoke test manuel)

## Anti-régression Skills (post-merge)

- [ ] 1 mois après merge : 0 incident lié à injection détectée tardivement
- [ ] 1 mois après merge : ≥ 5 skills additionnelles créées (preuve d'adoption admin)
- [ ] 3 mois après merge : ≥ 60 % des tours LLM ont `state["active_skills"] != []` (couverture skills active)
- [ ] 3 mois après merge : taux de matching tool sur golden_examples des skills published reste > 90 %
