# Specification Quality Checklist: Évaluation ESG-projet (extension F05 au mode projet)

**Purpose** : valider la complétude et la qualité de la spécification avant de passer à `/speckit.clarify` puis `/speckit.plan`.
**Created** : 2026-05-21
**Feature** : [spec.md](../spec.md)

---

## Content Quality

- [x] Focused on user value and business needs — 5 user stories priorisées P1/P2/P3 livrent un MVP incrémental autour de la valeur métier (PME informelle évaluant son projet pour un bailleur vert)
- [x] Written for non-technical stakeholders — sections « Contexte métier », « Objectif », « User Scenarios », « Success Criteria » consommables sans bagage technique
- [x] All mandatory sections completed — Contexte, Objectif, Clarifications (placeholder), User Scenarios & Testing, Requirements (FR + Key Entities), Success Criteria, Scope (In/Out), Fondations, Contraintes, Risques, Open Questions, Assumptions, Dependencies, Notes de livraison
- [~] No implementation details (languages, frameworks, APIs) — **déviation assumée** : les sections « Fondations transverses », « Contraintes techniques » et certains FR transverses (F01 à F045) citent des composants techniques existants (LangGraph, WeasyPrint, SQLAlchemy, etc.). Justification : l'utilisateur a explicitement demandé de **« Reprendre tel quel »** ces éléments dans le spec pour traçabilité avec les fondations livrées en sprints précédents. Ces détails restent confinés aux sections marquées « techniques » et ne polluent pas les User Stories, Acceptance Scenarios et Functional Requirements US1-US5.

## Requirement Completeness

- [x] No `[NEEDS CLARIFICATION]` markers remain — **par décision explicite** : les 8 questions ouvertes Q1-Q8 sont consolidées dans la section « Open Questions » et seront traitées par `/speckit.clarify` puis remontées dans la section « Clarifications »
- [x] Requirements are testable and unambiguous — chaque FR (FR-001 à FR-044) est rédigé en « DOIT » avec un critère vérifiable
- [x] Success criteria are measurable — SC-001 à SC-010 incluent métrique + cible + méthode de mesure (tableau dédié)
- [~] Success criteria are technology-agnostic (no implementation details) — **déviation mineure** : SC-005 cite « 3 136 passants pytest » (baseline projet), SC-004 cite `pytest --cov`, SC-007 cite Alembic. Justification : ces critères sont opérationnels au sein du repo ESG Mefali et leur traçabilité technique est demandée pour le CI. Les autres critères (SC-001, SC-002, SC-003, SC-006, SC-008, SC-009, SC-010) sont techno-agnostiques.
- [x] All acceptance scenarios are defined — chaque user story comporte ≥ 5 scénarios Given/When/Then (US1: 6, US2: 5, US3: 5, US4: 7, US5: 5)
- [x] Edge cases are identified — 10 edge cases listés (évaluation orpheline, changement de référentiel, versioning F13, RLS tiers, finalisation incomplète, conflit scores, abandon draft, timeout PDF, fenêtre tools LLM, référentiel dépublié)
- [x] Scope is clearly bounded — sections « In Scope » (11 items) et « Out of Scope » (8 items) explicites
- [x] Dependencies and assumptions identified — sections « Assumptions » (10 items) et « Dependencies » (4 items) dédiées

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — chaque FR est rattaché à au moins une user story et chaque scénario Given/When/Then valide une ou plusieurs FR
- [x] User scenarios cover primary flows — US1 (évaluation), US2 (matching), US3 (rapport PDF), US4 (chat LLM), US5 (migration F045) couvrent l'intégralité des flows de la feature
- [x] Feature meets measurable outcomes defined in Success Criteria — chaque SC se rattache à une ou plusieurs user stories (SC-001/SC-009 → US1, SC-002 → US2, SC-003 → US3, SC-006/SC-008 → US4, SC-007 → US5, SC-004/SC-005/SC-010 transverses)
- [~] No implementation details leak into specification — **même déviation assumée que ci-dessus** : autorisée par l'utilisateur dans ses instructions explicites. Les détails techniques sont rangés dans des sections clairement libellées (Fondations transverses, Contraintes techniques, Notes de livraison) et n'apparaissent pas dans les User Stories ou les Acceptance Scenarios.

---

## Validation Summary

**Statut global** : **PASS avec déviations assumées et documentées**

| Catégorie | Items totaux | Pass | Déviation assumée | Fail |
|---|---|---|---|---|
| Content Quality | 4 | 3 | 1 | 0 |
| Requirement Completeness | 8 | 7 | 1 | 0 |
| Feature Readiness | 4 | 3 | 1 | 0 |
| **Total** | **16** | **13** | **3** | **0** |

**Déviations assumées (3)** :
1. « No implementation details » — l'utilisateur a explicitement demandé que les fondations F01-F045 et contraintes techniques soient reprises verbatim dans le spec pour traçabilité. Les détails techniques sont confinés à des sections dédiées et ne contaminent pas les User Stories ni les Acceptance Scenarios.
2. « Success criteria technology-agnostic » — 3 SC sur 10 référencent des outils de mesure CI internes (pytest, Alembic, vitest). Justification : critères opérationnels au sein du repo, exigés par le contexte projet pour mesurer la non-régression.
3. « No implementation details leak into specification » — pendant des sections techniques explicites dédiées (Fondations, Contraintes), oui ; ailleurs (US, Acceptance, FR fonctionnels), non.

**Pas de FAIL** : aucun item ne nécessite de mise à jour du spec.

---

## Notes

- Les 8 questions ouvertes Q1-Q8 doivent être résolues par `/speckit.clarify` avant `/speckit.plan`. La section « Clarifications » du spec reste vide pour l'instant ; `/speckit.clarify` la peuplera en exploitant directement les questions de la section « Open Questions ».
- Aucune itération de mise à jour du spec n'est requise à ce stade. La feature est prête pour la phase de clarification.
- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan` — **aucun** dans ce cas.
