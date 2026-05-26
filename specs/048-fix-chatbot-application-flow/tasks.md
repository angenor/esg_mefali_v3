---
description: "Task list — 048-fix-chatbot-application-flow"
---

# Tasks: Fiabiliser la création de dossier de candidature et la mémoire ESG du chatbot

**Input**: Design documents from `/specs/048-fix-chatbot-application-flow/`
**Prerequisites**: plan.md, spec.md, research.md (D1–D5), data-model.md, contracts/

**Tests**: INCLUS et OBLIGATOIRES — la constitution impose le TDD (Principe IV, NON-NÉGOCIABLE, couverture ≥ 80 %). Les tests sont écrits AVANT l'implémentation et doivent ÉCHOUER d'abord.

**Organization**: tâches groupées par user story (US1, US2 = P1 ; US3 = P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, pas de dépendance bloquante)
- **[Story]** : US1 / US2 / US3
- Chemins absolus depuis la racine du repo.

## Path Conventions (web app — cf. plan.md)

- Backend : `backend/app/...`, tests `backend/tests/{unit,integration}/`
- Frontend : `frontend/app/...`, tests `frontend/tests/` (Vitest) + `frontend/tests/e2e/` (Playwright)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: préparer l'environnement de test (le projet existe déjà ; aucune init de stack).

- [X] T001 Vérifier l'environnement de dev et de test : `source backend/venv/bin/activate`, exécuter `pytest backend/tests -q` (baseline vert) et `cd frontend && npx vitest run` ; créer les fichiers de test vides référencés ci-dessous s'ils n'existent pas dans `backend/tests/unit/`, `backend/tests/integration/`, `frontend/tests/`, `frontend/tests/e2e/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: chemin de création de dossier **partagé** chat/UI (D5) — prérequis de US1 (parité FR-016) ET US3 (bouton). 

**⚠️ CRITICAL**: aucune story ne peut être finalisée avant cette phase.

