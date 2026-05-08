# Cross-artifact Consistency Analysis: F18

**Branch**: `feat/F18-mobile-money-photos-ia-public-data` (spec `037`)
**Date**: 2026-05-08
**Artifacts analysed**: [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md)

---

## 1. Coverage matrix — User Stories ↔ Functional Requirements ↔ Plan ↔ Tasks

| User Story | FRs principales | Plan section | Tasks |
|---|---|---|---|
| US1 — Mobile Money | FR-001..006, FR-019..025 | §3.2 (tables MM), §4.1/4.3 (services & endpoints), §4.4 (scoring) | T010-T014, T020-T021, T030-T032, T040-T047, T080-T083, T110-T113, T121, T130, T141 |
| US2 — Photos IA | FR-007..012, FR-019..025 | §3.2 (`credit_photos`), §4.1 (`photo_analyzer`), §4.6 (sécurité fichiers) | T060-T066, T122, T130, T141 |
| US3 — Données publiques | FR-013..015, FR-019..025 | §3.2 (`public_data_sources`), §4.1 (`public_data_collector`) | T070-T073, T123, T130, T141 |
| US4 — Méthodologie publique | FR-017..018, FR-022 | §3.2 (`credit_methodology_factors`), §4.3 (route publique) | T050-T053, T131, T141 |
| US5 — Auditabilité & révocabilité | FR-019..023 | §3.3 (RLS), §3.4 (audit), §4.5 (hook) | T030-T032, T090-T093, T161 |

**Conclusion** : 5/5 user stories couvertes ; chaque FR est traçable à au moins une section de plan et 1+ tâches. Aucun gap.

---

## 2. Success Criteria ↔ Tests

| SC | Garantie technique | Tâches de validation |
|---|---|---|
| SC-001 (403 sans consent) | `consent_guard.require_consent` | T030-T032, T141 |
| SC-002 (≥ 95 % lignes valides 4 fournisseurs MM) | Parsers + fixtures `tests/fixtures/mobile_money/{4 fichiers}` | T040-T042 |
| SC-003 (≥ 5 KPIs, < 30s P95) | Analyzer + tests perf | T043-T044 |
| SC-004 (5 scores photos, < 60s P95, idempotent) | Analyzer Vision + cache `content_hash` | T064-T066 |
| SC-005 (poids public ≤ 10 %) | Refactor `compute_combined_score` | T080-T081 |
| SC-006 (≥ 99 % audit) | `Auditable` mixin sur 5 modèles | T012-T013, T032 |
| SC-007 (méthodologie cohérente API/page) | Service filtre published + source_id | T050-T053, T131 |
| SC-008 (révocation → exclusion + purge 30j) | Hook + cron | T090-T093 |
| SC-009 (≥ 80 % couverture) | Plan tests | T160 |
| SC-010 (aucun chiffre sans source) | Test automatique sur réponses API | T083 |

**Conclusion** : 10/10 SC mappés à des tâches concrètes.

---

## 3. Vérification des invariants projet

| Invariant CLAUDE.md | Statut F18 |
|---|---|
| **F01 sourçage obligatoire** | OK — `credit_methodology_factors.source_id` NOT NULL, filtre published, test SC-010, `<SourceLink>` partout côté UI. |
| **F02 multi-tenant + RLS** | OK — 5 tables tenant avec `account_id` NOT NULL FK + RLS ENABLE+FORCE + 2 policies. `credit_methodology_factors` exempté (catalogue). |
| **F03 audit log** | OK — 5 modèles ajoutés à `AUDITABLE_MODELS`. `MobileMoneyAnalysis` à valider en revue (artefact recalculé, candidat à `EXEMPT_MODELS`). |
| **F04 Money typed** | OK — paires `amount/currency` sur `mobile_money_transactions` + balance ; CHECK currency enum. |
| **F05 consents** | OK — `require_consent(account_id, type)` câblé sur tous les endpoints sensibles, hook révocation + purge 30j. |
| **Dark mode** | OK — toutes pages/composants prévus dark mode. |
| **FR avec accents** | OK — UI 100 % FR avec accents. |
| **UUID v4 + timestamptz** | OK — convention respectée. |
| **Stockage local /uploads/** | OK — `/uploads/{account_id}/credit/{type}/`. |
| **Tests mock LLM** | OK — `photo_analyzer` testé avec mock OpenRouter Vision. |

**Conclusion** : aucun invariant violé.

---

## 4. Dépendances inter-features

| Dépendance | État | Risque |
|---|---|---|
| F01 sources | mergée (020) — disponible | Faible (seed à ajouter dans 037) |
| F02 multi-tenant | mergée (019) | Aucun |
| F03 audit | mergée (021) | Aucun |
| F04 Money | mergée (022) | Aucun |
| F05 consents | mergée (027) | **À vérifier** : signature exacte de `require_consent` et événement de révocation. T002 prévoit cette vérification. |
| OpenRouter Vision | dépendance externe | Modèle Claude vision multimodal disponible chez OpenRouter — fallback mock-friendly en tests. |

**Conclusion** : 1 risque modéré (signature F05) traité dans T002.

---

## 5. Cohérence numéros de migration & spec

- **Spec** : `037-mobile-money-photos-ia-public-data` ✅
- **Migration Alembic** : `037_alternative_credit_data.py` (down_revision=`035_admin_publication_status_workflow`) ✅
- **Branche** : `feat/F18-mobile-money-photos-ia-public-data` (renommée pour cohérence avec convention F-numéro projet) ✅
- F14 réservée 036 (parallèle) → pas de collision ✅

---

## 6. Risques / Blocking questions

| ID | Description | Impact | Mitigation |
|---|---|---|---|
| R1 | Signature exacte F05 `require_consent` non vérifiée | Moyen (refactor adapter) | T002 vérifie en début de sprint 1 |
| R2 | Coût Claude Vision sur masse de photos | Moyen | Idempotence `content_hash`, cap 10/PME, cache JSONB |
| R3 | Volume CSV MM > 50 000 lignes | Faible | Cap dur, message UX clair |
| R4 | Photos avec personnes (RGPD) | Élevé en théorie, mitigé | Pas de reconnaissance faciale, prompt explicite, consent obligatoire |
| R5 | `MobileMoneyAnalysis` doit-elle être auditée ? | Faible | Décision de revue : exempt (artefact recalculé), à confirmer en code review |

**Aucune blocking question** : toutes les décisions sont prises selon les invariants ou plan documenté.

---

## 7. Conclusion

- Spec, Plan, Tasks sont **cohérents** entre eux.
- 5 user stories, 25 FR, 10 SC tous couverts.
- 70 tâches ordonnées TDD-first sur 3 sprints.
- Tous les invariants projet (F01-F05, dark mode, FR, Money, RLS, audit) respectés.
- 0 blocker, 1 risque modéré tracé (T002).

**Ready for implementation** : ✅ OUI.
