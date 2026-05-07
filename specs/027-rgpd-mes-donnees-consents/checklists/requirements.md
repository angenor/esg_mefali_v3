# Specification Quality Checklist: F05 — RGPD : Page « Mes Données » + Consentements + Export/Suppression

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`
- Le spec mentionne intentionnellement les noms de tables (`consents`, `audit_log`, `accounts`) car ils sont des contraintes du projet imposées par les invariants F02/F03 documentés dans `.cc-orchestrator.md` — ces noms servent de contrat partagé entre features et ne sont pas considérés comme « implementation details » au sens SpecKit (équivalent du nommage de tables dans la spec F17/F08).
- Le format des endpoints REST (`GET /api/me/data/inventory`, etc.) est documenté car il sert de contrat partagé entre frontend et backend (équivalent F17/F08).
- 6 user stories prioritisées P1 (3) / P2 (2) / P3 (1), chacune indépendamment testable.
- 25 functional requirements unitairement testables.
- 10 success criteria mesurables et technology-agnostic.
- Edge cases couverts : volume export, double export, suppression cascade multi-utilisateur, annulation hors délai, cron interrompu, révocation post-traitement, politique v2, bypass `require_consent`, audit_log post-purge, attestation en cours, inscription refusant la politique.
