# Analyze — F14 cross-artifact consistency

## 1. Coverage spec → plan → data-model → tasks

| User Story | Spec FR | Plan section | Data model | Task IDs |
|---|---|---|---|---|
| US1 — Offres compatibles | FR-001..005, FR-013 | Phase 1 (offer_matches), Phase 3 (T08, T36) | offer_matches | T01, T08, T36, T38, T44 (US1) |
| US2 — Comparateur intermédiaires | FR-014, FR-012 | Phase 3 (T17, T19, T40) | offer_matches + ComparisonResult schema | T17, T19, T40, T44 (US2) |
| US3 — Critères manquants → sources F01 | FR-015 | Phase 3 (T34, T41) | score_breakdown.fund.missing_criteria[].source_id | T34, T41, T44 (US3) |
| US4 — Alertes nouvelles offres | FR-009, FR-010 | Phase 3 (T10, T15, T35) | match_alerts_subscriptions, OfferMatch.last_notified_at | T10, T15, T35, T44 (US4) |

✅ Toutes les US ont au moins 1 endpoint, 1 modèle ou colonne, 1 composant Vue, et 1 scénario E2E.

## 2. Functional requirements coverage

20 FR au total. Vérification :

- FR-001..FR-005 (modèle + scoring) → T01, T08
- FR-006 (4 endpoints REST) → T17 (5 endpoints en réalité avec PATCH match-alerts)
- FR-007 (RLS) → T04, T23
- FR-008 (recompute incrémental event-driven) → T12
- FR-009..FR-010 (alertes) → T10, T15
- FR-011..FR-012 (4 tools + ComparisonTableBlock) → T19, T22
- FR-013..FR-015 (3 pages frontend) → T38, T39, T40, T41
- FR-016 (audit) → T24
- FR-017 (cap MAX_TOOLS_PER_TURN=18) → T21
- FR-018 (dark mode) → T32-T36 (intégré chaque composant)
- FR-019 (ARIA) → T32, T33, T35 (intégré chaque composant)
- FR-020 (couverture ≥ 80 %) → T46

✅ Toutes les FR ont au moins une tâche assignée.

## 3. Success criteria coverage

| SC | Tâche | Validation |
|---|---|---|
| SC-001 (100 % matches affichent décomposé) | T36, T44 | Test E2E US1 |
| SC-002 (page comparateur < 2s pour 5 offres) | T40 | Test perf manuel quickstart |
| SC-003 (cron idempotent) | T11, T16 | Tests test_alerts_service + test_cron_matching |
| SC-004 (0 régression) | T46 | CI complete avant merge |
| SC-005 (round-trip Alembic) | T05 | Test test_alembic_036 |
| SC-006 (pas de fund_match writes) | T25 | Conformity grep AST |
| SC-007 (dark mode) | T32-T36 | Tests Vitest dark mode |
| SC-008 (compare émet block visualisation) | T19, T20 | Test marker SSE |

✅ Tous les SC sont vérifiables.

## 4. Constitution & invariants

- **Sourçage F01** : `score_breakdown.fund.missing_criteria[].source_id` populé via F13. UI `<MissingCriteriaList>` rend `<SourceLink>`. ✅
- **Multi-tenant F02 + RLS** : `account_id` NOT NULL sur 2 tables. RLS ENABLE+FORCE + 2 policies. T23 teste. ✅
- **Audit F03** : `OfferMatch` + `MatchAlertSubscription` dans `AUDITABLE_MODELS`. T24 teste source_of_change manual/llm/import. ✅
- **Money F04** : `_compute_size_match` lit `Money.from_columns(fund.min_amount_money, max_amount_money)` + `currency_service.convert` + catch `NoRateAvailableError` → 50 neutre. ✅
- **Versioning F04** : non applicable (matches recompute in-place). Lecture versionnée des `Offer`/`Fund` via leurs propres mécanismes. ✅
- **F12 mémoire** : aucune modification de `MessageChunk`. Les calculs déterministes ne génèrent pas de chunks. ✅
- **F22 decision tree** : tools déterministes, pas de retry LLM nécessaire. ✅
- **F23 skills** : tools NON listés dans skills MVP (post-MVP via `activation_rules`). ✅
- **Dark mode** : 5 composants × variantes `dark:` documentées dans tasks. ✅
- **FR avec accents** : tous libellés UI et `recommended_actions` formatés en français accentué. ✅

## 5. Risques cross-artifact

### R-A — F19 reminder_type_enum doit contenir `new_offer_alert`
**Statut** : à vérifier en Phase B au moment de la migration. Si F19 PR #20 (cron-rappels-dispatcher) est mergé avant F14, sa migration crée déjà l'enum avec les valeurs nécessaires. Sinon, F14 doit ajouter `ALTER TYPE reminder_type_enum ADD VALUE 'new_offer_alert'` dans la migration 036 (idempotent via `IF NOT EXISTS` pattern).
**Mitigation** : check explicite dans migration 036 :
```python
op.execute("ALTER TYPE reminder_type_enum ADD VALUE IF NOT EXISTS 'new_offer_alert'")
```
(skip SQLite via dialect check).

### R-B — F14 down_revision dépend de l'ordre de merge
**Statut** : à confirmer en Phase B. Au moment de Phase A, dernière migration sur main = `035_admin_publication_status_workflow`. Si F19 (#20) mergé avant F14, down_revision = la migration F19. Si F19 mergé après, down_revision = 035 et F19 devra rebase.
**Mitigation** : commit final de F14 mettra à jour `down_revision` à la valeur correcte juste avant le merge.

### R-C — F11 ComparisonTableBlock attend un format précis
**Statut** : F11 attend `subjects[]` + `rows[]` avec `values[].subjectId`. Le contract OpenAPI F14 respecte ce format. Test conformity à ajouter si frontend modifie le format.
**Mitigation** : test E2E US2 valide le rendu visuel.

### R-D — Backfill peut produire des matches incohérents
**Statut** : le backfill copie `compatibility_score` sur les 3 colonnes (global/fund/intermediary). Cela donne `bottleneck='balanced'` artificiel. Acceptable MVP : le cron `recompute_stale_matches` réécrira correctement les valeurs au prochain passage (sous 30 jours).
**Mitigation** : documenter dans CLAUDE.md que les premiers matches post-backfill sont approximatifs jusqu'au premier recompute cron.

## 6. Ambiguïtés résolues

| Ambiguïté | Résolution |
|---|---|
| Notification channels | MVP = uniquement Reminder F19 + badge dashboard (pas d'email — post-MVP) |
| Threshold default | `min_global_score = 60` par défaut, modifiable par PME via PATCH |
| Cap recompute | 50 offres / projet / run (anti-DoS) |
| Conservation fund_matches | 2 sprints en lecture seule, drop hors-scope F14 |
| Pondération sub-scores | Constante hardcodée MVP, table BDD post-MVP |
| Cache matches | BDD = autorité, lru_cache TTL 5 min sur listing uniquement |
| Auto-souscription alertes | Oui, via event listener `after_insert` Project (idempotent) |
| Sector match algorithme | Binaire 100/0 MVP |

## 7. Verdict

✅ **Spec, plan, data-model, contracts, tasks sont mutuellement consistants.**
✅ **Toutes les US, FR, SC sont couverts par au moins une tâche.**
✅ **Risques identifiés et mitigés.**
✅ **Constitution respectée.**

**Ready for `/speckit.implement` (Phase B).**
