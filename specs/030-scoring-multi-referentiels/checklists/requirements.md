# Specification Quality Checklist: F13 — Scoring ESG Multi-Référentiels

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *Note : on conserve les noms d'entités projet (Offer, EsgAssessment, ReferentialScore, etc.) pour la traçabilité avec F01/F04/F05/F07/F12, mais aucun choix de stack ou API spécifique n'est imposé dans la couche fonctionnelle*
- [x] Focused on user value and business needs — 7 user stories priorisées P1/P2/P3 ancrées sur Aïssa (PME agroalimentaire)
- [x] Written for non-technical stakeholders — chaque story raconte un parcours métier en français
- [x] All mandatory sections completed — User Scenarios, Requirements, Success Criteria, Assumptions, Dependencies

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 5 questions de clarification décidées en autonomie (recalcul async, backfill complet, badge coverage, version semver gérée par admin, fallback Mefali)
- [x] Requirements are testable and unambiguous — 65 FR (FR-001 à FR-065), chaque FR a un acceptance scenario associé via les user stories
- [x] Success criteria are measurable — 12 SC chiffrés (latences, %, couverture tests, etc.)
- [x] Success criteria are technology-agnostic (no implementation details) — vérifié, formulés en termes de latence, %, comportement utilisateur
- [x] All acceptance scenarios are defined — 7 user stories × 4-5 scenarios chacune = 30+ scénarios Given/When/Then
- [x] Edge cases are identified — 8 edge cases listés (référentiel désactivé, coverage 0, indicateurs orphelins, recalcul partiel, etc.)
- [x] Scope is clearly bounded — section Hors-scope explicite (référentiels custom PME, scores composites, recommandations IA priorisées par référentiel, alertes delta > 10 points, cohort comparison)
- [x] Dependencies and assumptions identified — section Dependencies (F01, F02, F03, F04, F05, F06, F07, F11, F12) et section Assumptions (13 hypothèses)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — chaque FR est testable via au moins un acceptance scenario
- [x] User scenarios cover primary flows — 3 P1 (sélecteur, dual view, PDF multi-réf), 3 P2 (recalcul async, versioning, tools LangChain), 1 P3 (multi-tenant)
- [x] Feature meets measurable outcomes defined in Success Criteria — chaque SC est lié à au moins une user story
- [x] No implementation details leak into specification — la section Requirements parle d'entités et de comportements, pas d'implémentation technique (le `plan.md` traitera l'implémentation)

## Notes

- 5 questions de clarification ont été tranchées en autonomie selon les invariants projet (multi-tenant strict, sourçage F01, versioning F04 semver) et la stack imposée (FastAPI BackgroundTasks MVP, asyncpg, asyncio.gather).
- Le scope MVP cible 5 référentiels (Mefali + GCF + IFC PS + BOAD ESS + GRI 2021) ; ODD reporté à post-MVP via F09.
- La rétrocompatibilité avec F06 (PDF mono-référentiel) est garantie par les valeurs default (`referentials=["mefali"]`) sur l'endpoint `POST /api/reports/esg/{id}/generate`.
- Le pattern « 1 saisie = N scores » repose sur la table `referential_indicators` (F01) qui lie chaque indicateur à plusieurs référentiels — sans cette structure F01, la promesse de F13 ne peut pas exister.
- Tests E2E Playwright explicitement listés dans `frontend/tests/e2e/F13-scoring-multi-referentiels.spec.ts` (3 scénarios couvrant les 3 user stories P1).

Toutes les conditions sont satisfaites — `spec.md` est prêt pour `/speckit.clarify` (sans questions ouvertes) puis `/speckit.plan`.
