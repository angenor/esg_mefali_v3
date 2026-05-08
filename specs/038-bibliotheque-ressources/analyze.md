# Cross-Artifact Analysis — F20 Bibliothèque Ressources

**Spec**: [spec.md](./spec.md) — **Plan**: [plan.md](./plan.md) — **Tasks**: [tasks.md](./tasks.md) — **Clarify**: [clarify.md](./clarify.md)
**Date**: 2026-05-08

---

## 1. Coverage matrix : User Stories → FR → Tasks

| User Story (priorité) | FR couverts | Tasks |
|---|---|---|
| US1 — Consulter guide sourcé (P1) | FR-001, 002, 003, 005, 008, 009, 012, 024, 025 | T01–T08, T13–T14, T17–T18, T23, T27, T40–T41, T44–T46, T50–T51 |
| US2 — Fiche pratique intermédiaire (P1) | FR-004, 010, 026 | T04, T15, T23, T48, T52 |
| US3 — Télécharger template (P2) | FR-001, 011, 025, 033 | T16, T25, T29, T47 |
| US4 — Visionner vidéo (P2) | FR-001, 011, 025, 034 | T11, T16, T47 |
| US5 — Admin CRUD (P1) | FR-006, 007, 013–018, 027, 031 | T20–T22, T24, T28, T54–T58 |
| US6 — Recommandation IA (P3) | FR-019–023 | T19, T31–T35 |

**Vérification** : toutes les FR de la spec sont couvertes par au moins une tâche. Toutes les User Stories sont indépendamment testables (MVP slice possible avec uniquement US1+US5).

## 2. Cohérence Spec ↔ Plan ↔ Tasks

| Élément | Spec | Plan | Tasks |
|---|---|---|---|
| Migration 038 | mentionnée FR-014/T-spec | section 2.4 + down_revision=`037_alternative_credit_data` | T01–T03, T07–T08 |
| 5 types de ressource | FR-001 | section 2.1 colonne `type` + CHECK enum | T01, T09–T11 |
| Source F01 obligatoire | FR-002, SC-003, SC-006 | section 2.2 FK `source_id RESTRICT NOT NULL` | T01, T11 (validator), T20 (service vérif `source.status='verified'`), T28 (test) |
| 4-yeux F09 | FR-006, US5 AS1-3 | section 2.2 CHECK `verified_by != created_by` + section 3.3 `publish_resource` | T01 (CHECK), T22 (logic), T28 (test) |
| EXEMPT_MODELS | FR-031, Assumption Multi-tenant | section 1.2 + section 3.1 | T05 |
| Versioning F04 | FR-005, edge case « Resource superseded » | section 2.1 colonnes `version/valid_from/valid_to/superseded_by` + section 3.3 `update_resource` | T01, T21 |
| Tools lecture seule | FR-019–023 + US6 | section 3.5 + 3.6 garde-fou | T31–T35 |
| Garde-fou anti-mutation | FR-022, SC-007 | section 3.6 (test conformité) | T34 |
| 15+ ressources seed | FR-028, SC-002, SC-005 | section 3.7 | T36–T39 |
| Atomicité view_count | FR-011, SC-010, SC-011 | section 3.3 `increment_view_count` | T16, T29 |
| toast-ui/editor | FR-027 | section 4.2 + section 1.1 | T54 (npm install), T55 |
| Whitelist video | FR-034, edge case | section 2.2 + section 3.2 validators | T11, T47 |
| Dark mode | FR-024–027, SC-004 | section 4.3 + section 1.2 conventions | T44–T58 (manuel) |
| `/uploads/resources/` | Assumption Storage | section 2.4 + section 3.4 helper upload | T25 |
| Couverture ≥ 80 % | SC-008 | section 5 + DoD | T61–T62 |
| E2E Playwright | « Test E2E » critères acceptation | section 5.3 | T59 |

**Aucune incohérence détectée**. Les noms de modules/fichiers sont cohérents entre plan et tasks.

## 3. Risques résiduels

| Risque | Source | Mitigation présente | Action requise |
|---|---|---|---|
| down_revision incorrect | Plan section 2.4 | T01 mentionne `037_alternative_credit_data` mais le caller suggérait `033_create_skills`. Vérification faite : la dernière migration mergée est bien `037_alternative_credit_data` (vu via `ls backend/alembic/versions/`). | OK ; à confirmer en début d'implémentation phase 1. |
| Rédaction seed chronophage | Plan section 7 | Fallback : prioriser BOAD/PNUD/GCF, drafts pour les autres | OK |
| `MAX_TOOLS_PER_TURN` insuffisant | Plan section 3.5 | T32 vérification | À ajuster pendant implémentation si besoin (probablement déjà 14+ après F23) |
| toast-ui/editor pas en stack | Note CLAUDE.md « à installer » | T54 `npm install` | OK |
| EXEMPT_MODELS pourrait perdre l'audit admin | Plan section 1.2 | Middleware `AdminAuditContextMiddleware` déjà en place (F03/F09) | OK, hérité existant |

## 4. Conformité aux conventions du projet

- ✅ FR avec accents (UI, commentaires, contenus de seed).
- ✅ snake_case (Python), PascalCase (Vue components), TS strict.
- ✅ Composables dans `composables/`, pages dans `pages/` avec routing automatique, store Pinia.
- ✅ Dark mode obligatoire sur tous les composants.
- ✅ Réutilisabilité : `<SourceLink>` (F01), `<ReferentialBadge>` (F04) réutilisés ; nouveau composant générique `ResourceMarkdownRenderer` extractible.
- ✅ Sourçage F01 cliquable sur chaque chiffre (validator post-tour LLM existant + balisage markdown).
- ✅ Multi-tenant : EXEMPT explicite (cohérent avec sources, intermediaries, funds, skills).
- ✅ Audit F03 via middleware admin existant.
- ✅ Versioning F04 sur édition de publié.
- ✅ Workflow 4-yeux F09 strict.
- ✅ Devise XOF (peu d'usage Money dans ce module mais aligné).
- ✅ UUID v4 pour les identifiants.
- ✅ Garde-fou anti-mutation LLM aligné F23.

## 5. Indicateurs de qualité

- **Tasks count**: 64
- **FR count**: 34
- **SC count**: 15
- **User Stories count**: 6 (3 P1 + 2 P2 + 1 P3)
- **Edge cases count**: 12
- **Test estimation backend**: ~75 nouveaux tests (model 8 + schemas 12 + service 18 + router 9 + admin router 11 + tools 6 + guard 1 + seed 4 + migration 5 + atomicité 1)
- **Test estimation frontend**: ~47 nouveaux tests Vitest (composables 13 + store 5 + composants publics 22 + composants admin 7) + 4 E2E
- **Couverture cible**: ≥ 80 % sur le périmètre F20

## 6. Décision finale

**Status**: ✅ READY FOR IMPLEMENT

Tous les artefacts SpecKit sont cohérents. Aucun blocker, aucune ambiguïté résiduelle. Les hypothèses sont documentées et alignées avec les patterns établis par les features F01, F03, F07, F09, F23.

Prochaine étape : `/speckit.implement` ou Phase B (implémentation) sur la branche `feat/F20-bibliotheque-ressources`.

## 7. Blocking questions

Aucune.
