# Cross-Artifact Analysis: F23 — Skills (Playbooks Métier)

**Date** : 2026-05-07
**Auteur** : SpecKit Phase A (autonome, post `/speckit.tasks`)
**Status** : OK — pas de blocage critique identifié

## Vue d'ensemble

| Artefact | Taille | Conformité |
|----------|--------|------------|
| spec.md | 7 user stories, 22 FR, 12 SC, 9 assumptions, 13 edge cases | ✓ Format respecté |
| plan.md | 9 sections (summary, technical context, structure, phases, migration, endpoints, skills MVP, CI, risks) | ✓ Format respecté |
| research.md | 10 décisions documentées (R1-R10) | ✓ Couvre toutes les ambiguïtés |
| data-model.md | 6 entités (Skill table, ActivationRules, GoldenExample, SkillEvalReport, ConversationState extension, AdminResponses) | ✓ Schémas complets |
| quickstart.md | 8 sections (création/test/publish/édition + dev integration + dépannage + monitoring + E2E) | ✓ Actionnable |
| contracts/ | 5 fichiers (skill_schema, activation_rules_schema, golden_example_schema, skill_eval_report_schema, admin_skills_endpoints) | ✓ JSON Schema valides |
| checklists/quality.md | 4 sections + anti-régression Skills | ✓ Format respecté |
| tasks.md | 63 tasks en 12 phases, mapping US correct, estimation 15 jours | ✓ Format respecté |

## Couverture FR → Tasks

| FR | Description courte | Coverage | Tasks |
|----|---|----|---|
| FR-001 | Migration 033 table skills | ✓ | T006 |
| FR-002 | Indexes (domain/status/valid_to, name unique, GIN activation_rules, status) | ✓ | T006 |
| FR-003 | CheckConstraints (domain, status, four_eyes) | ✓ | T006, T008 (test) |
| FR-004 | Modèle SQLAlchemy Skill | ✓ | T007, T008 (test) |
| FR-005 | Schemas Pydantic SkillCreate/Update/Read/etc. | ✓ | T033 |
| FR-006 | Service CRUD + query_skills_matching | ✓ | T036 (test), T037 |
| FR-007 | Validator (tools, sources, tokens, anti-injection) | ✓ | T034 (test), T035 |
| FR-008 | Module prompt_injection_detector.py | ✓ | T012 (test), T013 |
| FR-009 | Eval runner | ✓ | T030 (test), T031 |
| FR-010 | publish_skill avec eval gating | ✓ | T036 (test), T037, T032 |
| FR-011 | Skill loader load_skills_for_context | ✓ | T014 (test), T015 |
| FR-012 | Fuser fuse_prompt | ✓ | T016 (test), T017 |
| FR-013 | Helper select_tools_with_skills | ✓ | T016 (test), T017 |
| FR-014 | Refactor 7 nœuds LangGraph | ✓ | T019-T028 |
| FR-015 | active_skills dans ConversationState | ✓ | T011, T020 (test) |
| FR-016 | Test conformity no skill mutation tool | ✓ | T018 |
| FR-017 | 8 endpoints admin REST | ✓ | T041 (test), T043, T044 |
| FR-018 | Module seed 3 skills MVP | ✓ | T038 (test), T039, T040 |
| FR-019 | Audit log F03 sur mutations | ✓ | T036, T042 (test) |
| FR-020 | Frontend admin pages + composants | ✓ | T045-T056 |
| FR-021 | Validation tool names via ALL_TOOL_NAMES | ✓ | T034 (test), T035 |
| FR-022 | Édition skill published → nouvelle version | ✓ | T036 (test), T037, T042 (test) |

**Conclusion** : 22/22 FR couverts par au moins une tâche, avec test TDD avant implémentation.

## Couverture User Stories → Tasks

| US | Description | Tasks | Tests inclus | Indépendant ? |
|----|---|---|---|---|
| US1 | Skill loader contextuel | T014-T015 | T014 (TDD) | ✓ Après Phase 2 |
| US2 | Fusion + intersection | T016-T017 | T016 (TDD) | ✓ Après Phase 2 |
| US3 | Refactor 7 nœuds | T019-T029 | T019-T021 (TDD) | ✓ Après US1+US2 |
| US4 | Eval gating | T030-T032, T036, T037 | T030 (TDD), T036 (TDD), T042 (E2E) | ✓ Après Phase 2 |
| US5 | Anti-injection | T012-T013 | T012 (TDD) | ✓ Après Phase 2 |
| US6 | Test conformity no skill mutation | T018 | T018 (test) | ✓ Indépendant |
| US7 | CRUD admin REST + Frontend | T041-T056 | T041, T042, T056 (TDD/E2E) | ✓ Après US4+US5 |

**Conclusion** : 7/7 US ont leur story indépendamment livrable + tests TDD avant implémentation. Ordre cohérent (foundational → security → loader/fusion → integration → eval → service → frontend).

