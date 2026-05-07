# Specification Quality Checklist: F07 — Entité Offre = Couple Fonds × Intermédiaire

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — sections « Functional Requirements » utilisent des termes neutres (« le système DOIT ») ; les détails d'implémentation (FastAPI, SQLAlchemy, Vue) sont mentionnés uniquement dans Assumptions/Dependencies pour cadrer le contexte projet, ce qui est acceptable selon les conventions ESG Mefali (specs internes).
- [x] Focused on user value and business needs — toutes les User Stories partent d'une PME ou d'un admin et explicitent la valeur business.
- [x] Written for non-technical stakeholders — sections User Scenarios + Success Criteria + Assumptions sont lisibles sans connaissances techniques.
- [x] All mandatory sections completed — User Scenarios, Requirements, Success Criteria, Assumptions, Dependencies présents.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — toutes les ambiguïtés ont été résolues dans la section Clarifications (6 décisions documentées).
- [x] Requirements are testable and unambiguous — chaque FR-XXX cite un comportement vérifiable (ex : « Le calculator DOIT lever 422 si la paire (fund_id, intermediary_id) n'existe pas... »).
- [x] Success criteria are measurable — chaque SC-XXX inclut un seuil quantitatif (10s, 500ms p95, 0 fuite, 80% couverture, 4 tests E2E).
- [x] Success criteria are technology-agnostic — les SC parlent de comportement utilisateur ou de propriétés vérifiables, pas de framework.
- [x] All acceptance scenarios are defined — 6 user stories (US1 à US6) avec entre 3 et 6 scenarios Given-When-Then chacune.
- [x] Edge cases are identified — section dédiée avec 7 cas limites documentés (suppression fonds, draft state, source non-verified, paire inexistante, doublons, frais > min_amount, application en cours sur offre désactivée).
- [x] Scope is clearly bounded — section Hors-scope dans le brief original, et la spec liste explicitement les éléments inclus (table offers, calculator, API, tools, frontend pages/composants) et exclut Marketplace tiers, A/B testing, versionning fin par section.
- [x] Dependencies and assumptions identified — sections Dependencies (5 features) et Assumptions (10 items).

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — chaque FR-XXX est rattachable à une US-Y avec Acceptance Scenarios.
- [x] User scenarios cover primary flows — US1 (PME compare offres), US2 (admin crée offre), US3 (migration), US4 (calcul effectif), US5 (cron expiration), US6 (multi-tenant).
- [x] Feature meets measurable outcomes defined in Success Criteria — chaque SC est traceable à une US.
- [x] No implementation details leak into specification — les FR utilisent des termes business ; les détails d'implémentation (chemins de fichiers, FastAPI, SQLAlchemy) restent dans plan.md.

## Notes

- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`
- Aucune itération nécessaire : tous les items passent à la première validation.
- Les 6 clarifications enregistrées couvrent les ambiguïtés critiques (modèle Offre obligatoire vs direct, mode hybride feature flag, scope backfill, déduplication documents, langue par défaut, cron auto-désactivation).
