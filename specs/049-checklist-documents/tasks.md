---
description: "Task list — Fourniture des documents de la checklist (V1)"
---

# Tasks: Fourniture des documents de la checklist d'un dossier de candidature (V1)

**Input**: Design documents from `/specs/049-checklist-documents/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUS et OBLIGATOIRES — la Constitution IV (Test-First) est non-négociable (couverture ≥ 80 %). Les tests sont écrits AVANT l'implémentation et DOIVENT échouer d'abord.

**Organization**: tâches groupées par user story (P1→P4) pour livraison incrémentale. MVP = User Story 1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallélisable (fichiers différents, sans dépendance non satisfaite)
- **[Story]**: US1..US5 (phases user story uniquement)

## Path Conventions (web — monolithe modulaire)

- Backend : `backend/app/...`, tests `backend/tests/...`
- Frontend : `frontend/app/...`, tests `frontend/test/...`, E2E `frontend/e2e/...`
- **Aucune migration Alembic** (réutilisation du champ JSON `checklist`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: préparer les fichiers de tests et confirmer l'absence de migration.

- [X] T001 [P] Créer les squelettes de tests backend `backend/tests/test_applications/test_checklist_documents.py` et `backend/tests/test_documents/test_delete_cleanup.py` (imports, fixtures dossier + document du **même compte**, marqueurs pytest-asyncio)
- [X] T002 [P] Créer les squelettes de tests frontend `frontend/test/composables/useApplications.checklist.spec.ts`, `frontend/test/components/ChecklistItemRow.spec.ts`, `frontend/test/components/DocumentPicker.spec.ts` et `frontend/e2e/checklist-documents.spec.ts`
- [X] T003 Vérifier dans `backend/app/models/application.py` que le champ `checklist` (JSON) et la forme d'item (`key,name,status,document_id,required_by`) couvrent le besoin sans changement de schéma (confirmer : aucune migration)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: schémas + chemin de **lecture** enrichi (statut effectif, sous-objet `document`, progression) + contrats de types frontend. Partagé par toutes les stories.

**⚠️ CRITICAL**: aucune story ne peut être complétée avant cette phase.

- [X] T004 [P] Backend : ajouter les schémas `AttachDocumentRequest`, `DocumentRef`, `ChecklistItemOut` (enrichi : `document`, statut effectif) et `ChecklistProgress` dans `backend/app/modules/applications/schemas.py`
- [X] T005 Backend (TEST FIRST) : écrire dans `backend/tests/test_applications/test_checklist_documents.py` les tests de sérialisation enrichie — item avec `document_id` valide → `status="provided"` + `document` peuplé (nom de fichier) ; item avec `document_id` pointant un document supprimé → `status="missing"`, `document=null` (statut effectif) ; `checklist_progress` = compte exact ; checklist vide → `total=0`. (DOIVENT échouer)
- [X] T006 Backend : implémenter le helper de sérialisation (chargement **groupé** des documents référencés du compte, calcul du statut effectif + sous-objet `document`) et `compute_checklist_progress` dans `backend/app/modules/applications/service.py`
- [X] T007 Backend : brancher la sérialisation enrichie + `checklist_progress` dans la réponse détail `GET /api/applications/{id}` et `GET /api/applications/{id}/checklist` dans `backend/app/modules/applications/router.py`
- [X] T008 [P] Frontend : étendre l'interface `ChecklistItem` (+ `document?: { id; original_filename; mime_type; status } | null`) et `ApplicationDetail` (+ `checklist_progress`) dans `frontend/app/stores/applications.ts` ; ajouter les mutators locaux `setChecklistItem(itemKey, item)` et `setChecklistProgress(progress)`

**Checkpoint**: chemin de lecture enrichi prêt — les stories peuvent démarrer.

---

## Phase 3: User Story 1 - Téléverser un fichier sur un item manquant (Priority: P1) 🎯 MVP

**Goal**: depuis un item « Manquant », téléverser un fichier ; l'item passe « Fourni » et affiche le nom du fichier.

**Independent Test**: ouvrir un dossier, téléverser un PDF valide sur un item « Manquant » → item « Fourni » + nom affiché + progression incrémentée.

### Tests (TEST FIRST — DOIVENT échouer) ⚠️

- [X] T009 [P] [US1] Backend : tests du `PUT …/checklist/{item_key}/document` dans `backend/tests/test_applications/test_checklist_documents.py` — nominal (missing→provided, `document` peuplé, progression) ; **document d'un autre compte → 403** ; `item_key` inconnu → 404 ; `application_id` inconnu/autre utilisateur → 404 ; body sans `document_id` → 422 ; **1 ligne d'audit créée** ; les **autres items inchangés** (atomicité FR-021) ; **non-écrasement** : un second rattachement sur un autre item (relecture après commit, verrou `with_for_update()`) préserve le premier
- [X] T010 [P] [US1] Frontend : tests `useApplications.attachDocument` (succès → MAJ store) dans `frontend/test/composables/useApplications.checklist.spec.ts` et test `ChecklistItemRow` (upload valide → émet attach, affiche le nom ; fichier invalide → message d'erreur, pas d'attach) dans `frontend/test/components/ChecklistItemRow.spec.ts`

### Implementation

- [X] T011 [US1] Backend : implémenter `attach_checklist_document(db, application, item_key, document_id)` (verrou `with_for_update()` sur le dossier → relire `checklist`, validation `account_id` == dossier, existence item/document, set `document_id`+`status="provided"` sur le seul item ciblé, flush) dans `backend/app/modules/applications/service.py`
- [X] T012 [US1] Backend : ajouter l'endpoint `PUT /api/applications/{application_id}/checklist/{item_key}/document` (auth, `AttachDocumentRequest`, réponse `{ item enrichi, checklist_progress }`, codes 403/404/422 du contrat) dans `backend/app/modules/applications/router.py`
- [X] T013 [P] [US1] Frontend : `attachDocument(applicationId, itemKey, documentId)` dans `frontend/app/composables/useApplications.ts` (PUT, MAJ store via `setChecklistItem`/`setChecklistProgress`, gestion erreur FR)
- [X] T014 [P] [US1] Frontend : créer `frontend/app/components/applications/ChecklistItemRow.vue` (badge statut Manquant/Fourni dark-mode, action **Téléverser** réutilisant `DocumentUpload`, affichage du nom de fichier si fourni) — props `applicationId`, `item` ; émet `changed`
- [X] T015 [US1] Frontend : intégrer `ChecklistItemRow` dans l'onglet Checklist de `frontend/app/pages/applications/[id].vue` (remplacer le rendu lecture seule, conserver « Aucun document requis » si vide — FR-017) et câbler le flux upload→attach (`useDocuments.uploadDocuments` puis `attachDocument`)

**Checkpoint**: US1 livrable — MVP fonctionnel et testable seul.

---

## Phase 4: User Story 2 - Rattacher un document déjà téléversé (Priority: P2)

**Goal**: rattacher à un item « Manquant » un document existant via un sélecteur.

**Independent Test**: avec ≥ 1 document existant, ouvrir le sélecteur depuis un item « Manquant », choisir → item « Fourni ».

**Backend**: aucun nouvel endpoint (réutilise le `PUT` de US1).

### Tests (TEST FIRST) ⚠️

- [X] T016 [P] [US2] Frontend : tests `DocumentPicker` (liste des documents du compte, sélection émet l'id, **état vide → message + invite au téléversement**, **aucun filtrage par origine — un document quelconque du compte, y compris créé via l'upload checklist, est listé et sélectionnable (FR-002a)**) dans `frontend/test/components/DocumentPicker.spec.ts`

### Implementation

- [X] T017 [P] [US2] Frontend : créer `frontend/app/components/documents/DocumentPicker.vue` (réutilise `FullscreenModal` + `DocumentList` + `useDocuments.fetchDocuments`, dark-mode, émet `@select(documentId)`, gère l'état vide)
- [X] T018 [US2] Frontend : ajouter l'action **Choisir un existant** dans `ChecklistItemRow.vue` (ouvre `DocumentPicker`, sur sélection appelle `attachDocument` de US1)

**Checkpoint**: US1 + US2 fonctionnent indépendamment.

---

## Phase 5: User Story 3 - Prévisualiser le document rattaché (Priority: P3)

**Goal**: ouvrir l'aperçu du document d'un item « Fourni » sans quitter la page.

**Independent Test**: sur un item « Fourni », cliquer Aperçu → le document s'affiche (PDF/image).

### Tests (TEST FIRST) ⚠️

- [X] T019 [P] [US3] Frontend : test « aperçu » dans `frontend/test/components/ChecklistItemRow.spec.ts` (item fourni → ouverture de `DocumentPreview` avec `documentId`/`mimeType`/`filename` issus de `item.document`)

### Implementation

- [X] T020 [US3] Frontend : ajouter l'action **Aperçu** dans `ChecklistItemRow.vue` (réutilise `DocumentPreview` dans une modale, props depuis `item.document`)

**Checkpoint**: US1 + US2 + US3 indépendamment fonctionnels.

---

## Phase 6: User Story 4 - Détacher ou remplacer le document (Priority: P3)

**Goal**: détacher (→ « Manquant ») ou remplacer le document d'un item « Fourni ».

**Independent Test**: sur un item « Fourni », détacher → « Manquant » ; remplacer → nouveau nom de fichier.

### Tests (TEST FIRST) ⚠️

- [X] T021 [P] [US4] Backend : tests du `DELETE …/checklist/{item_key}/document` dans `backend/tests/test_applications/test_checklist_documents.py` — provided→missing (`document=null`, progression décrémentée) ; **idempotent** sur item déjà missing ; **le document n'est PAS supprimé** et reste rattachable ailleurs (FR-011) ; `item_key`/`application_id` inconnus → 404 ; 1 ligne d'audit ; autres items inchangés
- [X] T022 [P] [US4] Frontend : tests dans `frontend/test/components/ChecklistItemRow.spec.ts` — Détacher (→ missing) et Remplacer (provided→nouveau document) ; tests `useApplications.detachDocument` dans `frontend/test/composables/useApplications.checklist.spec.ts`

### Implementation

- [X] T023 [US4] Backend : implémenter `detach_checklist_document(db, application, item_key)` (verrou `with_for_update()` sur le dossier → relire `checklist`, `document_id=None`, `status="missing"` sur le seul item ciblé) dans `backend/app/modules/applications/service.py`
- [X] T024 [US4] Backend : ajouter l'endpoint `DELETE /api/applications/{application_id}/checklist/{item_key}/document` (réponse `{ item, checklist_progress }`) dans `backend/app/modules/applications/router.py`
- [X] T025 [P] [US4] Frontend : `detachDocument(applicationId, itemKey)` dans `frontend/app/composables/useApplications.ts` (DELETE, MAJ store)
- [X] T026 [US4] Frontend : ajouter les actions **Détacher** et **Remplacer** dans `ChecklistItemRow.vue` (remplacer = ouvrir upload/`DocumentPicker` puis `attachDocument` avec le nouvel id)

**Checkpoint**: cycle de vie d'un item complet (fournir / prévisualiser / détacher / remplacer).

---

## Phase 7: User Story 5 - Visualiser la progression (Priority: P4)

**Goal**: voir « M / N » dans l'onglet Checklist et un badge compact sur la carte de dossier.

**Independent Test**: dossier avec M fournis sur N → indicateur exact dans l'onglet + badge « M/N » dans la liste ; mise à jour après attach/detach.

### Tests (TEST FIRST) ⚠️

- [X] T027 [P] [US5] Backend : test `checklist_progress` présent et exact dans la **liste** `GET /api/applications/` dans `backend/tests/test_applications/test_checklist_documents.py`
- [X] T028 [P] [US5] Frontend : tests de l'indicateur « M/N documents » (onglet) et du badge carte dans `frontend/test/components/ChecklistItemRow.spec.ts` (ou un `applications.progress.spec.ts` dédié)

### Implementation

- [X] T029 [US5] Backend : ajouter `checklist_progress { provided, total }` à la sérialisation de la **liste** `GET /api/applications/` (+ schéma de réponse liste) dans `backend/app/modules/applications/router.py` et `backend/app/modules/applications/schemas.py`
- [X] T030 [US5] Frontend : afficher « M / N documents fournis » (compteur + barre, dark-mode) en tête de l'onglet Checklist dans `frontend/app/pages/applications/[id].vue`
- [X] T031 [US5] Frontend : ajouter le badge compact « M/N » sur la carte de dossier (à côté de « M/N sections ») dans `frontend/app/pages/applications/index.vue`

**Checkpoint**: toutes les user stories indépendamment fonctionnelles.

---

## Phase 8: Cross-Cutting Correctness (FR-014 intégrité + FR-019 parité)

**Purpose**: correctness transverse, non rattachée à une seule story UI mais exigée par SC-005 et FR-019.

### Intégrité référentielle à la suppression d'un document (FR-014, SC-005)

- [X] T032 [P] Backend (TEST FIRST) : test dans `backend/tests/test_documents/test_delete_cleanup.py` — un document rattaché à **2 items / 2 dossiers** du compte, supprimé via `delete_document` → les 2 items repassent `missing` (`document_id=None`) ; aucun crash ; progression recalculée
- [X] T033 Backend : implémenter `clear_document_references(db, account_id, document_id)` (parcourt les dossiers du compte, réinitialise atomiquement chaque item référençant le document) dans `backend/app/modules/applications/service.py`
- [X] T034 Backend : appeler `clear_document_references` depuis `delete_document` dans `backend/app/modules/documents/service.py` (dépendance unidirectionnelle documents→applications, avant suppression de la ligne)

### Parité chatbot (FR-019)

- [X] T035 [P] Backend (TEST FIRST) : mettre à jour le mock de `get_application_checklist` vers la forme réelle (`{key,name,status,document_id,required_by}`) et asserter le comptage via `status=="provided"` + libellé `name` dans `backend/tests/test_tools/test_application_tools.py`
- [X] T036 Backend : corriger `get_application_checklist` pour lire `status == "provided"`, `name`, et dériver « requis » de `required_by` (supprimer les lectures `provided`/`label`/`required` inexistantes) dans `backend/app/graph/tools/application_tools.py`

**Checkpoint**: état cohérent pour tous les consommateurs (UI, fiche de prép, chatbot, audit).

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T037 [P] E2E Playwright du flux P1 (upload → « Fourni » + progression) dans `frontend/e2e/checklist-documents.spec.ts`
- [X] T038 [P] Revue dark mode + accents français sur `ChecklistItemRow.vue` et `DocumentPicker.vue` (fonds/textes/bordures/hover selon CLAUDE.md ; messages d'erreur FR) — FR-020
- [ ] T039 Exécuter la recette `specs/049-checklist-documents/quickstart.md` (5 user stories + cas limites : document supprimé, réutilisation, multi-tenant, checklist vide)
- [X] T040 Vérifier la couverture ≥ 80 % (`cd backend && pytest --cov=app/modules/applications --cov=app/modules/documents` ; `cd frontend && npm run test`) et compléter les tests manquants

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)** : aucune dépendance.
- **Foundational (P2)** : dépend de Setup — **bloque toutes les stories** (schémas + lecture enrichie).
- **User Stories (P3–P7)** : dépendent de Foundational.
  - US2, US3, US4 réutilisent l'endpoint d'attach de **US1** (T011/T012) → US1 d'abord.
  - US2 (picker), US3 (preview), US5 (progression) sont par ailleurs indépendantes entre elles une fois US1 fait.
- **Cross-Cutting (P8)** : FR-014 (T032–T034) dépend de US1 (les `document_id` doivent pouvoir être stockés) ; FR-019 (T035–T036) indépendant (peut démarrer après Foundational).
- **Polish (P9)** : après les stories visées.

### User Story Dependencies

- **US1 (P1)** : socle ; introduit l'endpoint d'attach réutilisé par US2/US4.
- **US2 (P2)** : dépend de US1 (attach) ; ajoute le sélecteur.
- **US3 (P3)** : dépend de Foundational (sous-objet `document`) ; indépendant de US2.
- **US4 (P3)** : dépend de US1 (attach pour remplacer) ; ajoute detach.
- **US5 (P4)** : dépend de Foundational (progression) ; backend liste indépendant.

### Within Each User Story

- Tests AVANT implémentation (RED → GREEN → REFACTOR).
- Backend : schémas → service → endpoint.
- Frontend : composable → composant → intégration page.

### Parallel Opportunities

- T001/T002 en parallèle ; T004 ‖ T008.
- US1 : T009 ‖ T010 (tests) ; puis T013 ‖ T014 (frontend) pendant T011/T012 (backend).
- US4 : T021 ‖ T022 ; T025 ‖ (T023/T024).
- P8 : T032 ‖ T035. P9 : T037 ‖ T038.
- Une fois US1 livré, US2/US3/US5 peuvent être menées en parallèle par plusieurs développeurs (FR-014/FR-019 aussi).

---

## Parallel Example: User Story 1

```bash
# Tests d'abord (échouent) :
Task T009: "Backend tests PUT attach (nominal + 403/404 + audit + atomicité)"
Task T010: "Frontend tests attachDocument + ChecklistItemRow (upload→provided)"