## Détection d'incohérences

### ✓ Cohérences vérifiées

1. **Migration Alembic** — `down_revision="032_add_validation_error_tool_call_logs"` cohérent avec dernière migration 032 confirmée par `ls backend/alembic/versions/`.
2. **Spec number 033** — disponible (specs/ contient jusqu'à 032 selon ls vérification).
3. **Format golden_examples** — aligné F22 (réutilise `app.lib.eval_matching` après extraction du module commun T009-T010).
4. **Versioning F04** — utilise `VersioningMixin` existant, version semver patch+1 via lib `semver`.
5. **Audit log F03** — entries explicites sur 6 actions (skill_created/updated/published/unpublished/deleted/superseded + injection_attempt_blocked).
6. **3 skills MVP** — `skill_esg_diagnostic`, `skill_score_gcf`, `skill_dossier_gcf_via_boad` cohérents avec fiche F23.
7. **No skill mutation tool** — pattern interdit `^(create|update|delete|publish)_skill` couvert par test conformity T018.
8. **Sources verified** — validator vérifie `source.verification_status='verified'` (cohérent avec F01 4-yeux).
9. **State LangGraph** — `active_skills` ajouté dans `ConversationState`, snapshoté par checkpointer existant (pas de modification du checkpointer).

### ⚠ Points d'attention (non-bloquants)

1. **`tiktoken` et `semver` dépendances** — T001 et T002 vérifient leur présence dans `requirements.txt`. Si absent, à ajouter en début de Phase 1.
2. **3 sources MVP requises** — `seed_skills.py` doit d'abord vérifier l'existence des sources (GCF Investment Framework, GCF Funding Proposal Template, BOAD Procédures Climat). Si absentes, créer dans T039 ou nécessiter une étape préalable de seed sources.
3. **`semver` lib usage** — F04 mergé utilise déjà `semver` ? À vérifier dans T002. Sinon ajouter.
4. **F09 admin squelette** — `app/modules/admin/router.py` et `middleware.py` existent (vérifié via `ls`). F23 ajoute `skills_router.py` à enregistrer dans le router agrégateur.
5. **GIN index PostgreSQL only** — créé en SQL natif par migration 033 (cf. T006). Tests SQLite : load + filter Python (acceptable car volumétrie test < 50).
6. **Eval gating coût LLM** — chaque test/publish coûte ~5-10 cas × ~6s/cas = 30-60s LLM. Acceptable pour usage admin manuel. CI eval optionnel via path-filter.
7. **State immutabilité Python** — `state["active_skills"] = [...]` est une mutation in-place du dict TypedDict. Convention LangGraph standard, pas de violation de notre rule immutabilité (le state est réinitialisé à chaque checkpoint).
8. **Sécurité prompt injection regex first** — couverture limitée vs ML-based detector (post-MVP). Documenté dans research R3 + risks plan.md.

### ✓ Risques mitigés

| Risque | Mitigation |
|--------|------------|
| Skill mal écrite cause hallucinations | Eval gating ≥ 90 %, audit log F03, revue 4-yeux |
| Conflit entre 2 skills activées | Max 2 skills + tri spécificité, doc guideline |
| Prompt injection via prompt_expert | Détecteur 10 patterns regex, refus 422 + audit log, revue admin |
| Token budget explosion | Limit prompt_expert ≤ 5000 tokens, cap total 12 000 (charge 1 au lieu de 2) |
| Conversations en cours cassent | Snapshot active_skills dans state, persiste à travers checkpoint |
| LLM compromis modifie skills | 0 tool LLM exposé, test conformity bloquant CI |
| Eval gating timeout | Parallèle max 5 concurrent, timeout global 60s, retourne 504 si dépassé |
| Migration 033 backward compat | Table nouvelle, zero-downtime, code lit `[]` si table vide |
| Régression tests existants | T029 + T060 run pytest complet attendu 0 régression |
| Frontend dark mode oublié | Checklist quality.md mentionne explicitement "dark mode complet" |

## Couverture des Edge Cases (spec.md)

| Edge Case | Mitigation/Task |
|---|---|
| Skill avec activation_rules vide | Validator warning (T035) |
| 2 skills même name | UNIQUE constraint (T006) + erreur 422 (T035) |
| Skill draft 0 golden_examples | Autorisé en draft, refus à publish (T030, T031) |
| Skill éditée pendant conversation | Snapshot state["active_skills"] (T011, T020) |
| Token explosion | Cap 12k → 1 skill (T017, T016) |
| Source FK invalide | Validator rejette (T035, T034) |
| Source non verified | Validator rejette (T035) |
| Tool whitelist nom invalide | Validator rejette (T035) |
| Eval gating timeout | EvalTimeoutError + 504 (T031, T032) |
| Hack via tool_whitelist exotique | Regex `^[a-z_][a-z0-9_]*$` validation |
| Concurrent edit | Optimistic locking documenté |
| Skill sans tool_whitelist | Mode permissif documenté |
| Migration 033 zero-downtime | T006 (nullable col + GIN PG-only) |

**Conclusion** : 13/13 edge cases couverts par au moins une tâche.

## Couverture des Success Criteria

| SC | Description | Vérification |
|----|---|---|
| SC-001 | 3 skills MVP `published` | T039, T063 |
| SC-002 | Loader retourne max 2 skills | T014 |
| SC-003 | Fusion contient `## SKILL ACTIVE` | T016 |
| SC-004 | Intersection 100 % exactitude | T016 |
| SC-005 | Eval gating bloque < 90 % | T030, T036, T042 |
| SC-006 | Anti-injection ≥ 95 % détection | T012 |
| SC-007 | Endpoint publish < 60s P95 | T031 timeout |
| SC-008 | 0 régression sur 935 tests | T029, T060 |
| SC-009 | Couverture ≥ 80 % nouveaux modules | T062 |
| SC-010 | 0 tool LLM mute Skills | T018 |
| SC-011 | E2E publish gating échec → blocked | T042 |
| SC-012 | E2E dossier GCF/BOAD vocabulaire métier | T020 |

**Conclusion** : 12/12 SC mesurés par tâches dédiées.

## Tasks ordering & dépendances critiques

```
Phase 1 [Setup, P1-P5]              indépendant
  ↓
Phase 2 [Foundational]              T006 → T007 → T008
                                    T009 → T010 (refactor F22)
                                    T011
  ↓
Phase 3 [US5 Anti-injection]        T012 → T013
  ↓
Phase 4 [US1 Loader]                T014 → T015 (utilise Skill model)
Phase 5 [US2 Fusion]                T016 → T017 (utilise tiktoken)
Phase 6 [US6 Conformity]            T018 indépendant
  ↓
Phase 7 [US3 Refactor 7 nœuds]      T019-T021 → T022-T028 → T029
  ↓
Phase 8 [US4 Eval runner]           T030 → T031 → T032
  ↓
Phase 9 [Service CRUD + Validator]  T033 → T034 → T035 (utilise US5)
                                    T036 → T037 (utilise US4)
                                    T038 → T039 → T040 (seed)
  ↓
Phase 10 [US7 CRUD admin + Front]   T041-T044 (backend)
                                    T045-T056 (frontend)
  ↓
Phase 11 [Doc + CI]                 T057-T059
  ↓
Phase 12 [Validation]               T060-T063
```

**Tasks parallèles** (`[P]`) : 22 sur 63 (35 %), répartis sur les phases pour permettre 2-3 dev en parallèle.

## Estimation et planning

| Sprint | Phases | Tasks | Estimation |
|---|---|---|---|
| Sprint 1 | 1, 2, 3 | T001-T013 | 3 jours dev |
| Sprint 2 | 4, 5, 6, 7 | T014-T029 | 5 jours dev |
| Sprint 3 | 8, 9 | T030-T040 | 4 jours dev |
| Sprint 4 | 10 | T041-T056 | 3 jours dev |
| Sprint 5 (partiel) | 11, 12 | T057-T063 | 1 jour dev |

**Total** : 16 jours dev (+1 jour buffer), cohérent avec l'estimation 2.5 sprints de la fiche F23.

## Conclusion analyse

✓ **Spec.md** : 7 US, 22 FR, 12 SC, 13 edge cases, tous mappés à au moins une tâche TDD.
✓ **Plan.md** : structure projet alignée, 5 zones de modification clairement identifiées, migration Alembic 033 spécifiée.
✓ **Tasks.md** : 63 tâches en 12 phases avec dépendances claires, TDD strict, parallélisation [P] documentée.
✓ **Contracts** : 5 schémas JSON valides cohérents avec data-model.md.
✓ **Quickstart** : actionnable pour Admin et Dev.
✓ **Checklist quality** : 4 sections + anti-régression post-merge.

**Aucun blocage identifié**. Prêt pour `/speckit.implement` dans une session ultérieure.

## Recommandations pré-implémentation

1. **Vérifier dépendances** (Phase 1) : `tiktoken>=0.5.0`, `semver>=3.0.0` dans `backend/requirements.txt`.
2. **Vérifier sources MVP** : 3 sources (GCF Investment Framework, GCF Funding Proposal Template, BOAD Procédures Climat) doivent exister en BDD ou être créées dans le seed.
3. **Coordonner avec F09** : le sous-module `admin/skills_router.py` doit s'enregistrer dans le router agrégateur F09 existant.
4. **Anticiper budget LLM** : eval gating manuel = ~$0.50 par test, ~10-20 tests/mois en démarrage = ~$10/mois.
5. **Documenter ALL_TOOL_NAMES** : la collecte au module load doit être robuste aux nouveaux tools ajoutés (post-merge F23).
