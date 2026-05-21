# Specification Quality Checklist: Matching financement vert centré projet

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — la spec garde les noms de fondations transverses (F01, F02, F04, F06, F11, F14, F23) pour ancrage métier mais ne prescrit pas l'implémentation ; les noms d'endpoints sont indicatifs (« exposera un endpoint »).
- [x] Focused on user value and business needs — 5 user stories métier prioritisées, cas central PME informelle + projet vert documenté.
- [x] Written for non-technical stakeholders — chaque story est lisible en langage métier.
- [x] All mandatory sections completed — User Scenarios, Requirements, Success Criteria, Assumptions tous remplis.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — résolus en session 2026-05-21 : Q1 = (C) double score séparé, Q2 = (A) enrichir `offer_matches` F14, Q3 = (A) 5 champs candidats. Section « Clarifications » consigne les décisions.
- [x] Requirements are testable and unambiguous — chaque FR commence par « Le système DOIT » et est testable.
- [x] Success criteria are measurable — SC-001 à SC-010 ont tous une métrique chiffrée ou un booléen vérifiable.
- [x] Success criteria are technology-agnostic — SC-003 mentionne « < 2 s » sans préciser de stack, SC-008 mentionne « ≥ 80 % » sans préciser l'outil, SC-006 cite Alembic mais c'est une dépendance projet documentée dans CLAUDE.md.
- [x] All acceptance scenarios are defined — chaque user story a des scénarios Given/When/Then numérotés.
- [x] Edge cases are identified — 8 edge cases listés (draft, cancelled, devises, source non vérifiée, multi-tenant, RLS, migration, cascade recalcul).
- [x] Scope is clearly bounded — Hors-scope explicite avec 9 items.
- [x] Dependencies and assumptions identified — section Assumptions de 10 items + section Dépendances avec 12 fondations + 5 risques.

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — FR-001..FR-020 mappent vers les Acceptance Scenarios des user stories.
- [x] User scenarios cover primary flows — story P1 (PME informelle), P1 (chat lifecycle), P2 (filtrage non vert), P2 (double score), P3 (UI complémentaire).
- [x] Feature meets measurable outcomes defined in Success Criteria — chaque SC est validable par un test ou une métrique.
- [x] No implementation details leak into specification — pas de SQL DDL, pas de code Python, pas d'API REST schemas détaillés.

## Notes

- ✅ Tous les items de la checklist sont validés — la spec est prête pour `/speckit.clarify` (si l'équipe veut retravailler les zones grises restantes : cas projet draft, recalcul automatique) ou `/speckit.plan` directement.
- Les 3 clarifications critiques ont été résolues en session 2026-05-21 (cf. section « Clarifications » de spec.md).
- Les 2 autres zones grises du brief (cas projet draft, recalcul automatique) ont reçu des défauts raisonnables documentés en Assumptions (matching dès draft, recalcul auto + on-demand).
- La spec hérite explicitement de F14 (commit `c9204c8`) — elle enrichit la logique projet-centric sans casser le contrat existant. La cohabitation est explicite pour 2 sprints minimum.