# Puis implémentation backend et frontend en parallèle :
Task T013: "Frontend useApplications.attachDocument"
Task T014: "Frontend ChecklistItemRow.vue (upload + nom de fichier)"
# (pendant que T011/T012 construisent service + endpoint backend)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE** (téléverser → « Fourni » + nom + progression) → démo/déploiement.

### Incremental Delivery

Foundational → US1 (MVP) → US2 → US3 → US4 → US5 → P8 (intégrité + parité) → P9 (polish). Chaque story ajoute de la valeur sans casser les précédentes.

### Couverture des exigences (rappel)

- FR-001/002/004/010/016/018/021 → US1 ; FR-002a → réutilisation upload (US1, automatique) **+ vérifié T016**.
- FR-003 → US2 ; FR-005 → US3 ; FR-006/007/011/013 → US4 ; FR-008/SC-004 → US5 + Foundational.
- FR-009/SC-002 → Foundational ; FR-014/SC-005 → P8 ; FR-019 → P8 ; FR-012/017/020 → préservation + P9.
- SC-001/SC-007 → E2E + quickstart ; SC-003 → US1 (403) ; SC-006 → tests d'audit US1/US4.

---

## Notes

- [P] = fichiers différents, sans dépendance non satisfaite.
- Vérifier que chaque test échoue avant d'implémenter (Constitution IV).
- Commit après chaque tâche ou groupe logique (`feat:`/`test:`/`fix:`).
- Aucune migration ni dépendance nouvelle ; réutilisation maximale des composants documentaires existants.

