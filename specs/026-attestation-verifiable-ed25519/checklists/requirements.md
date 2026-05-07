# Specification Quality Checklist: F08 — Attestation Vérifiable Ed25519

**Purpose** : valider la complétude et la qualité de la spec avant le passage à la planification.
**Created** : 2026-05-07
**Feature** : [spec.md](../spec.md)

## Content Quality

- [x] Aucun détail d'implémentation prématuré dans la section « User Scenarios » (les choix techniques `cryptography>=41.0`, `segno>=1.5` sont confinés à la section Clarifications, comme attendu par la fiche F08 qui les recommande explicitement)
- [x] Centré sur la valeur utilisateur (PME émettrice, fund officer vérificateur, admin de modération) et le besoin métier (différenciateur produit n°2 — vérification hors-plateforme)
- [x] Lisible par un stakeholder non technique (les sections Clarifications et FR-001..FR-020 sont plus techniques, mais explicites en français)
- [x] Toutes les sections obligatoires renseignées : User Scenarios (6 stories priorisées P1/P2/P3), Edge Cases (9 cas), Functional Requirements (FR-001..FR-020), Key Entities (3), Success Criteria (SC-001..SC-008), Assumptions (12)

## Requirement Completeness

- [x] Aucun marqueur `[NEEDS CLARIFICATION]` restant — les 5 questions ont été résolues en mode autonomie totale
- [x] Toutes les exigences sont testables et non ambiguës (FR-001..FR-020 sont formulées sous forme « Le système DOIT … »)
- [x] Critères de succès mesurables (8 SC avec métriques chiffrées : latence < 2 s p95, couverture ≥ 85 %, rate limiting > 95 %, etc.)
- [x] Critères de succès agnostiques de la technologie (pas de mention `cryptography`, `segno`, `Nuxt`, `Pydantic` dans la section Success Criteria — les noms apparaissent dans Clarifications/FR par nécessité technique mais pas dans SC)
- [x] Tous les scénarios d'acceptation définis (24 scénarios distribués sur les 6 user stories)
- [x] Cas limites identifiés (9 edge cases : altération PDF, malveillance utilisateur, énumération, concurrence, multi-tenant, etc.)
- [x] Périmètre clairement délimité (hors-scope explicites : rotation auto des clés, blockchain, wallet PME, watermark, preview HTML)
- [x] Dépendances et hypothèses identifiées (12 assumptions, 4 dépendances de feature : F01, F02, F03, F04)

## Feature Readiness

- [x] Toutes les exigences fonctionnelles ont des critères d'acceptation clairs (chaque FR-XXX est traçable vers un ou plusieurs scénarios d'acceptation des US)
- [x] Les user scenarios couvrent les flux primaires (génération par UI, scan par fund officer, révocation PME, révocation admin, génération par LLM, expiration auto)
- [x] La feature satisfait les outcomes mesurables définis dans Success Criteria (chaque SC est testable)
- [x] Aucun détail d'implémentation ne fuit dans la spec en dehors des sections Clarifications et FR (qui sont par nature semi-techniques)

## Notes

- Cette feature dépend des fondations F01 (sourçage des chiffres LLM), F02 (multi-tenant + RLS + rôle Admin), F03 (audit log Auditable), F04 (Money typed pour scores). Les 4 sont mergées sur `main` au moment de la rédaction (HEAD = `9b2800e`).
- Les 5 décisions de clarification ont été tracées avec rationale et alignées sur les invariants `.cc-orchestrator.md` et la fiche F08.
- Les hors-scope sont explicites pour cadrer le périmètre MVP (ne pas dériver vers blockchain/HSM/preview).
- La couverture de test cible ≥ 85 % sur les modules cryptographiques (signing, qr, service) reflète l'importance critique de ces couches (la fiche F08 explicite ce seuil).
- Les 5 scénarios E2E Playwright décrits dans tasks.md couvrent l'intégralité des cas d'acceptation P1 + 2 cas P2 (admin revoke + LLM tool).
