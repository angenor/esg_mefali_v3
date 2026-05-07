# Specification Quality Checklist: F17 — Carbone Mix UEMOA + Facteurs ADEME/IPCC Sourcés + Catégorie Achats

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) outside Key Entities/Assumptions where they reference existing F01 catalogue tables
- [x] Focused on user value and business needs (4 user stories prioritisées P1/P1/P2/P3)
- [x] Written for non-technical stakeholders (jargon limité ; références techniques cantonnées dans Assumptions/Hypothèses)
- [x] All mandatory sections completed (User Scenarios, Requirements, Success Criteria)

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous (FR-001 à FR-023)
- [x] Success criteria are measurable (SC-001 à SC-009 chiffrés)
- [x] Success criteria are technology-agnostic (focus sur résultats utilisateur, pas sur stack)
- [x] All acceptance scenarios are defined (4 par US1, 4 par US2, 4 par US3, 3 par US4)
- [x] Edge cases are identified (8 cas énumérés)
- [x] Scope is clearly bounded (Hors-scope HS1-HS6 explicites)
- [x] Dependencies and assumptions identified (A1-A8, H1-H9, R1-R4)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria (FR ↔ SC ↔ acceptance scenarios alignés)
- [x] User scenarios cover primary flows (calcul carbone pays-spécifique, sourçage cliquable, catégorie Achats, plan de réduction sourcé)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification (pas de mention de SQLAlchemy/Pydantic/Vue ailleurs que dans Assumptions techniques)

## Notes

- Tous les critères passent à l'itération 1.
- Décisions de scope auto-résolues par /speckit.specify selon les invariants ESG Mefali (sourçage F01 obligatoire, multi-tenant F02, dark mode, français avec accents).
- Numérotation SpecKit `021-carbone-mix-uemoa-source` susceptible de collision avec F12/F03/F04 développés en parallèle ; l'orchestrateur résoudra avant Phase B.