## Statut d'implémentation (2026-06-03)

- **Backend** : 40 tests verts (`test_checklist_documents.py` 26, `test_delete_cleanup.py` 2, `test_application_tools.py` mis à jour) ; suite `tests/test_applications` + `tests/test_documents` + tool : **220 passants**. Couverture du code ajouté ≥ 80 % (service applications 89 %, router 84 %, `delete_document` couvert ; seules 2 lignes purement défensives non couvertes).
- **Frontend** : 17 tests unitaires verts (composable attach/detach + mutators store, `ChecklistItemRow` cycle de vie complet, `DocumentPicker`). Les 12 échecs de la suite globale vitest sont **préexistants** (guided-tours, pages ESG) et sans rapport (vérifié par stash).
- **Convention tests** : tasks.md référence `frontend/test/...spec.ts`, mais la convention réelle du projet est `frontend/tests/**/*.test.ts` (vitest) et `frontend/tests/e2e/*.spec.ts` (Playwright) — les fichiers ont été placés selon la convention réelle pour être découverts.
- **T037 (E2E)** : spec `tests/e2e/checklist-documents.spec.ts` rédigée et correcte (clés auth `access_token`/`auth_user`, globs `**/api/...`, sélecteurs alignés). Exécution **bloquée par un problème SSR préexistant du dev-server** (erreur 500 « Cannot read properties of undefined (reading 'charAt') ») qui fait aussi échouer le spec de référence `candidater.spec.ts` — indépendant de 049.
- **T039 (recette manuelle)** : non exécutée — nécessite un stack live (uvicorn + Nuxt dev + navigateur) et la validation interactive ; bloquée par le même souci SSR frontend. Les scénarios sont couverts par les tests automatisés (backend intégration + frontend unitaires + E2E rédigé).

