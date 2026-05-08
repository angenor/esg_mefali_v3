# Implementation Plan: F14 — Matching Projet ↔ Offre + Comparateur

**Branch**: `feat/F14-matching-projet-offre` | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Down_revision Alembic**: à confirmer en Phase B (au moment de Phase A : `035_admin_publication_status_workflow`)

## Architecture overview

F14 introduit **2 nouvelles tables** (`offer_matches`, `match_alerts_subscriptions`), **1 service backend** (`matching_service.py`), **1 router REST** (`matching_router.py`), **4 tools LangChain** (`matching_tools.py`), **1 cron** (`notify_new_offer_matches.py`), **2 event listeners SQLAlchemy** (Project + Offer), **3 nouvelles pages Vue**, **5 nouveaux composants**, **1 composable**, **1 store Pinia**.

F14 réutilise **massivement F13** : le calcul du score décomposé fund/intermediary délègue à `app.modules.esg.multi_referential_service.compute_referential_score_for_offer` qui retourne déjà un `BottleneckInfo`. F14 ajoute la persistance, l'orchestration, et 5 sub-scores non-ESG (sector/size/location/documents/instrument).

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend Nuxt 4                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ /profile/projects/[id]      → <OffersCompatibleSection>│   │
│ │ /profile/projects/[id]/matches  (liste paginée)        │   │
│ │ /financing/compare/[fund_id]?project_id=X              │   │
│ │ /financing/offers/[offer_id]   (extension F07)         │   │
│ └────────────────────────────────────────────────────────┘   │
│ Composable useMatching   Store Pinia matches                 │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP /api/projects/{id}/matches, /compare
                     │ HTTP /api/projects/{id}/match-alerts
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend FastAPI                                              │
│ ┌─────────────────────────────────────────────────────────┐  │
│ │ matching_router.py                                      │  │
│ │   GET  /matches | POST /recompute-matches               │  │
│ │   GET  /compare | GET /match-details                    │  │
│ │   PATCH /match-alerts                                   │  │
│ └─────────────────────────────────────────────────────────┘  │
│ ┌─────────────────────────────────────────────────────────┐  │
│ │ matching_service.compute_offer_match()                  │  │
│ │   ├─ delegate to F13 compute_referential_score_for_offer│  │
│ │   ├─ compute 5 sub-scores (sector/size/location/docs/   │  │
│ │   │    instrument) avec MATCHING_WEIGHTS                │  │
│ │   ├─ bottleneck rule (fund / intermediary / balanced)   │  │
│ │   └─ UPSERT offer_matches (UNIQUE project_id, offer_id) │  │
│ └─────────────────────────────────────────────────────────┘  │
│ ┌─────────────────────────────────────────────────────────┐  │
│ │ alerts_service.subscribe / unsubscribe / notify_new     │  │
│ └─────────────────────────────────────────────────────────┘  │
│ ┌─────────────────────────────────────────────────────────┐  │
│ │ Event listeners after_update on Project, Offer          │  │
│ │   → invalidate matches (expires_at = now())             │  │
│ └─────────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────┘
                     │ asyncpg + RLS                            
                     ▼
