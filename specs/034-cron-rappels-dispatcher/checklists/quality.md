# Quality Checklist: F19 — Cron Dispatcher Rappels

**Created** : 2026-05-07
**Owner** : SpecKit Phase A

## Spec quality

- [x] User stories priorisées (P1 / P2 / P3)
- [x] Au moins 1 user story P1 indépendamment livrable (US1, US2, US3, US5, US6 → P1)
- [x] Acceptance scenarios Given/When/Then complets pour chaque US
- [x] Edge cases listés (≥ 9 cas)
- [x] Fonctional requirements numérotés FR-001 à FR-025 (25 FR)
- [x] Success criteria mesurables (SC-001 à SC-010, 10 SC)
- [x] Assumptions explicites (10+ assumptions)
- [x] Aucun [NEEDS CLARIFICATION] restant
- [x] Clarifications session documentée (15+ items)

## Plan quality

- [x] Technical context complet (langage, deps, storage, testing, target)
- [x] Project structure détaillée (backend + frontend + docs)
- [x] Phases logiques (Phase 0 research, Phase 1 design, Phase 2 tasks)
- [x] Risks & mitigations table (10+ risques)
- [x] Constitution check effectué
- [x] Acceptance gates listés

## Research quality

- [x] Décisions documentées avec alternatives (R1-R15)
- [x] Justifications mesurables
- [x] Patterns/code samples pour les décisions techniques clés
- [x] Compatibilité SQLite/PostgreSQL discutée

## Data model quality

- [x] Schéma table extension détaillé (3-4 colonnes nouvelles)
- [x] Indexes spécifiés avec predicates (UNIQUE PARTIAL)
- [x] Migration Alembic complète (upgrade + downgrade)
- [x] Modèle SQLAlchemy mis à jour
- [x] Format dedup_key documenté par type
- [x] Audit log F03 events tabulés
- [x] Volumétrie estimée

## Quickstart quality

- [x] Prérequis listés
- [x] Démarrage local documenté (single + workers)
- [x] Tests E2E manuels documentés (assessment + silence radio)
- [x] Idempotence test documenté
- [x] Inspect audit log F03 documenté
- [x] Frontend NotificationCenter test documenté
- [x] Migration / rollback documentés

## Contracts quality

- [x] JSON Schema valide pour `reminder_dispatched_event`
- [x] REST endpoints documentés (request/response/errors/test cases)
- [x] APScheduler jobs config tabulé (10 jobs)
- [x] Implementation patterns code samples

## Tasks quality (à valider après /speckit.tasks)

- [ ] Tasks numérotées avec préfixe T0XX
- [ ] Mapping user story → tasks
- [ ] TDD obligatoire (test avant impl)
- [ ] Couverture ≥ 80 % planifiée
- [ ] Tests E2E inclus
- [ ] Audit conformity tests inclus

## Conformité projet

- [x] Convention nommage : feature branch `feat/F19-cron-rappels-dispatcher`
- [x] Spec number 034 (cohérent avec le séquentiel)
- [x] Migration `down_revision="033_create_skills"`
- [x] Pas de modification du frontend en dehors des nouveaux composants/dead code activé
- [x] Pas de dépendance externe nouvelle (sauf `apscheduler`)
- [x] Dark mode obligatoire pour les nouveaux composants frontend
- [x] F02 multi-tenant (account_id) sur tous les nouveaux flows
- [x] F03 audit log sur toute mutation cron
- [x] LLM ne mute pas les reminders (pas de tool LangChain `create_reminder`)
- [x] Tests SQLite-compatible pour CI rapide

## Couverture FR (vérifié dans analyze.md)

- [x] FR-001 → FR-025 (25 FR) traités dans tasks.md

## Couverture User Stories → Tasks (vérifié dans analyze.md)

- [ ] US1 (dispatcher SSE)
- [ ] US2 (auto-création reminders)
- [ ] US3 (APScheduler lifespan)
- [ ] US4 (Frontend NotificationCenter)
- [ ] US5 (Migration 034 + audit log)
- [ ] US6 (E2E tests)