### Revue adversariale (5 dimensions, 21 findings, 8 confirmés) — correctifs appliqués

- **[HIGH] Atomicité FR-021 non garantie** : le `with_for_update()` renvoyait l'instance de l'identity-map **sans rafraîchir** `checklist` → last-write-wins persistait sous concurrence inter-sessions. **Corrigé** par `.execution_options(populate_existing=True)` sur les relectures verrouillées (attach/detach/clear) + test de régression `test_attach_concurrent_sessions_no_lost_update` (vérifié rouge sans le correctif, vert avec).
- **[MEDIUM] Sélecteur tronqué à 20 docs** : `DocumentPicker` chargeait la page 1 par défaut → documents au-delà invisibles (FR-003/FR-002a). **Corrigé** : `fetchDocuments({ limit: 200 })` + assertion test.
- **[LOW] Corbeille dans le sélecteur** : `DocumentList` exposait l'action destructrice dans le picker. **Corrigé** : prop `selectableOnly` (défaut = comportement actuel) masquant la suppression, activée par le picker + assertion test.
- **[LOW] État UI résiduel au détachement** : `onDetach` ne réinitialisait pas `showUpload`/`replaceMode`. **Corrigé** : `resetControls()` au succès + test.
- **[LOW] Double croix de fermeture sur l'aperçu** : `FullscreenModal` + `DocumentPreview` affichaient chacun une croix. **Corrigé** : prop `showClose` sur `FullscreenModal`, l'aperçu passe `:show-close="false"`.
- **Findings acceptés sans changement (documentés)** : (1) `403 vs 404` cross-compte sous RLS — défense en profondeur OK, SC-003 respecté (la RLS masque le document → 404 ; le 403 applicatif reste pour les documents legacy `account_id NULL`) ; (2) progression liste (statut stocké) vs détail (statut effectif) — divergence empêchée par le nettoyage eager FR-014 (choix research D8, anti-N+1 sur la liste) ; (3) portée du verrou `clear_document_references` — optimisation JSONB explicitement différée (research D3, YAGNI à l'échelle V1).
