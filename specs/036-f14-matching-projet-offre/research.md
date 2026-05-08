# Research — F14 Matching Projet ↔ Offre

## Réutilisation existante

### F13 multi-référentiels (déjà mergé)

`backend/app/modules/esg/multi_referential_service.py` expose **`compute_referential_score_for_offer(db, offer, assessment) -> BottleneckInfo`** qui :
- Charge le référentiel du `fund` (fallback Mefali si NULL)
- Charge le référentiel de l'`intermediary` (idem)
- Calcule un score 0..100 par référentiel via `compute_score_for_referential`
- Identifie le goulot (`min(fund_score, intermediary_score)`) + top 3 critères bloquants
- Retourne un objet `BottleneckInfo` (`fund_score`, `intermediary_score`, `top_3_blockers[]`)

**F14 délègue à cette fonction** la couche ESG du score décomposé. F14 ajoute uniquement les 5 sub-scores non-ESG (sector/size/location/documents/instrument) et la persistance.

### F07 offers + DIRECT singleton

`backend/app/modules/offers/calculator.py` produit `compute_effective_offer` qui agrège fund+intermediary en `effective_*` (criteria/documents/fees/processing_time/disbursement_time). F14 lit ces champs effectifs pour `documents_match`. Le seed `DIRECT` (`code='DIRECT'`) permet de générer une « offre directe sans intermédiaire » qui sert de fallback dans le backfill.

### F11 visualization tools

`frontend/app/components/richblocks/ComparisonTableBlock.vue` est déjà disponible avec :
- Format desktop (table) + mobile (cartes)
- Highlight winner (parsing best-effort)
- SourceLink F01 par cellule
- Types `ComparisonValueType` (money/percentage/duration/rating/boolean)

F14 réutilise tel quel via le tool `compare_offers_for_fund` qui émet le marker SSE et le composant rend automatiquement.

`frontend/app/components/richblocks/MatchCardBlock.vue` est aussi disponible — F14 l'utilise dans `<OffersCompatibleSection>`.

### F01 sourçage

`<SourceLink>` + `<SourceModal>` + composable `useSources` permettent à F14 d'afficher les sources verified pour chaque critère manquant sans nouveau code.

### F03 audit log

Le mixin `Auditable` + listener global `before_flush` capture automatiquement toutes les mutations sur les modèles dans `AUDITABLE_MODELS`. F14 ajoute simplement `OfferMatch` et `MatchAlertSubscription` à cette liste — aucun code custom nécessaire.

---

## Décisions techniques (résumé)

| ID | Sujet | Décision | Alternatives écartées |
|---|---|---|---|
| D1 | Migration FundMatch → OfferMatch | Tables parallèles + legacy 2 sprints | Renommage in-place (risqué), drop immédiat (breaking) |
| D2 | Cache matches | Pas de cache persistance, lru_cache 5 min sur listing | Redis (over-engineering), 1h cache (stale) |
| D3 | sector_match | Binaire 100/0 selon `project.sector ∈ fund.target_sectors` | Score graduel ontologique (post-MVP) |
| D4 | size_match | Graduel linéaire ±50 % autour de la fourchette | Binaire (trop strict), gaussien (over-eng) |
| D5 | Pondération | Constante hardcodée `MATCHING_WEIGHTS` | Table BDD configurable (post-MVP) |
| D6 | Trigger recompute | Event listener after_update + BackgroundTasks | Recompute synchrone (latence), pure cron (alertes tardives) |
| D7 | Idempotence alertes | `last_notified_at` sur OfferMatch | Table satellite `match_notifications` (over-eng) |
| D8 | Backfill | Best-effort, ON CONFLICT DO NOTHING, skip si inférence impossible | Abandon historique (perte UX), exhaustif (intrusif) |

---

## Risques techniques résolus

### R1 — Boucle infinie event listener Project after_update
Mitigation : ContextVar Python `_recompute_in_progress` set lors du début de `recompute_matches_for_project`, reset après. Tout listener qui détecte la flag skippe.

### R2 — Backfill long sur prod (~10k fund_matches)
Mitigation : SQL pur (pas Python loop), exécuté lors de la migration up dans une seule transaction. Estimation : 10k INSERTs SELECT < 5s.

### R3 — Money typed conversion peut échouer (pas de taux)
Mitigation : `_compute_size_match` catche `NoRateAvailableError` (F04) et retourne 50 (neutre) avec flag `size_match_currency_mismatch=true` dans le breakdown. Test unitaire ad hoc.

### R4 — Cap 50 offres / projet
Mitigation : `recompute_matches_for_project` log WARN si `count > 50` et tronque (politique anti-DoS MVP). Post-MVP : pagination du recompute.

### R5 — RLS PostgreSQL skip en SQLite tests
Mitigation : pattern projet existant — migration check `if op.get_bind().dialect.name == 'postgresql'`, tests RLS dédiés `tests/security/test_offer_matches_rls.py` exécutés uniquement avec marker `@pytest.mark.postgres`.

---

## Dépendances cross-features

- **F01 sources** : `cite_source` non requis dans F14 (les sources sont stockées via `source_id` sur les indicateurs F13, pas via tool calls). Toutefois, le rendu `<MissingCriteriaList>` utilise `<SourceLink>` cliquable.
- **F06 projects** : F14 lit `Project` (sector, target_amount Money typed F04, location_country, financing_structure, objective_env). Aucune migration sur `Project`.
- **F07 offers** : F14 lit `Offer` (effective_required_documents, fund/intermediary via selectin). Refactor `compare_offers_for_fund` (stub F07 → impl F14).
- **F13 multi-référentiels** : F14 délègue le calcul ESG à `compute_referential_score_for_offer`. Aucune modification F13.
- **F19 cron rappels** : F14 crée des Reminder F19 (`kind='new_offer_alert'`). Type ajouté dans F19 (vérifier que le PR F19 inclut bien cette valeur dans `reminder_type_enum` — sinon migration F14 doit l'ajouter via `ALTER TYPE`).
- **F11 visualization** : F14 réutilise `ComparisonTableBlock` et `MatchCardBlock` sans modification.
- **F22 decision tree** : pas d'impact direct (matching déterministe sans LLM).
- **F23 skills** : tools F14 NON listés dans skills MVP, mais peuvent l'être post-MVP.

---

## Références

- Brainstorming Module 3.2 — `documents_et_brouillons/features_a_implementer/F14-matching-projet-offre.md`
- F13 service — `backend/app/modules/esg/multi_referential_service.py`
- F11 components — `frontend/app/components/richblocks/{ComparisonTableBlock,MatchCardBlock}.vue`
- F07 calculator — `backend/app/modules/offers/calculator.py`
- F03 audit log — `docs/audit-log.md`
- F02 RLS — `docs/auth-and-multitenant.md`
- F04 Money typed — `backend/app/core/money.py`
