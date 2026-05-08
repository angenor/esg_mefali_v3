# Quality checklist — F14 Matching Projet ↔ Offre

## Spec quality

- [x] Toutes les User Stories ont un Independent Test
- [x] Toutes les FR sont mesurables / testables
- [x] Tous les SC sont quantifiables
- [x] Hors-scope explicitement listé
- [x] Clarifications résolues sans ambiguïté restante
- [x] Vocabulaire FR cohérent avec le projet

## Plan quality

- [x] Architecture claire (diagramme + flux)
- [x] Décisions techniques justifiées avec alternatives
- [x] Contrôle de constitution (sourçage, multi-tenant, audit, Money, dark mode, FR)
- [x] Phase 0/1/2/3 documentées
- [x] Risques + mitigations listés

## Data model quality

- [x] Toutes les colonnes ont type, nullable, default, contrainte
- [x] Indexes justifiés par requêtes attendues
- [x] CHECK constraints applicatives portables PG/SQLite
- [x] RLS PG-only avec policies F02 cohérentes
- [x] Round-trip up/down/up validé en plan

## Contracts quality

- [x] OpenAPI 3.1 valide
- [x] Tous les endpoints documentés (5)
- [x] Schémas Pydantic miroir
- [x] Codes erreurs (404, 422, 401)
- [x] Auth Bearer JWT documentée

## Tasks quality

- [x] Tâches granulaires (≤ 1 jour de travail chacune)
- [x] Dépendances explicites `[D:X]`
- [x] Tâches parallélisables marquées `[P]`
- [x] Tests inclus pour chaque module métier
- [x] Critical path identifié

## Cross-artifact consistency (analyze.md)

- [x] US ↔ FR ↔ tasks couverts
- [x] FR ↔ tasks couverts
- [x] SC ↔ tâches de validation couverts
- [x] Risques cross-feature documentés (F19 enum, ordre de merge)

## Pre-implementation guardrails

- [x] Aucun nouveau secret / env var requis
- [x] Aucune dépendance npm/pip nouvelle (réutilise stack existante)
- [x] Migration Alembic réversible
- [x] Backfill best-effort idempotent
- [x] Feature flag pour rollout (USE_OFFER_MATCH_VIEW)
- [x] Conformity tests planifiés (no fund_match writes, no skill mutation)