┌──────────────────────────────────────────────────────────────┐
│ PostgreSQL 16                                                │
│   offer_matches (RLS ENABLE+FORCE, 2 policies F02)           │
│   match_alerts_subscriptions (RLS ENABLE+FORCE, 2 policies)  │
│   fund_matches (legacy, lecture seule, drop ≥ 2 sprints)     │
└──────────────────────────────────────────────────────────────┘
```

LangGraph nodes `chat`, `financing`, `application` → injection des 4 tools matching dans `MODULE_TOOL_MAPPING`. Page `/profile/projects/{id}` → tools lecture via `PAGE_TOOL_MAPPING['profile_projects']`.

Cron quotidien F19 :
- `scripts/recompute_stale_matches.py` (idempotent, batch 100, picks `expires_at < now()`)
- `scripts/notify_new_offer_matches.py` (idempotent, marque `last_notified_at`)

---

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, LangChain, LangGraph, langchain-openai (réutilisation F13 pour scoring) ; Nuxt 4, Vue Composition API, Pinia, TailwindCSS, Playwright, Vitest
**Storage**: PostgreSQL 16 + pgvector (lecture seule pour Source/Project/Offer/Referential), Money typed F04, audit log F03, RLS F02
**Testing**: pytest async + Vitest + Playwright. Mock LLM par défaut (pas d'appel OpenRouter pour tests F14, calcul ESG délégué à F13 qui est déjà testée)
**Target Platform**: Linux server (FastAPI uvicorn), navigateurs modernes
**Project Type**: Monorepo (`backend/` + `frontend/`)
**Performance Goals**: P95 `compute_offer_match` < 500 ms (5 sub-scores + délégation F13 + UPSERT). P95 page comparateur < 2s pour 5 offres. Cron batch 100 matches/run < 30s.
**Constraints**: Cap dur 50 offres / `recompute-matches` (anti-DoS). Pas d'appel LLM dans le calcul (déterministe). Pas d'appel HTTP externe.
**Scale/Scope**: 1 PME = ~5 projets actifs × ~50 offres compatibles = ~250 matches max actifs simultanés. Cron quotidien = ~1000 PME × 5 projets × incrémental → batch 100/run viable.

---

## Constitution Check

- ✅ **Sourçage F01** : chaque critère manquant porte un `source_id` cliquable dans `<MissingCriteriaList>`.
- ✅ **Multi-tenant F02 + RLS** : `account_id` NOT NULL sur les 2 tables, RLS ENABLE+FORCE, policies `pme_access_own_account` + `admin_full_access`.
- ✅ **Audit F03** : `OfferMatch` et `MatchAlertSubscription` ajoutés à `AUDITABLE_MODELS`. Source of change : `manual`/`llm`/`import` selon contexte (middleware admin / `_with_llm_source` / cron).
- ✅ **Money typed F04** : pas de nouveaux champs Money à persister, mais consommation via `Offer.effective_fees` et conversion via `currency_service` (F04) pour `size_match`.
- ✅ **Versioning F04** : `OfferMatch` n'est PAS catalogue (recompute in-place), versioning non applicable. `Offer` versioning lu en lecture seule.
- ✅ **Dark mode obligatoire** : tous nouveaux composants utilisent les classes `dark:`.
- ✅ **FR avec accents** : tous les libellés UI et messages backend en français accentué.
- ✅ **F12 mémoire** : pas d'impact (matching ne génère pas de chunks).
- ✅ **F22 decision tree** : pas d'impact (tools F14 sont déterministes, pas de retry LLM).
- ✅ **F23 skills** : aucun tool F14 n'est listé dans une skill MVP, mais le système d'activation peut les inclure post-MVP via `activation_rules`.

---

## Phase 0 — Research / Decisions

### Décision D1 — Stratégie migration FundMatch → OfferMatch
**Décision** : créer table `offer_matches` en parallèle, conserver `fund_matches` 2 sprints en lecture seule (legacy `_deprecated`).
**Rationale** : aligne la pratique F04 (conservation `*_xof` 2 sprints), évite breaking change sur la page `/financing` actuelle, permet rollback rapide.
**Alternatives écartées** : renommage in-place (risqué pour les routers existants qui lisent `fund_matches`), drop immédiat (impossible sans refactorer toute la page `/financing` simultanément).

### Décision D2 — Cache des matches
**Décision** : pas de cache in-memory pour la persistance (BDD = autorité), mais cache `lru_cache(ttl=300s)` sur `list_matches_for_project` pour la pagination.
**Rationale** : matches changent peu (recompute 30j ou event-driven), cache sur listing améliore P95 sans risque d'incohérence (TTL 5 min acceptable pour UI).
**Alternatives écartées** : Redis (over-engineering MVP), cache 1h (trop long, donne des matches stale après modification projet).

### Décision D3 — Calcul du sector_match
**Décision** : valeur binaire 100/0 selon `project.sector ∈ offer.fund.target_sectors` (liste hardcodée référencée F01 via SECTORS catalog).
**Rationale** : simple, déterministe, pédagogique pour la PME (« compatible » ou « non »).
**Alternatives écartées** : score graduel basé sur similarité sectorielle (nécessite ontologie sectorielle absente F14, post-MVP).

### Décision D4 — Calcul du size_match
**Décision** : 100 si `target_amount` dans la fourchette, graduel linéaire vers 0 à ±50 % de l'écart au plus proche bord.
**Rationale** : récompense les projets dans la cible, pénalise progressivement les écarts, évite le binaire trop strict.
**Alternatives écartées** : binaire (trop strict), gaussien (over-engineering).

### Décision D5 — Pondération MVP
**Décision** : pondération hardcodée `MATCHING_WEIGHTS = {sector: 0.25, esg: 0.30, size: 0.15, location: 0.10, documents: 0.10, instrument: 0.10}` dans une constante module.
**Rationale** : simplicité MVP, validable par tests unitaires, modifiable post-MVP via table `matching_weights` (hors-scope).
**Alternatives écartées** : pondération configurable BDD (over-engineering MVP), pondération par sector (complexité non justifiée).

### Décision D6 — Trigger de recompute
**Décision** : event listeners SQLAlchemy `after_update` sur `Project` (champs `target_amount_amount`, `target_amount_currency`, `sector`, `location_country`, `financing_structure`, `objective_env`) et `Offer` (champs `is_active`, `publication_status`, `effective_*`). Schedule async via FastAPI BackgroundTasks (limité à 50 offres/projet, log au-delà).
**Rationale** : cohérent F22 (event-driven), évite recompute global. Délégation au cron F19 pour le rattrapage `expires_at < now()`.
**Alternatives écartées** : recompute synchrone (latence inacceptable), pure cron (alertes trop tardives).

### Décision D7 — Idempotence des alertes
**Décision** : champ `OfferMatch.last_notified_at` (NULL = jamais notifié, sinon timestamp). Cron pick WHERE `last_notified_at IS NULL AND global_score >= subscription.min_global_score`. Marqué après création du Reminder F19.
**Rationale** : idempotence de la table de matches sans table satellite. Cohérent avec patterns F19.
**Alternatives écartées** : table `match_notifications` séparée (over-engineering MVP).

### Décision D8 — Backfill best-effort
**Décision** : backfill `fund_matches` → `offer_matches` lors de la migration, ON CONFLICT DO NOTHING. Inférence `project_id` = dernier projet actif du compte ; `offer_id` = offre `(fund_id, intermediary_id=DIRECT, version la plus récente publiée)`. Skip si inférence impossible (log WARN).
**Rationale** : préserve la valeur métier des matches existants quand possible, sans bloquer la migration.
**Alternatives écartées** : abandon des `fund_matches` historiques (perte UX), backfill exhaustif avec création de projets (intrusif, hors-scope).

---

## Phase 1 — Data model

Voir [data-model.md](./data-model.md) pour le détail complet.

**Résumé** :
- `OfferMatch` (16 colonnes, 4 CHECK, 5 indexes, UNIQUE `(project_id, offer_id)`, RLS)
- `MatchAlertSubscription` (7 colonnes, UNIQUE `(project_id)`, RLS)
- Réutilisation `Project` (F06), `Offer` (F07), `Source` (F01), `Referential` (F13), `ESGAssessment` (F05)
- 0 nouvel ENUM SQL (les enums sont en VARCHAR + CHECK pour portabilité SQLite tests, conforme pattern projet)

---

## Phase 2 — API Contracts

Voir [contracts/openapi.yaml](./contracts/openapi.yaml) pour la spec OpenAPI complète.

**Résumé** :
- `GET /api/projects/{project_id}/matches` → `OfferMatchListResponse` (paginated, filters)
- `POST /api/projects/{project_id}/recompute-matches` → `RecomputeMatchesResponse` (202)
- `GET /api/projects/{project_id}/compare?fund_id=X` → `ComparisonResult` (F11 typed)
- `GET /api/projects/{project_id}/match-details/{offer_id}` → `OfferMatchDetail`
- `PATCH /api/projects/{project_id}/match-alerts` → `MatchAlertSubscriptionResponse`

Auth : `Depends(get_current_user)` sur tous, RLS PG via `current_setting('app.current_account_id')`.

---

## Phase 3 — Implementation order (high level, voir tasks.md)

1. **Backend models** (`models/offer_match.py`, `models/match_alert_subscription.py`) + tests unit
2. **Migration Alembic 036** (round-trip + backfill) + test
3. **Schemas Pydantic v2** (`schemas/matching.py`) + tests
4. **Service `matching_service.py`** (core algorithm + UPSERT) + tests unit
5. **Service `alerts_service.py`** (subscribe/unsubscribe/notify) + tests
6. **Event listeners** (`hooks.py`) + tests
7. **Router REST** (`matching_router.py`) + tests integration + RLS
8. **Tools LangChain** (`matching_tools.py`) + tests + injection MODULE_TOOL_MAPPING
9. **Crons** (`recompute_stale_matches.py`, `notify_new_offer_matches.py`) + tests
10. **Frontend types + composable + store** + tests Vitest
11. **Composants Vue** (5 nouveaux) + tests Vitest
12. **Pages Vue** (3 nouvelles + extensions F06/F07) + tests
13. **Spec Playwright F14** (4 scénarios)
14. **Documentation `docs/matching-offers.md`**
15. **Conformity tests** (no fund_match writes, no skill mutation, ARIA, dark mode)

---

## Risks & Mitigations

| Risque | Mitigation |
|---|---|
| Recompute N matches × M projets coûteux | Cap dur 50 offres/projet/run, cache TTL 5 min sur list, cron batch 100/run |
| Score fonds vs intermédiaire diverge trop → confusion | Tooltip ARIA + `<BottleneckBadge>` explicite + section pédagogique sur la page comparateur |
| PME inondées d'alertes | Threshold `min_global_score=60` par défaut, toggle on/off par projet, idempotence `last_notified_at` |
| Backfill fund_matches échoue sur certains comptes | Skip + log WARN + UX inchangée (la PME peut recréer ses matches via recompute) |
| Event listener Project after_update boucle infinie | Garde `_BACKGROUND_TASKS` set + flag `_recompute_in_progress` ContextVar |
| Drop fund_matches casserait les pages legacy | Conservation 2 sprints + feature flag `USE_OFFER_MATCH_VIEW` côté frontend |

---

## Tracking

- ✅ Spec : `spec.md`
- ✅ Plan : ce fichier
- ✅ Data model : `data-model.md`
- ✅ Contracts : `contracts/openapi.yaml`
- ✅ Tasks : `tasks.md`
- ✅ Quickstart : `quickstart.md`
- ✅ Research : `research.md`
- ✅ Analyze : `analyze.md`
- ✅ Checklist : `checklists/quality.md`
