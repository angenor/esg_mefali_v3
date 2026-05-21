# Implementation Plan: Catalogue d'administration du financement vert

**Branch**: `044-admin-catalog-financing` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/044-admin-catalog-financing/spec.md`

## Summary

Créer une page `/admin/catalog` en lecture seule qui regroupe en 4 onglets les éléments du catalogue de financement vert (Fonds, Intermédiaires, Offres effectives, Liaisons fonds × intermédiaires) avec recherche, filtres (statut de publication, type), tri, fiches détaillées sourcées (F01), pagination automatique au-delà de 2 000 éléments, et export CSV de la vue courante. Aucune migration BDD : les entités existent déjà (F06/F07) et 3 des 4 onglets sont déjà servis par les routers admin existants (`/api/admin/funds`, `/api/admin/intermediaries`, `/api/admin/offers`). La feature ajoute (1) un router admin pour les liaisons fonds × intermédiaires, (2) un endpoint d'export CSV unifié, et (3) la page frontend agrégatrice + un store/composable dédié.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy async, Pydantic v2 (backend) ; Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS (frontend)
**Storage**: PostgreSQL 16 (tables existantes `funds`, `intermediaries`, `offers`, `fund_intermediaries`, `sources`) ; aucune nouvelle table ni migration
**Testing**: pytest + httpx AsyncClient (backend), Vitest (unit/composables), Playwright (E2E frontend)
**Target Platform**: Web admin (desktop prioritaire, responsive ≥ 1024 px) ; mode sombre obligatoire
**Project Type**: Web application (backend FastAPI + frontend Nuxt 4 existants)
**Performance Goals**: Chargement initial onglet < 2 s pour 1 000 éléments ; filtrage côté serveur < 500 ms p95 ; pagination 50/page au-delà de 2 000 éléments
**Constraints**: Lecture seule (aucune mutation), authentification ADMIN obligatoire (middleware existant), parité dark mode, accents français
**Scale/Scope**: Volume actuel < 100 éléments par catégorie ; cible 1 000 / catégorie d'ici 2 ans ; bascule pagination déclenchée à 2 000

## Constitution Check

*Évaluation contre `.specify/memory/constitution.md` (v1.0.0)*

| Principe | Statut | Justification |
|---|---|---|
| I. Francophone-First | PASS | UI 100 % FR avec accents ; identifiants code EN ; outil admin sans contexte PME francophone à étendre |
| II. Architecture Modulaire | PASS | Sous-module `app/modules/admin/catalog_*` réutilisant exclusivement les modèles `financing` et `offers` ; frontières claires |
| III. Conversation-Driven UX | N/A | Outil d'administration interne hors parcours conversationnel utilisateur PME |
| IV. Test-First (NON-NEGOTIABLE) | PASS | Tests backend pytest écrits AVANT routers, tests Vitest AVANT composants/store ; Playwright E2E pour parcours admin critique ; cible 80 % |
| V. Sécurité & Données | PASS | Accès via `get_current_admin` existant ; RLS admin policy F02 déjà active ; aucune écriture, aucun secret |
| VI. Inclusivité & Accessibilité | PARTIAL | Public admin uniquement (pas de PME peu numérique). Cible desktop ≥ 1024 px acceptable. Labels ARIA tabs, navigation clavier, contraste dark mode respectés |
| VII. Simplicité | PASS | Réutilise 90 % des endpoints existants ; 1 router additionnel + 1 endpoint export ; aucune migration |

**Gate Result**: PASS — aucun écart non justifié.

## Project Structure

### Documentation (this feature)

```text
specs/044-admin-catalog-financing/
├── plan.md              # Ce fichier
├── spec.md              # Spécification fonctionnelle
├── research.md          # Phase 0 — décisions techniques
├── data-model.md        # Phase 1 — entités lues (lecture seule)
├── quickstart.md        # Phase 1 — parcours de validation manuelle
├── contracts/
│   ├── admin-catalog-fund-intermediaries.openapi.yaml
│   └── admin-catalog-export.openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md             # Généré par /speckit.tasks (hors-scope ici)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   └── admin/
│   │       ├── catalog_router.py             # NEW — orchestrateur /api/admin/catalog/*
│   │       ├── fund_intermediaries_router.py # NEW — liste + détail des liaisons
│   │       ├── catalog_export_service.py     # NEW — sérialisation CSV par onglet
│   │       └── router.py                     # MODIFIED — include catalog_router
│   └── schemas/
│       └── admin_catalog.py                  # NEW — DTO Pydantic v2 (summary, liaison row/detail, export request)
└── tests/
    └── modules/admin/
        ├── test_catalog_fund_intermediaries.py  # NEW
        ├── test_catalog_summary.py              # NEW
        └── test_catalog_export.py               # NEW

frontend/
├── app/
│   ├── pages/admin/catalog/
│   │   ├── index.vue                         # NEW — shell + 4 onglets
│   │   ├── funds/[id].vue                    # NEW — fiche détail fond (réutilise admin/funds/[id].vue)
│   │   ├── intermediaries/[id].vue           # NEW — fiche détail intermédiaire
│   │   ├── offers/[id].vue                   # NEW — fiche détail offre
│   │   └── fund-intermediaries/[id].vue      # NEW — fiche détail liaison
│   ├── components/admin/catalog/
│   │   ├── CatalogTabs.vue                   # NEW — onglets + compteurs (ARIA tablist)
│   │   ├── CatalogToolbar.vue                # NEW — recherche + filtres + tri + bouton export
│   │   ├── CatalogTable.vue                  # NEW — tableau générique (pagination automatique)
│   │   ├── CatalogEmptyState.vue             # NEW — états vide + aucun résultat
│   │   ├── CatalogIncoherenceBadge.vue       # NEW — badge « Incohérence détectée »
│   │   └── FundIntermediaryDetail.vue        # NEW — bloc fiche liaison
│   ├── composables/
│   │   └── useAdminCatalog.ts                # NEW — fetch + état par onglet
│   ├── stores/
│   │   └── adminCatalog.ts                   # NEW — Pinia : tab courante, filtres, pagination, cache léger
│   └── types/
│       └── adminCatalog.ts                   # NEW — miroir TypeScript des DTO Pydantic
└── tests/
    └── unit/admin/catalog/
        ├── adminCatalog.store.spec.ts        # NEW
        └── useAdminCatalog.spec.ts           # NEW
```

**Structure Decision**: Application web existante (backend FastAPI + frontend Nuxt 4). La feature s'insère dans les modules existants (`backend/app/modules/admin/`, `frontend/app/pages/admin/`) sans création de top-level. Réutilisation maximale des composants visuels admin déjà en place (`/admin/funds/[id].vue`, `SourceLink`, `MoneyDisplay`, `RoleBadge`).

## Complexity Tracking

> Aucun écart constitutionnel à justifier — section non remplie.