- [X] T002 [P] Écrire les tests d'intégration du service de création (ÉCHOUENT d'abord) dans `backend/tests/integration/test_application_create_service.py` : (a) `create_application(offer_id=…)` dérive `fund_id`/`intermediary_id` et lie `project_id` ; (b) dédup — 2e appel même `(user_id, project_id, offer_id)` en `draft` retourne le MÊME dossier ; (c) `offer_id` inexistant → erreur (ValueError → 404 amont). Réf. contracts/application-creation.md T1, T2.
- [X] T003 Étendre le schéma `ApplicationCreate` avec `offer_id: UUID | None` et `project_id: UUID | None` dans `backend/app/modules/applications/schemas.py` (validation : `offer_id` prioritaire si fourni).
- [X] T004 Étendre `create_application(...)` dans `backend/app/modules/applications/service.py` : si `offer_id` → charger `Offer`, poser `fund_id`/`intermediary_id`/`offer_id` ; lier `project_id` ; **dédup** du dossier `draft` pour `(user_id, project_id, offer_id)` (réutiliser l'existant). Dépend de T003. Fait passer T002.

**Checkpoint**: service partagé prêt — US1 et US3 peuvent démarrer.

---

## Phase 3: User Story 1 — Créer un dossier via le chatbot, quel que soit le contexte (Priority: P1) 🎯 MVP

**Goal**: le chatbot crée le dossier (statut brouillon) + génère le document réel téléchargeable, depuis n'importe quelle page, sans « outil indisponible », en bloquant si les critères ESG requis manquent.

**Independent Test**: depuis le chat ouvert sur `/documents`, « génère un dossier de candidature pour GCF via BOAD » → dossier créé + document généré (ou guidage si ESG incomplet), aucun message d'outil indisponible.

### Tests for User Story 1 (écrire AVANT, doivent ÉCHOUER) ⚠️

- [X] T005 [P] [US1] Tests unitaires du sélecteur piloté par l'intention dans `backend/tests/unit/test_tool_selector_intent.py` : cas T1–T7 de contracts/tool-selector.md (notamment `node=application`+page `/documents` → `create_fund_application` présent ; `len(selected) ≤ 36` ; whitelist conservée ; priorité nœud > page en troncature).
- [X] T006 [P] [US1] Tests unitaires de l'export réel dans `backend/tests/unit/test_export_application_tool.py` : le tool `export_application` écrit un fichier réel sous `/uploads/applications/` et enregistre un `Document` (plus de chemin factice). Réf. contracts/application-creation.md T6.
- [X] T007 [P] [US1] Tests unitaires du gating ESG dans `backend/tests/unit/test_application_esg_gating.py` : critères requis manquants → génération bloquée (`blocked:true`, pas de fichier) ; critères couverts → génération autorisée. Le référentiel applicable est résolu via `compute_referential_score_for_offer` (mocké). Réf. T7/T8.
- [X] T008 [P] [US1] Test d'intégration « dossier via chat depuis /documents » dans `backend/tests/integration/test_chat_create_application.py` : simulation d'un tour LLM routé `application`/`financing` avec `current_page=/documents` → `create_fund_application` exposé et exécuté.

### Implementation for User Story 1

- [X] T009 [US1] Refactorer `select_tools_for_node` dans `backend/app/graph/tool_selector.py` : `base = GLOBAL_WHITELIST ∪ MODULE_TOOL_MAPPING[node] ∪ PAGE_TOOL_MAPPING[slug]`, troncature priorisée (whitelist > tools du nœud/intention > tools de page) ; enrichir `debug_info` (`node_tools_included`). Fait passer T005.
- [X] T010 [US1] Vérifier/renforcer la classification d'intention F013 dans `backend/app/graph/nodes.py` pour router « créer/candidater/générer un dossier » vers le nœud `application`/`financing` même depuis une page non-financement (ajouter mots-clés/exemples si la classification reste sur `chat`). Fait passer T008.
- [X] T011a [US1] Ajouter `register_generated_document(db, *, user_id, account_id, storage_path, original_filename, mime_type, file_size, document_type)` dans `backend/app/modules/documents/service.py` : insère une ligne `Document` (status final, sans OCR) pour un fichier déjà écrit sur disque. (Lève U2 — le service n'a que `upload_document` pour les uploads entrants.)
- [X] T011 [US1] Câbler le tool chat `export_application` au vrai moteur `backend/app/modules/applications/export.py` dans `backend/app/graph/tools/application_tools.py` : générer les bytes, écrire `/uploads/applications/{id}.{fmt}` (défaut `docx`, mime adapté), appeler `register_generated_document` (T011a), retourner l'URL réelle. Remplace le stub `_export_application`. Dépend de T011a. Fait passer T006.
- [X] T012 [US1] Ajouter la garde de gating ESG avant génération dans `backend/app/graph/tools/application_tools.py` : **réutiliser** `app/modules/esg/multi_referential_service.py::compute_referential_score_for_offer` pour résoudre le référentiel applicable à l'offre (pas de FK offre→référentiel — cf. research D4/U1), puis comparer ses critères `is_required` à `covered_criteria`/`missing_criteria` de l'évaluation ESG-projet du `project_id` ; si incomplet → retour `{ok:false, blocked:true, missing_criteria, message}`. Dépend de T011. Fait passer T007.
- [X] T013 [US1] Refactorer `create_fund_application` (chat tool) dans `backend/app/graph/tools/application_tools.py` pour appeler le service partagé `create_application` (T004) au lieu de l'assignation directe `offer_id`/`project_id` (parité FR-016, dédup FR-006). Dépend de T004.
- [X] T014 [US1] Ajouter une directive de prompt « création de dossier via chat » (séquence create → générer sections si besoin → export ; jamais affirmer une génération non effectuée) dans les prompts `financing`/`application` de `backend/app/graph/nodes.py`.

**Checkpoint**: US1 testable seule — création + document via chat depuis n'importe quelle page, gating actif.

---

## Phase 4: User Story 2 — Retrouver le travail ESG d'une session à l'autre (Priority: P1)

**Goal**: le chatbot reconnaît les évaluations ESG existantes en nouvelle session et ne présente pas comme « manquants » des critères déjà remplis.

**Independent Test**: session A saisir ≥ 2 critères ; session B (nouvelle conversation) « où en est mon évaluation ESG du projet X » → critères reconnus couverts.

### Tests for User Story 2 (écrire AVANT, doivent ÉCHOUER) ⚠️

- [X] T015 [P] [US2] Tests unitaires du résumé ESG proactif dans `backend/tests/unit/test_context_esg_summary.py` : `_load_full_context_for_state` retourne `project_esg_assessments` (compteurs couverts/manquants corrects ; `[]` si aucun ; `[]` + log si erreur SQL ; scoping `account_id`). Réf. contracts/chat-context-esg.md T1–T4.
- [X] T016 [P] [US2] Test d'intégration cross-session dans `backend/tests/integration/test_esg_memory_cross_session.py` : après saisie de critères, un nouveau chargement de contexte expose l'évaluation et l'état couvert (SC-002).

### Implementation for User Story 2

- [X] T017 [US2] Étendre `_load_full_context_for_state` dans `backend/app/api/chat.py` : ajouter la clé `project_esg_assessments` (résumé léger joint aux projets actifs déjà chargés, ≤ 1 requête, tolérant aux erreurs). Fait passer T015.
- [X] T018 [US2] Ajouter le champ `user_project_esg_assessments: list[dict] | None` à `ConversationState` dans `backend/app/graph/state.py` (TypedDict, `class ConversationState` ligne 9), à côté de `user_projects`.
- [X] T019 [US2] Propager `user_project_esg_assessments` lors de la construction du state dans `backend/app/api/chat.py` (~ligne 1239, à côté de `user_projects`). Fait passer T016.
- [X] T020 [US2] Injecter la directive « vérifie `get_project_esg_assessment` avant de déclarer un critère manquant ; ne crée pas un 2e assessment si un draft existe » dans les prompts `financing`/`application`/`esg_scoring` de `backend/app/graph/nodes.py`.

**Checkpoint**: US1 ET US2 fonctionnent indépendamment ; le gating US1 bénéficie de la mémoire restaurée.

---

## Phase 5: User Story 3 — Candidater depuis l'interface Financement (Priority: P2)

**Goal**: le bouton « Candidater » crée un dossier brouillon (rattaché projet/offre) et conduit vers le dossier, avec feedback d'erreur ; plus de clic mort.

**Independent Test**: sur `/financing/offers/{id}?project_id=…`, cliquer « Candidater » → dossier créé visible, 0 page 404, double-clic sans doublon.

### Tests for User Story 3 (écrire AVANT, doivent ÉCHOUER) ⚠️

- [X] T021 [P] [US3] Tests d'intégration de l'endpoint dans `backend/tests/integration/test_applications_endpoint.py` : `POST /api/applications/` avec `offer_id`+`project_id` → 201 dossier lié ; `offer_id` inexistant → 404 ; dossier d'un autre compte → 403. Réf. contracts/application-creation.md T3–T5.
- [X] T022 [P] [US3] Test Vitest du handler dans `frontend/tests/financing-apply.spec.ts` : clic → `createApplication` appelé + navigation ; erreur API → message affiché, pas de navigation ; double-clic → une seule création. Réf. contracts/frontend-apply.md T1–T3.
- [X] T023 [P] [US3] Test E2E Playwright dans `frontend/tests/e2e/candidater.spec.ts` : parcours offre → « Candidater » → dossier visible (`/applications` ou `/documents`), 0 404 ; sans `project_id` → message de guidage. Réf. T4–T5.

### Implementation for User Story 3

- [X] T024 [US3] Propager `offer_id`/`project_id` dans `POST /` de `backend/app/modules/applications/router.py` vers le service `create_application` (T004) ; mapper `ValueError` → 404, cross-account → 403. Fait passer T021.
- [X] T025 [P] [US3] Ajouter `createApplication({ offerId, projectId })` (appel `POST /api/applications/`, retour dossier, erreurs FR) dans `frontend/app/composables/useApplications.ts` (créer le composable s'il n'existe pas).
- [X] T026 [US3] Réécrire `handleApply(offerId)` dans `frontend/app/pages/financing/offers/[offer_id].vue` : appeler `createApplication` puis `router.push('/applications/{id}')` ; supprimer la redirection vers la route inexistante `/apply` ; afficher message d'erreur/guidage (FR-015). Dépend de T025. Fait passer T022/T023.
- [X] T027 [US3] Ajouter état de chargement + désactivation du bouton pendant l'appel (anti double-clic, FR-006) dans `frontend/app/pages/financing/offers/[offer_id].vue` (et/ou `frontend/app/components/financing/OfferDetail.vue`).

**Checkpoint**: les 3 user stories fonctionnent indépendamment ; dossiers chat/UI équivalents.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Exécuter `pytest backend/tests -k "tool_selector or context_esg or application_create or export or gating or esg_memory or applications_endpoint" --cov=app --cov-report=term-missing` et vérifier ≥ 80 % sur les modules touchés.
- [X] T029 [P] Lint + typecheck frontend : `cd frontend && npx vitest run && npx playwright test && npm run lint`.
- [X] T030 [P] Dérouler `specs/048-fix-chatbot-application-flow/quickstart.md` (scénarios 1–3) manuellement (chat + UI) et consigner les résultats. Mesurer SC-005 (parcours offre → dossier en < 3 échanges après confirmation) en comptant les tours dans le scénario 1.
- [X] T031 Revue `code-reviewer` + `security-reviewer` (RLS F02 conservée, sourçage F01, audit F03 sur création dossier/maj ESG) sur le diff de la branche.
- [X] T032 Ajouter l'entrée ledger F048 dans `CLAUDE.md` (Module 3) résumant les correctifs (sélecteur intention, mémoire ESG proactive, export réel, gating, parité chat/UI).

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (P1)** : aucune dépendance.
- **Foundational (P2 : T002–T004)** : bloque US1 (T013) et US3 (T024).
- **US1 (P3)** : après Foundational. T009/T010 (sélecteur+routing) indépendants du service ; T013 dépend de T004.
- **US2 (P4)** : après Foundational ; indépendante de US1 (testable seule).
- **US3 (P5)** : après Foundational (T004) ; frontend T026 dépend de T025.
- **Polish (P6)** : après les stories visées.

### Within Each User Story
- Tests écrits et en ÉCHEC avant implémentation (Principe IV).
- Schéma → service → endpoint/tool → prompt → intégration.

### Ordre intra-fichier (NON parallèle)
- `application_tools.py` : T011 → T012 → T013 (même fichier, séquentiel).
- `nodes.py` : T010, T014, T020 (même fichier, séquentiel).
- `chat.py` : T017 → T019 (même fichier, séquentiel).
- `[offer_id].vue` : T026 → T027 (même fichier, séquentiel).

### Parallel Opportunities
- Tous les tests `[P]` d'une même story (T005–T008 ; T015–T016 ; T021–T023) en parallèle.
- US1, US2, US3 parallélisables entre développeurs une fois la Foundation livrée (US3 et US1 partagent T004 → livrer T004 d'abord).

---

## Parallel Example: User Story 1

```bash
# Lancer les tests US1 ensemble (doivent échouer d'abord) :
Task: "T005 tests sélecteur intention — backend/tests/unit/test_tool_selector_intent.py"
Task: "T006 tests export réel — backend/tests/unit/test_export_application_tool.py"
Task: "T007 tests gating ESG — backend/tests/unit/test_application_esg_gating.py"
Task: "T008 test intégration chat /documents — backend/tests/integration/test_chat_create_application.py"
```

---

## Implementation Strategy

### MVP (US1 seule)
1. Phase 1 Setup → 2. Phase 2 Foundational (T002–T004) → 3. Phase 3 US1 → **STOP & VALIDATE** (quickstart scénario 1) → démo.

### Incrémental
- Foundation → US1 (création + document via chat) → US2 (mémoire ESG, lève le « critères manquants » erroné) → US3 (bouton UI) → Polish.
- US1 + US2 (tous deux P1) constituent le cœur « tout via le chatbot » ; US3 ajoute la parité UI.

---

## Notes
- `[P]` = fichiers différents, pas de dépendance.
- **FR-008b** (lecture détaillée à la demande) est **déjà couvert sans tâche** : `get_project_esg_assessment`/`list_project_esg_assessments` sont déjà dans `GLOBAL_WHITELIST` (`tool_selector_config.py`). Aucune implémentation requise ; vérifié indirectement par T016.
- `T011a` (documents/service.py) est dans un fichier distinct de T011/T012 (application_tools.py) → parallélisable, mais T011 en dépend.
- Aucune migration Alembic (réutilisation stricte des entités existantes).
- Vérifier l'échec des tests avant d'implémenter ; commit après chaque tâche ou groupe logique.
- Messages chatbot/erreurs UI en français (Principe I) ; dark mode obligatoire pour tout ajout frontend visible.
