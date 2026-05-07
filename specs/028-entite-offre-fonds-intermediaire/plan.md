# Implementation Plan: F07 — Entité Offre = Couple Fonds × Intermédiaire

**Branch**: `feat/F07-entite-offre-fonds-intermediaire` (alias SpecKit `028-entite-offre-fonds-intermediaire`)
**Date**: 2026-05-07
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-entite-offre-fonds-intermediaire/spec.md`

## Summary

F07 introduit l'**Entité Offre** comme l'unité commercialement actionnable côté PME (Module 3.1.3 du brainstorming). Concrètement : (1) **enrichissement** des modèles `Fund` (instruments JSONB, theme JSONB, submission_mode enum, submission_calendar, source_id F01, version+valid_from+valid_to F04, publication_status, refactor min/max amounts en Money typed, renommage enum `fund_type` en `multilateral|bilateral|regional|national|private|carbon_marketplace`), `Intermediary` (required_documents JSONB structuré, fees_structured JSONB Money typed, processing_time_days_min/max, disbursement_time_days_min/max, submission_portal_url, success_rate, total_funded_volume Money typed, source_id, publication_status), `FundIntermediary` (accredited_from NOT NULL, accredited_to NULL, max_amount_per_fund Money typed, accreditation_source_id), `FundApplication` (offer_id transitoirement NULL puis NOT NULL post-backfill) ; (2) **création** d'une nouvelle table `offers` avec versioning F04 et calcul automatique des champs `effective_*` via le service `compute_effective_offer(fund_id, intermediary_id) → OfferDraft` (intersection critères, union documents dédupliquée, somme frais Money, somme délais) ; (3) **création** d'un intermédiaire singleton `code='DIRECT'` modélisant les fonds `access_type='direct'` comme des offres uniformes ; (4) **migration Alembic 028** réversible avec backfill : pour chaque paire `FundIntermediary` existante + chaque fonds `direct` créer une `Offer` (`is_active=false`, `publication_status='draft'`), puis lier toutes les `FundApplication` existantes via `offer_id` ; (5) **module backend** `app/modules/offers/` (router, service, calculator, schemas) exposant 6 endpoints REST (`GET /api/offers`, `GET /api/offers/{id}`, `GET /api/offers/comparator`, `POST /api/admin/offers`, `PATCH /api/admin/offers/{id}`, `POST /api/admin/offers/compute`) ; (6) **3 nouveaux tools LangChain** (`list_offers`, `get_offer`, `compare_offers_for_fund`) + extension du tool `create_fund_application` pour `offer_id` ; (7) **frontend** : 3 nouvelles pages (`/financing/offers/[id]`, `/financing/funds/[id]`, `/financing/intermediaries/[id]`) + refactor `/financing/index.vue` derrière feature flag `USE_OFFER_VIEW` (default `false`), 8 composants Vue (`OfferCard`, `FundCard`, `IntermediaryCard`, `OfferDetail`, `EffectiveCriteriaList`, `EffectiveDocumentsList`, `EffectiveFees`, `SubmissionModeBadge`) tous dark-mode + accessibilité ARIA ; (8) **cron quotidien** `backend/scripts/check_expired_accreditations.py` désactivant automatiquement les offres dont l'accréditation a expiré (`accredited_to < today`) avec journalisation audit_log F03 ; (9) **tests** : 80%+ couverture unit/integration backend + 80%+ couverture composants frontend + 4 scénarios E2E Playwright (`F07-entite-offre-fonds-intermediaire.spec.ts`).

## Technical Context

**Language/Version** : Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies** :
- Backend : FastAPI, SQLAlchemy async (asyncpg), Alembic, Pydantic v2, LangGraph + LangChain (tools), `app.core.money` (Money Pydantic + helpers), `app.modules.currency` (conversion XOF F04), `app.core.auditable` (mixin F03 — non utilisé sur Offer car catalogue admin, mais utilisé pour journaliser le cron via `audit_context`)
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4 (dark mode), DOMPurify (rendu sources cliquables), `marked` (descriptions enrichies)
**Storage** : PostgreSQL 16 + pgvector, Alembic pour migrations. Pas de stockage fichiers nouveau.
**Testing** :
- Backend : pytest, pytest-asyncio, pytest-cov (couverture ≥ 80 % sur `app/modules/offers/`, `app/models/financing.py` parties enrichies, `app/graph/tools/financing_tools.py` extensions)
- Frontend : Vitest + @vue/test-utils + @vitest/coverage-v8 + happy-dom (couverture ≥ 80 % sur les 8 nouveaux composants)
- E2E : Playwright (`@playwright/test`) — fichier `frontend/tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts` avec 4 scénarios
**Target Platform** : Linux server (Docker) + navigateurs modernes (Chrome/Firefox/Safari)
**Project Type** : Web application (backend FastAPI + frontend Nuxt 4 séparés)
**Performance Goals** :
- `compute_effective_offer` : < 500 ms p95 sur fond avec ≤ 20 critères, ≤ 10 documents, ≤ 5 frais structurés (SC-002)
- `GET /api/offers` (liste paginée 20 items) : < 300 ms p95 (filtres + tri par `success_rate`)
- `GET /api/offers/{id}` : < 200 ms p95 (1 SELECT avec joins fund + intermediary + source)
- `GET /api/offers/comparator?fund_id=X` : < 400 ms p95 pour ≤ 10 offres comparables
- Migration Alembic up/down/up : < 60 s sur base de dev avec 12 fonds + 14 intermédiaires + 50 paires + 3 applications
- Cron `check_expired_accreditations.py` : < 30 s sur 100 paires
**Constraints** :
- Multi-tenant strict (F02 invariant n°2) : tables `funds`, `intermediaries`, `fund_intermediaries`, `offers` sont **catalogue global** (pas de RLS par account_id), endpoints `/api/admin/offers/*` requièrent `is_admin=true` (helper F02). Table `fund_applications` reste multi-tenant.
- Sourçage F01 invariant n°1 : tous les nouveaux champs porteurs de chiffres ou critères (effective_criteria, effective_required_documents, effective_fees) DOIVENT être tracés via `source_id` (FK `sources.id` direct sur Offer + `source_id` dans chaque sous-objet JSONB).
- Audit log F03 invariant n°3 : `Fund/Intermediary/FundIntermediary/Offer` restent **EXEMPT** du mixin `Auditable` (catalogue admin only, cohérent avec policy actuelle). Le cron `check_expired_accreditations.py` insère explicitement des lignes `audit_log` via `app/core/audit_context.set_current_source_of_change('cron_accreditation_expiry')`.
- Versioning + Money typed F04 invariant n°4 : tous nouveaux montants sont Money typed (paire amount + currency Char(3)). VersioningMixin réutilisé sur `offers`. Money typed enregistré pour `funds.min/max_amount`, `fund_intermediaries.max_amount_per_fund`, `intermediaries.fees_structured.doc_fee_amount`, `intermediaries.total_funded_volume`, `offers.effective_fees.total_min/max`.
- RGPD F05 invariant n°5 : non concerné (pas de traitement de données PME sensibles, pas de PII collectée).
- Aucun secret hardcodé : URLs SMTP du cron, `EXPORT_URL_SIGNING_KEY` etc. → env vars.
- Aucun tool LLM ne mute le catalogue (invariant n°7) : `list_offers`, `get_offer`, `compare_offers_for_fund` sont read-only ; le tool `create_fund_application` mute `fund_applications` (table métier multi-tenant), pas le catalogue.
- Dark mode obligatoire : 8 nouveaux composants Vue + 3 nouvelles pages.
- Réutilisabilité composants : avant création, vérifier `frontend/app/components/ui/` ; extraire `<MoneyDisplay>` et `<DurationRange>` génériques si pattern apparaît > 2 fois.
- Français avec accents dans tout le contenu UI ; libellés audit_log en anglais snake_case (cohérent F03).
- Feature flag `USE_OFFER_VIEW` : env var lue dans `nuxt.config.ts` (`runtimeConfig.public.useOfferView`), default `false` ; pas de table `feature_flags` BDD pour MVP.
**Scale/Scope** :
- 1 nouvelle table BDD (`offers`) + ~20 colonnes ajoutées sur `funds`, ~15 sur `intermediaries`, ~5 sur `fund_intermediaries`, 1 sur `fund_applications`
- 1 migration Alembic réversible avec backfill
- 6 endpoints REST `/api/offers/*` + `/api/admin/offers/*`
- 3 nouveaux tools LangChain + 1 tool étendu (`create_fund_application`)
- 1 module backend nouveau `app/modules/offers/` (calculator, service, router, schemas, seed singleton)
- 1 cron Python (`backend/scripts/check_expired_accreditations.py`)
- 3 nouvelles pages Vue + 1 page refactorée
- 8 nouveaux composants Vue + extension `useFinancing.ts` + extension store `financing.ts`
- 1 spec E2E Playwright (4 scénarios)

## Constitution Check

Le repo n'a pas de `constitution.md` formelle ; les invariants ESG Mefali listés dans `.cc-orchestrator.md` jouent ce rôle.

| Invariant | Statut | Justification |
|---|---|---|
| 1 — Sourçage F01 obligatoire | ✓ Passe | Tous les champs porteurs de chiffres/critères sur Offer/Fund/Intermediary/FundIntermediary ont `source_id NOT NULL` ; le frontend affiche les sources cliquables sur `EffectiveCriteriaList`, `EffectiveDocumentsList`, `EffectiveFees`. |
| 2 — Multi-tenant strict F02 | ✓ Passe (catalogue admin) | Tables `funds`, `intermediaries`, `fund_intermediaries`, `offers` sont catalogue global (cohérent avec policy actuelle) ; `fund_applications` reste multi-tenant via `account_id` ; endpoints `/api/admin/*` protégés par helper `is_admin`. |
| 3 — Audit log append-only F03 | ✓ Passe | Catalogue exempt du mixin (cohérent F03), mais cron `check_expired_accreditations.py` journalise explicitement avec `audit_context`. |
| 4 — Versioning + Money typed F04 | ✓ Passe | `VersioningMixin` réutilisé sur `Offer` ; tous nouveaux montants Money typed ; legacy `min_amount_xof`/`max_amount_xof`/`typical_fees` conservés en deprecated 2 sprints (réversibilité). |
| 5 — RGPD F05 | N/A | Pas de PII PME collectée par F07. |
| 6 — Aucun secret hardcodé | ✓ Passe | `USE_OFFER_VIEW` env var ; pas de nouvelle clé. |
| 7 — Aucun tool LLM ne mute le catalogue | ✓ Passe | `list_offers`, `get_offer`, `compare_offers_for_fund` sont read-only ; mutations catalogue uniquement via endpoints `/api/admin/*`. |
| 8 — Dark mode obligatoire | ✓ Passe | 8 composants Vue avec variantes `dark:` Tailwind sur tous les éléments visuels. |
| 9 — Réutilisabilité composants | ✓ Passe | Avant création, audit de `components/ui/` ; extraction `<MoneyDisplay>` et `<DurationRange>` si pattern apparaît > 2 fois. |
| 10 — Français avec accents | ✓ Passe | Contenus UI en français (titres, descriptions, messages d'erreur, badges). |
| 11 — Tests E2E Playwright | ✓ Passe | `frontend/tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts` avec 4 scénarios exécutables. |
| 12 — Couverture tests ≥ 80 % | ✓ Passe | Cibles fixées : 80%+ backend (modules offers, financing extensions, tools), 80%+ frontend (8 nouveaux composants). |

**Conclusion** : Aucune violation. Pas de section « Complexity Tracking » nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/028-entite-offre-fonds-intermediaire/
├── spec.md              # /speckit.specify (created)
├── plan.md              # /speckit.plan (this file)
├── research.md          # Phase 0 (this command)
├── data-model.md        # Phase 1 (this command)
├── quickstart.md        # Phase 1 (this command)
├── contracts/           # Phase 1 (this command)
│   ├── openapi-offers.yaml
│   ├── openapi-admin-offers.yaml
│   └── tools-langchain.md
├── checklists/
│   └── requirements.md  # Quality checklist (created)
└── tasks.md             # /speckit.tasks (next command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── financing.py              # ENRICHED : Fund, Intermediary, FundIntermediary
│   │   ├── application.py            # ENRICHED : FundApplication (ajout offer_id)
│   │   └── offer.py                  # NEW : modèle SQLAlchemy Offer
│   ├── modules/
│   │   ├── offers/                   # NEW MODULE
│   │   │   ├── __init__.py
│   │   │   ├── calculator.py         # compute_effective_offer + OfferDraft Pydantic
│   │   │   ├── service.py            # CRUD Offer, transitions publication_status
│   │   │   ├── router.py             # endpoints /api/offers/*
│   │   │   ├── admin_router.py       # endpoints /api/admin/offers/*
│   │   │   ├── schemas.py            # Pydantic OfferRead, OfferCreate, OfferComparison, etc.
│   │   │   └── seed_direct.py        # seed intermédiaire singleton DIRECT (idempotent)
│   │   └── financing/
│   │       └── service.py            # EXTENDED : nouvelle méthode `list_offers_for_fund(fund_id)`
│   ├── graph/
│   │   └── tools/
│   │       └── financing_tools.py    # EXTENDED : 3 nouveaux tools + extension create_fund_application
│   └── main.py                       # PROTECTED ZONE : 1 ligne ajoutée (registration router)
├── alembic/
│   └── versions/
│       └── 028_offers_and_enrich_fund_intermediary.py  # NEW migration
├── scripts/
│   └── check_expired_accreditations.py  # NEW cron script
└── tests/
    ├── unit/
    │   ├── test_offer_calculator.py     # NEW : compute_effective_offer logic
    │   ├── test_offer_model.py          # NEW : invariants table offers
    │   ├── test_offer_service.py        # NEW : CRUD + transitions
    │   └── test_seed_direct.py          # NEW : seed singleton DIRECT idempotent
    ├── integration/
    │   ├── test_offers_router.py        # NEW : endpoints /api/offers/*
    │   ├── test_admin_offers_router.py  # NEW : endpoints /api/admin/offers/*
    │   ├── test_financing_tools_offers.py  # NEW : tools LangChain
    │   ├── test_check_expired_accreditations.py  # NEW : cron idempotent
    │   └── test_application_offer_id.py  # NEW : FundApplication offer_id behavior
    ├── migrations/
    │   └── test_alembic_028.py          # NEW : up/down/up + backfill
    └── security/
        └── test_offers_publication_filter.py  # NEW : SC-007 (0 fuite drafts)

frontend/
├── app/
│   ├── pages/
│   │   └── financing/
│   │       ├── index.vue              # REFACTORED : feature flag USE_OFFER_VIEW
│   │       ├── [id].vue               # PRESERVED : vue Fund actuelle (legacy)
│   │       ├── offers/
│   │       │   └── [offer_id].vue     # NEW : détail Offre (vue principale)
│   │       ├── funds/
│   │       │   └── [fund_id].vue      # NEW : détail Fonds + offres associées
│   │       └── intermediaries/
│   │           └── [intermediary_id].vue  # NEW : détail Intermédiaire + offres
│   ├── components/
│   │   └── financing/                 # NEW DIRECTORY
│   │       ├── OfferCard.vue
│   │       ├── FundCard.vue
│   │       ├── IntermediaryCard.vue
│   │       ├── OfferDetail.vue
│   │       ├── EffectiveCriteriaList.vue
│   │       ├── EffectiveDocumentsList.vue
│   │       ├── EffectiveFees.vue
│   │       └── SubmissionModeBadge.vue
│   ├── composables/
│   │   └── useFinancing.ts            # EXTENDED : listOffers, getOffer, compareOffersForFund
│   ├── stores/
│   │   └── financing.ts               # EXTENDED : state offers, getter offersForFund
│   └── types/
│       └── financing.ts               # EXTENDED : Offer, OfferComparison, OfferDraft, etc.
├── nuxt.config.ts                     # PROTECTED ZONE : ajout `runtimeConfig.public.useOfferView`
└── tests/
    ├── components/
    │   ├── OfferCard.spec.ts
    │   ├── OfferDetail.spec.ts
    │   ├── EffectiveCriteriaList.spec.ts
    │   ├── EffectiveDocumentsList.spec.ts
    │   ├── EffectiveFees.spec.ts
    │   ├── SubmissionModeBadge.spec.ts
    │   ├── FundCard.spec.ts
    │   └── IntermediaryCard.spec.ts
    └── e2e/
        └── F07-entite-offre-fonds-intermediaire.spec.ts  # NEW : 4 scénarios Playwright
```

**Structure Decision** : architecture web app monorepo (backend FastAPI Python 3.12 + frontend Nuxt 4 TypeScript), aligné avec la convention ESG Mefali existante. Le module `app/modules/offers/` est isolé (router, service, calculator, schemas) et n'introduit aucune dépendance circulaire. Le frontend respecte la convention `pages/` Nuxt 4 + `components/financing/` cohérent avec la structure existante. Aucune zone interdite (`main.py`, `nuxt.config.ts`) n'est modifiée hors stricte nécessité (1 ligne registration router + 1 ligne `runtimeConfig`).

## Phase 0 — Research

Voir [research.md](./research.md) pour les décisions techniques détaillées sur :
- Stratégie de migration backfill (réversibilité, idempotence, perf)
- Algorithme `compute_effective_offer` (intersection critères, union documents, somme frais Money typed)
- Stratégie de feature flag `USE_OFFER_VIEW` (env var vs table BDD)
- Choix d'inférence langue (heuristique pays vs liste explicite)
- Pattern API REST `/api/offers/comparator` vs filtres sur `/api/offers`
- Pattern singleton `Intermediary code='DIRECT'` (alternative considérée : `intermediary_id` nullable)
- Stratégie de tests intersection JSONB (PostgreSQL + SQLite)

## Phase 1 — Design

### Data Model

Voir [data-model.md](./data-model.md) pour le schéma BDD complet :
- Table `offers` (DDL complet : 16 colonnes + 4 colonnes versioning F04 + 5 indexes + 4 contraintes CHECK)
- Colonnes ajoutées sur `funds` (~10), `intermediaries` (~12), `fund_intermediaries` (~5), `fund_applications` (1)
- ENUM PostgreSQL `submission_mode_enum`, `publication_status_enum` (réutilisé F01)
- Renommage `fund_type_enum` (avec migration des valeurs existantes)
- Stratégie d'index : `offers(fund_id, intermediary_id, valid_to)`, `offers(theme @>)`, `offers(submission_mode)`, full-text sur `offers.name`, `offers(publication_status, is_active)` pour filtre API public
- Strategie indexes sur enrichissements : `funds(theme @>)`, `intermediaries(country)`, `fund_intermediaries(accredited_to)` pour cron

### API Contracts

Voir [contracts/openapi-offers.yaml](./contracts/openapi-offers.yaml) (endpoints publics) et [contracts/openapi-admin-offers.yaml](./contracts/openapi-admin-offers.yaml) (endpoints admin) pour les schémas OpenAPI complets.

Endpoints publics :
- `GET /api/offers` — liste filtrée + paginée + triée
- `GET /api/offers/{id}` — détail
- `GET /api/offers/comparator?fund_id=X` — comparateur multi-offres pour un fonds

Endpoints admin (rôle `admin` requis) :
- `GET /api/admin/offers?include_drafts=true` — liste complète
- `POST /api/admin/offers/compute?fund_id=X&intermediary_id=Y` — preview du calcul auto
- `POST /api/admin/offers` — création depuis draft édité
- `PATCH /api/admin/offers/{id}` — édition (transitions status incluses)

### Tools LangChain

Voir [contracts/tools-langchain.md](./contracts/tools-langchain.md) pour les schémas Pydantic des 3 nouveaux tools :
- `list_offers(filters: OfferFilters) → list[OfferSummary]`
- `get_offer(offer_id: UUID) → OfferDetail`
- `compare_offers_for_fund(fund_id: UUID) → list[OfferComparison]`
- Extension `create_fund_application(...)` : ajout paramètre optionnel `offer_id` (priorité sur `fund_id` + `intermediary_id` legacy si présent).

### Quickstart

Voir [quickstart.md](./quickstart.md) pour le guide opérationnel :
- Comment lancer la migration `028` localement
- Comment seeder l'intermédiaire singleton `DIRECT`
- Comment tester le calculator via curl ou pytest
- Comment activer `USE_OFFER_VIEW=true` localement
- Comment exécuter le cron `check_expired_accreditations.py`

## Phase 2 — Tasks

Voir [tasks.md](./tasks.md) (généré par `/speckit.tasks`).

Note importante : `tasks.md` DOIT contenir des tests E2E **Playwright** exécutables dans `frontend/tests/e2e/F07-entite-offre-fonds-intermediaire.spec.ts` couvrant les 4 scénarios :
1. Admin crée offre via calcul auto → publication → visible côté PME
2. PME consulte 2 offres GCF distinctes (BOAD + UNDP) et les compare côte-à-côte
3. PME tente d'accéder à `/api/admin/offers?include_drafts=true` → 403 ; vérification que le filtrage `publication_status='published'` est strict
4. Cron `check_expired_accreditations.py` désactive offre expirée → invisible côté PME (re-fetch après cron)

## Risks & Mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Migration backfill crée des offres « fantômes » non commercialisables | Moyenne | Moyen | `is_active=false` + `publication_status='draft'` par défaut ; admin valide manuellement avant publication. |
| Calcul `intersection(criteria)` faux car schémas critères non alignés (JSON libre actuel) | Élevée | Moyen | Présenter le calcul comme draft éditable ; documenter les conventions JSONB attendues dans data-model.md ; recalcul possible après F01 (couche `Indicator/Criterion` typée future). |
| `fund_type` enum renommage casse les fonds existants | Moyenne | Élevé | Migration transactionnelle qui crée le nouveau type, migre les valeurs (`international` → `multilateral`, etc.), drop l'ancien type. Test up/down/up couvre la régression. |
| Pages frontend `pages/financing/[id].vue` actuelles cassent | Moyenne | Moyen | Feature flag `USE_OFFER_VIEW=false` par défaut ; pages legacy préservées intactes. Bascule effective post-F14 (feature ultérieure). |
| `accepted_languages` non respecté par F15 (générateur dossier) | Moyenne | Élevé | Documenter explicitement dans la spec F07 que F15 lit `offer.accepted_languages` ; tooltips UI. Test E2E couvrira la valeur stockée. |
| Cron expiration `check_expired_accreditations.py` non lancé en prod | Élevée | Élevé | Documenter l'exécution manuelle ou via orchestrateur externe ; F19 introduira un cron dispatcher dédié post-MVP. Test E2E #4 couvre le comportement. |
| Conversion devises Money typed échoue si `app.modules.currency` absent | Faible | Élevé | F04 livré avant F07 (vérifié) ; tests mock le module currency. Fallback : warning dans `notes` si conversion impossible. |
| `Source` non `verified` lors de publication d'offre | Moyenne | Moyen | Endpoint `PATCH /api/admin/offers/{id}` retourne 422 explicite ; UI back-office affiche un message explicatif et un lien vers la source à vérifier. |

## Dependencies on other features

- **F01 (Sources catalogue)** : `verified` requis pour publication ; FK `source_id` sur 4 tables. **Confirmé livré** (migration 020).
- **F02 (Multi-tenant + roles)** : helper `is_admin` requis. **Confirmé livré** (migration 019).
- **F03 (Audit log)** : journalisation cron via `audit_context`. **Confirmé livré** (migration 021).
- **F04 (Versioning + Money typed)** : `VersioningMixin`, `Money`, `app.modules.currency`. **Confirmé livré** (migration 022).
- **F06 (Entité Project vert)** : `FundApplication.project_id` non modifié. **Confirmé livré** (migration 025).

Toutes les dépendances sont mergées sur main au moment du démarrage de F07. Aucun blocage.

## Out of scope (post-MVP)

- Marketplace d'offres tierces (consultants accréditants leurs propres offres)
- Versionning très fin par section d'une offre (overlay diff visuel)
- A/B testing de templates par offre
- API publique pour découvrir les offres ouvertes (licence à clarifier)
- Cron dispatcher dédié (F19, post-MVP)
- Bascule effective de `USE_OFFER_VIEW=true` en production (feature ultérieure post-F14)
- Frontend back-office admin pour création/édition d'offres (F09, post-MVP) — pour MVP F07, l'admin utilise les endpoints REST directement (curl ou outil API).

## Complexity Tracking

> Aucune violation des invariants ESG Mefali. Pas de justification nécessaire.
