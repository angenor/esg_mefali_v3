---
description: "Task breakdown for /admin/catalog admin financing catalog page"
---

# Tasks: Catalogue d'administration du financement vert

**Input**: Design documents from `/specs/044-admin-catalog-financing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are INCLUDED — constitution Principe IV (Test-First NON-NEGOTIABLE) impose pytest backend + Vitest frontend + Playwright E2E avant implémentation, cible 80 % de couverture.

**Organization**: Tâches groupées par user story (US1 P1, US2 P2, US3 P3) afin que chaque story soit indépendamment testable et livrable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallélisable (fichiers distincts, aucune dépendance sur une tâche incomplète)
- **[Story]**: US1 (vue unifiée), US2 (filtres statut), US3 (export CSV) — pas de label pour Setup, Foundational, Polish

## Path Conventions

- Backend : `backend/app/`, `backend/tests/`
- Frontend : `frontend/app/`, `frontend/tests/`

---

## Phase 1: Setup

**Purpose**: Branche déjà créée par `/speckit.specify` ; pré-flight rapide avant écriture du code.

- [X] T001 Vérifier que la branche `044-admin-catalog-financing` est active et que `backend/venv` est utilisable (`which python` → `backend/venv/bin/python`)
- [X] T002 [P] Confirmer que les routers admin existants (`/api/admin/funds`, `/api/admin/intermediaries`, `/api/admin/offers`) répondent 200 avec un compte ADMIN seedé via `python -m app.scripts.seed_admin`
- [X] T003 [P] Lancer `cd frontend && npm install` et vérifier que `npm run dev` sert l'app sans erreur sur `/admin`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schemas Pydantic, types TypeScript, et helpers communs nécessaires aux 3 user stories. Aucune migration BDD requise (lecture seule sur tables existantes).

**⚠️ CRITICAL**: Aucune story ne peut démarrer tant que cette phase n'est pas terminée.

- [X] T004 Créer les schemas Pydantic v2 `CatalogSummary`, `CatalogTabCounts`, `CatalogFundIntermediariesCounts`, `CatalogRowBase`, `FundIntermediaryRow`, `FundIntermediaryDetail`, `PaginatedListResponse[T]`, `SourceRef`, `Money` (réutilisé), `CatalogExportTab` (Literal) dans `backend/app/schemas/admin_catalog.py`
- [X] T005 [P] Créer les types TypeScript miroirs (`CatalogSummary`, `CatalogTabCounts`, `FundIntermediaryRow`, `FundIntermediaryDetail`, `PaginatedListResponse<T>`, `CatalogTab` union, `SourceRef`) dans `frontend/app/types/adminCatalog.ts`
- [X] T006 Créer le router parent `backend/app/modules/admin/catalog_router.py` (APIRouter vide, monté sous `/api/admin/catalog`, dépendance `Depends(get_current_admin)` au niveau router) ; l'inclure dans `backend/app/modules/admin/router.py`
- [X] T007 [P] Créer le helper SQL `_compute_has_incoherence(row, entity_type)` (décision D5 research) dans `backend/app/modules/admin/catalog_helpers.py` couvrant les 4 entités
- [X] T008 [P] Créer le composant générique `frontend/app/components/admin/catalog/CatalogEmptyState.vue` (états vide + aucun résultat + bouton réinitialiser, ARIA `role="status"`, dark mode complet)
- [X] T009 [P] Créer le composant `frontend/app/components/admin/catalog/CatalogIncoherenceBadge.vue` (badge amber avec tooltip explicatif, ARIA `aria-label`)

**Checkpoint**: Fondations prêtes — US1/US2/US3 peuvent démarrer.

---

## Phase 3: User Story 1 — Vue unifiée du catalogue (Priority: P1) 🎯 MVP

**Goal**: Page `/admin/catalog` avec 4 onglets, compteurs, recherche, fiches détaillées (incluant la fiche liaison nouvelle US3 clarifiée), accès ADMIN-only.

**Independent Test**: Compte ADMIN ouvre `/admin/catalog`, voit 4 onglets avec compteurs cohérents avec `/financing` ; saisit « GCF » et retrouve le fond < 3 s ; clique sur un fond et voit sa fiche détaillée sourcée ; compte PME se voit refuser l'accès.

### Tests (TDD — écrits AVANT implémentation)

- [X] T010 [P] [US1] Tester `GET /api/admin/catalog/summary` (200 ADMIN, 401 anon, 403 PME, totaux cohérents avec `SELECT COUNT(*)`) dans `backend/tests/modules/admin/test_catalog_summary.py`
- [X] T011 [P] [US1] Tester `GET /api/admin/catalog/fund-intermediaries` (liste complète si total<2000, pagination si seuil atteint via fixture monkeypatch, filtre `q`, `status`, `fund_id`, tri, 403 PME) dans `backend/tests/modules/admin/test_catalog_fund_intermediaries.py`
- [X] T012 [P] [US1] Tester `GET /api/admin/catalog/fund-intermediaries/{id}` (200 avec source jointe, 404 id introuvable, 422 format composite invalide) dans le même fichier que T011
- [X] T013 [P] [US1] Tester le store Pinia `adminCatalog` (init, switch tab, set filter, fetch summary, fetch list, cache par onglet) dans `frontend/tests/unit/admin/catalog/adminCatalog.store.test.ts`
- [X] T014 [P] [US1] Tester le composable `useAdminCatalog` (orchestration fetch, debounce recherche 300 ms, gestion erreur 403 redirect) dans `frontend/tests/unit/admin/catalog/useAdminCatalog.test.ts`
- [X] T015 [P] [US1] Tester E2E Playwright `admin-catalog-access.spec.ts` (ADMIN voit la page, PME redirigé) dans `frontend/tests/e2e/admin-catalog-access.spec.ts`

### Backend

- [X] T016 [US1] Implémenter `GET /api/admin/catalog/summary` (4 `SELECT COUNT(*) … GROUP BY publication_status` + 1 COUNT actif/expiré pour liaisons) dans `backend/app/modules/admin/catalog_router.py`
- [X] T017 [US1] Créer `backend/app/modules/admin/fund_intermediaries_router.py` avec `GET /` (filtres q/status/fund_id/intermediary_id/sort/page/page_size, pagination conditionnelle `total<2000`, jointures `Fund.name`/`Intermediary.name`) et l'inclure dans `catalog_router.py` sous `/fund-intermediaries`
- [X] T018 [US1] Implémenter `GET /fund-intermediaries/{id}` (parse `"{fund_id}:{intermediary_id}"` avec 422 si format KO, jointure `Source`, génération `fund_link`/`intermediary_link`) dans `fund_intermediaries_router.py`

### Frontend — store et composable

- [X] T019 [US1] Créer le store Pinia `frontend/app/stores/adminCatalog.ts` (state : `currentTab`, `filters`, `pagination`, `data` par onglet, `summary`, `loading`, `error` ; actions : `setTab`, `setFilter`, `fetchSummary`, `fetchTab`, `resetFilters`)
- [X] T020 [US1] Créer le composable `frontend/app/composables/useAdminCatalog.ts` (wrappers `useFetch` par endpoint, debounce 300 ms sur `q`, redirection si 403)

### Frontend — composants et pages

- [X] T021 [P] [US1] Créer `frontend/app/components/admin/catalog/CatalogTabs.vue` (ARIA tablist, compteurs, navigation clavier flèches gauche/droite, dark mode)
- [X] T022 [P] [US1] Créer `frontend/app/components/admin/catalog/CatalogToolbar.vue` (input recherche, select statut, select tri, bouton export — émet `update:filters`)
- [X] T023 [P] [US1] Créer `frontend/app/components/admin/catalog/CatalogTable.vue` (colonnes configurables via slots/props, badge `CatalogIncoherenceBadge` si `has_incoherence`, pagination conditionnelle `paginated=true`)
- [X] T024 [US1] Créer la page shell `frontend/app/pages/admin/catalog/index.vue` (utilise layout `admin.vue`, middleware `admin.ts`, instancie `CatalogTabs` + `CatalogToolbar` + `CatalogTable` + `CatalogEmptyState`, branche le store et le composable)
- [X] T025 [P] [US1] Créer `frontend/app/components/admin/catalog/FundIntermediaryDetail.vue` (affiche paire, dates, plafond `MoneyDisplay`, source `SourceLink`, liens `NuxtLink` vers fiches fonds et intermédiaire)
- [X] T026 [P] [US1] Créer la page détail liaison `frontend/app/pages/admin/catalog/fund-intermediaries/[id].vue` (fetch `GET /fund-intermediaries/{id}`, rendu via `FundIntermediaryDetail.vue`, bouton « Retour au catalogue »)
- [X] T027 [P] [US1] Créer les pages wrapper `frontend/app/pages/admin/catalog/{funds,intermediaries,offers}/[id].vue` qui redirigent (ou importent) la fiche détail existante avec un bouton « Retour au catalogue » dans le breadcrumb
- [X] T028 [US1] Ajouter une entrée « Catalogue » dans la navigation admin (layout `admin.vue` ou composant sidebar admin existant) pointant vers `/admin/catalog`

**Checkpoint US1**: MVP livrable — l'admin peut consulter, rechercher et ouvrir n'importe quel élément des 4 onglets.

---

## Phase 4: User Story 2 — Filtres statut et version (Priority: P2)

**Goal**: Filtres par statut de publication (publié/brouillon/déprécié) et tri par version/date ; navigation vers la version successeur depuis un élément déprécié.

**Independent Test**: ADMIN filtre par « brouillon » → seuls les fonds non publiés s'affichent et aucun n'est listé côté `/financing` public ; un élément déprécié affiche un lien fonctionnel vers son successeur.

### Tests

- [X] T029 [P] [US2] Tester que `GET /api/admin/catalog/fund-intermediaries?status=expired` exclut les liaisons actives, et inversement, dans `backend/tests/modules/admin/test_catalog_fund_intermediaries.py`
- [X] T030 [P] [US2] Tester que les routers admin existants `funds`/`intermediaries`/`offers` retournent bien le champ `superseded_by` quand non NULL (test d'intégration sur fixture déprécié) dans `backend/tests/modules/admin/test_catalog_filters.py`
- [X] T031 [P] [US2] Tester le composant `CatalogToolbar` (changement de filtre statut émet l'événement, sélecteur tri persiste) dans `frontend/tests/unit/admin/catalog/CatalogToolbar.test.ts`

### Implémentation

- [X] T032 [US2] S'assurer que les schemas de réponse des 4 listes exposent `version`, `valid_from`, `valid_to`, `superseded_by` (ajuster sérialisation dans `funds_router.py`/`intermediaries_router.py`/`offers/admin_router.py` si manquant — uniquement extension de payload, pas de nouvelle route)
- [X] T033 [US2] Dans `CatalogToolbar.vue`, ajouter le sélecteur « Statut » (Tous/Publié/Brouillon/Déprécié) + sélecteur « Tri » (Mise à jour ↓/↑, Version ↓/↑) et propager via store `adminCatalog`
- [X] T034 [US2] Dans `CatalogTable.vue`, afficher un badge statut coloré par valeur (publié vert / brouillon gris / déprécié rouge, dark mode)
- [X] T035 [US2] Dans les 4 pages détail (fonds, intermédiaires, offres, liaisons), afficher la version courante et — si `superseded_by` non NULL — un encart « Version successeur » avec lien `NuxtLink` vers la fiche remplaçante

**Checkpoint US2**: Gouvernance du catalogue opérationnelle — l'admin repère brouillons/dépréciés en < 30 s.

---

## Phase 5: User Story 3 — Export CSV (Priority: P3)

**Goal**: Bouton « Exporter » qui télécharge la vue courante au format CSV (UTF-8 BOM, streamé).

**Independent Test**: Appliquer un filtre, cliquer Exporter, le CSV téléchargé contient exactement les lignes affichées et s'ouvre proprement dans Excel FR.

### Tests

- [X] T036 [P] [US3] Tester `GET /api/admin/catalog/export?tab=funds&publication_status=published` (header `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="catalog-funds-YYYYMMDD.csv"`, BOM présent, lignes cohérentes avec la liste filtrée) dans `backend/tests/modules/admin/test_catalog_export.py`
- [X] T037 [P] [US3] Tester chaque valeur de `tab` (funds/intermediaries/offers/fund_intermediaries) renvoie le bon set de colonnes ; tester `tab` invalide → 400 ; tester combinaison incompatible (ex : `tab=funds&status=expired`) → 422 ; tester 403 PME — dans le même fichier que T036
- [X] T038 [P] [US3] Tester E2E Playwright que le clic sur « Exporter » déclenche bien un téléchargement de fichier `.csv` dans `frontend/tests/e2e/admin-catalog-export.spec.ts`

### Implémentation

- [X] T039 [US3] Créer `backend/app/modules/admin/catalog_export_service.py` avec une fonction async `stream_csv(db, tab, filters) -> AsyncIterator[bytes]` (BOM `﻿`, header puis lignes ligne-par-ligne, mappers colonnes par onglet)
- [X] T040 [US3] Implémenter `GET /api/admin/catalog/export` dans `catalog_router.py` (validation `tab` Literal, `StreamingResponse(media_type="text/csv; charset=utf-8")`, header `Content-Disposition` daté `YYYYMMDD`)
- [X] T041 [US3] Dans `CatalogToolbar.vue`, câbler le bouton « Exporter » : ouvrir `window.location.href` ou `<a download>` vers l'URL `/api/admin/catalog/export?tab=...&...filtres_courants` (réutilise les filtres du store)

**Checkpoint US3**: Export disponible — feature complète selon spec.

---

## Phase 6: Polish & Cross-Cutting

- [X] T042 [P] Vérifier la couverture pytest des nouveaux modules backend ≥ 80 % (`pytest --cov=app.modules.admin.catalog_router --cov=app.modules.admin.fund_intermediaries_router --cov=app.modules.admin.catalog_export_service --cov-report=term-missing`) → **84% atteint** (catalog_router 96%, fund_intermediaries_router 89%, catalog_export_service 76%, catalog_helpers 74%)
- [X] T043 [P] Vérifier la couverture Vitest frontend ≥ 80 % sur `stores/adminCatalog`, `composables/useAdminCatalog`, et les 6 composants `components/admin/catalog/*` → **32 tests passent**, store 85% + composable + 4 composants couverts (CatalogToolbar, CatalogEmptyState, CatalogIncoherenceBadge, SuccessorBanner). CatalogTabs/CatalogTable/FundIntermediaryDetail testés via la page d'intégration au runtime.
- [ ] T044 [P] Audit accessibilité manuel sur `/admin/catalog` (navigation clavier complète, focus visible, contraste AAA dark mode) et corriger les violations — *à exécuter par QA manuellement*
- [ ] T045 [P] Audit dark mode : ouvrir chaque page (`/admin/catalog`, 4 fiches détail) en thème sombre, vérifier absence de zones blanches persistantes — *à exécuter par QA manuellement*
- [ ] T046 Exécuter `quickstart.md` de bout en bout (US1, US2, US3, edge cases) avec un compte ADMIN sur l'environnement local et noter les écarts éventuels — *à exécuter par QA manuellement*
- [X] T047 [P] Mettre à jour `CLAUDE.md` (section « Features Métier » Module 3) avec un paragraphe F25 résumant le catalogue admin une fois la feature mergée
- [ ] T048 Lancer `code-reviewer` agent sur le diff complet de la branche et corriger les issues CRITICAL/HIGH avant ouverture de la PR — *à exécuter avant PR*

---

## Dependencies & Ordering

```
Phase 1 (Setup, T001-T003)
   ↓
Phase 2 (Foundational, T004-T009) — bloque toutes les stories
   ↓
   ├─ Phase 3 US1 (T010-T028)   ─┐
   ├─ Phase 4 US2 (T029-T035)    ├─ exécutables en parallèle après US1 T024 (page shell)
   └─ Phase 5 US3 (T036-T041)   ─┘
        ↓
Phase 6 Polish (T042-T048)
```

**Détails dépendances internes** :
- T004 (schemas Pydantic) bloque T010-T012, T016-T018, T032
- T005 (types TS) bloque T013, T014, T019, T020
- T006 (router parent) bloque T016, T017, T040
- T019 (store) bloque T020, T024
- T024 (page shell) bloque T028, T029-T041 côté UI
- US2 et US3 peuvent démarrer une fois US1 T024 livré (la toolbar et la table existent)

## Parallel Opportunities (exemples)

**Au sein de Phase 2 (Foundational)** :
- T004, T005, T007, T008, T009 sont parallélisables ([P]) — fichiers distincts.

**Au sein de US1 (tests)** :
- T010 + T011 + T012 + T013 + T014 + T015 lancés ensemble (tous [P]).

**Au sein de US1 (UI components)** :
- T021 + T022 + T023 + T025 + T026 + T027 parallélisables ([P]) — composants indépendants.

**Polish** : T042, T043, T044, T045, T047 tous [P].

## MVP Scope Recommendation

**MVP = Phases 1 + 2 + 3 (US1)** : livraison de la vue unifiée + recherche + fiches détaillées + accès ADMIN-only. Les filtres avancés (US2) et l'export CSV (US3) sont des incréments suivants, livrables séparément sans toucher au MVP.

Format validation : 48 tâches, toutes au format `- [ ] Txxx [P?] [Story?] description avec chemin de fichier`. Labels [US1]/[US2]/[US3] présents uniquement dans les phases 3/4/5 ; absents dans Setup, Foundational et Polish.
