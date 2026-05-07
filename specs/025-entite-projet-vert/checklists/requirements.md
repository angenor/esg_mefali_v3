# Quality Checklist — F06 Entité Projet Vert

## Spec quality

- [x] Toutes les ambiguïtés majeures sont clarifiées dans la section Clarifications (5 questions répondues lors de la session 2026-05-07).
- [x] Les 4 user stories sont indépendamment testables et priorisées (P1 P1 P2 P2).
- [x] Chaque user story expose un test indépendant exécutable (« Independent Test »).
- [x] Les FR sont mesurables et numérotées (FR-001 à FR-036).
- [x] Les Success Criteria sont mesurables (SC-001 à SC-010, métriques quantifiées).
- [x] Aucun jargon non expliqué (RLS, Money typed, source_of_change, audit log, multi-tenant tous clairs).
- [x] Le périmètre de la feature est borné : F06 ne touche pas à F09 (matching projet-offre), F11 (PostGIS / show_map), F18 (déjà déployé).

## Constitution & invariants

- [x] **I. Francophone-First** : libellés UI français, accents (« Créé », « Hérité », « Bénéficiaires »).
- [x] **II. Architecture modulaire** : zones interdites épargnées (system.py, graph.py, deps.py, main.py minimal).
- [x] **III. Conversation-driven UX** : tools LangChain symétriques aux endpoints API ; `ask_interactive_question` pour confirmer la création depuis le chat.
- [x] **IV. Test-First** : plan TDD ; couverture ≥ 80 %.
- [x] **V. Sécurité** : aucun secret hardcodé ; Pydantic strict ; RLS héritée F02.
- [x] **VI. Inclusivité & accessibilité** : ARIA roles, dark mode, keyboard navigation.
- [x] **VII. Simplicité** : pas de Redis/Celery/PostGIS introduits ; JSONB simple pour `objective_env`.
- [x] Invariant n°1 (sourçage F01) : validator `source_required.py` appliqué sur `create_project`.
- [x] Invariant n°2 (multi-tenant F02) : `account_id NOT NULL` ; RLS ENABLE+FORCE + 2 policies ; tests cross-tenant.
- [x] Invariant n°3 (audit log F03) : `Project` hérite `Auditable` ; tests source_of_change.
- [x] Invariant n°4 (Money typed F04) : paire `target_amount_amount` + `target_amount_currency` ; CHECK applicatif.
- [x] Invariant n°7 (admin only catalogue) : F06 ne touche pas le catalogue.
- [x] Invariant n°8 (dark mode) : 7 composants Vue avec variantes `dark:`.
- [x] Invariant n°9 (réutilisabilité) : audit pré-implémentation OK ; réutilise `<MoneyDisplay>`, `<SourceLink>`, `useFocusTrap`.
- [x] Invariant n°10 (français accents) : tous libellés conformes.
- [x] Invariant n°11 (E2E exécutables) : Playwright `F06-entite-projet-vert.spec.ts` 4 scénarios.
- [x] Invariant n°12 (couverture ≥ 80 %) : pytest --cov sur `app/modules/projects/`, `app/graph/tools/project_tools.py`, `app/models/project*.py`.

## Migration & data

- [x] Migration Alembic réversible (up/down/up) testée.
- [x] Down_revision = `024_carbone_mix_uemoa` (cohérent avec l'état actuel de `main`).
- [x] Backfill idempotent (`WHERE project_id IS NULL`).
- [x] CHECK contraintes : `target_amount_pair_chk`, `status_chk`, `maturity_chk`, etc.
- [x] Indexes composites prévus pour les requêtes principales.
- [x] RLS policies créées pour `projects` et `project_documents`.
- [x] Compatibilité SQLite (tests) via `JSONType` et fallback Python loop pour le backfill.

## API & tools

- [x] 7 endpoints REST documentés (`contracts/project-api.md`).
- [x] 7 tools LangChain documentés (`contracts/project-tools-langchain.md`).
- [x] Tool selector : `MAX_TOOLS_PER_TURN=14` respecté.
- [x] `delete_project` retourne payload exploitable par `ask_interactive_question`.
- [x] `duplicate_project` : status forcé `draft`, project_documents non copiés.

## Frontend

- [x] 4 pages prévues (profile/company, projects/index, projects/new, projects/[id], projects/[id]/duplicate).
- [x] 7 composants Vue prévus (sans `ProjectMap` différé F11).
- [x] Composable `useProjects.ts` + store Pinia `projects.ts`.
- [x] Lien sidebar « Mes Projets » avec badge count.
- [x] Réutilisation `<MoneyDisplay>` F04, `<SourceLink>` F01.

## Tests

- [x] Tests unit : modèle, schemas, tools.
- [x] Tests integration : CRUD, duplicate, delete guard, RLS, audit log, tools.
- [x] Test migration : up/down/up + backfill idempotent.
- [x] Tests Vitest : 7 composants + composable + store.
- [x] Test E2E Playwright : 4 scénarios couvrant US1-US4.

## Performance

- [x] Cibles définies : list < 80 ms p95, create < 100 ms, duplicate < 150 ms, migration < 30 s.
- [x] Indexes alignés sur les requêtes principales.

## Sécurité

- [x] Validation Pydantic v2 stricte sur tous les payloads.
- [x] Aucune concaténation SQL ; ORM uniquement.
- [x] RLS PostgreSQL F02 héritée et testée.
- [x] Logs structurés sur opérations sensibles (`project_force_deleted`).

## Documentation

- [x] `spec.md` complet et clarifié.
- [x] `plan.md` avec gates constitutionnels passés.
- [x] `research.md` avec 11 décisions tracées.
- [x] `data-model.md` avec schémas SQL, Pydantic, mapping backfill.
- [x] `contracts/project-api.md` avec exemples curl et codes HTTP.
- [x] `contracts/project-tools-langchain.md` avec exemples invocation LLM.
- [x] `quickstart.md` avec walkthrough complet.
- [x] `tasks.md` ordonné par dépendance et user story.
