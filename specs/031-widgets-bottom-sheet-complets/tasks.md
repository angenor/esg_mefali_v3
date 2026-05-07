---
description: "Task list for F10 — Widgets Interactifs Bottom Sheet Complets"
---

# Tasks: Widgets Interactifs Bottom Sheet Complets (F10)

**Input**: Design documents from `/specs/031-widgets-bottom-sheet-complets/`
**Prerequisites**: spec.md, plan.md, data-model.md, research.md, contracts/, quickstart.md

**Tests**: TDD strict obligatoire (constitution principle IV NON-NEGOTIABLE). Tous les tests sont écrits AVANT l'implémentation.

**Organization**: Tasks grouped by user story to enable independent implementation. P1 stories (US1-US4) constitute the MVP; P2 stories (US5-US8) are added incrementally; US9 is cross-cutting.

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]** : Task parallélisable (fichiers indépendants, pas de dépendance bloquante)
- **[Story]** : Mappe la task à un user story (US1...US9). Phases Setup/Foundational/Polish ne portent pas de label.
- Chemins absolus relatifs au repo root `/Users/mac/Documents/projets/2025/esg_mefali_v3/`.

## Path Conventions

- Backend : `backend/app/`, tests `backend/tests/`
- Frontend : `frontend/app/` (Nuxt 4), tests `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Préparer les dépendances système et les outillages partagés.

- [ ] T001 Vérifier la disponibilité de `libmagic` sur le poste dev (`brew install libmagic` macOS / `apt install libmagic1` Linux), documenter dans `backend/README.md` ou `quickstart.md` (Plan §Technical Context)
- [ ] T002 [P] Ajouter `python-magic>=0.4.27` à `backend/requirements.txt` et `backend/requirements-dev.txt` si nécessaire (FR-025, R5)
- [ ] T003 [P] Vérifier la présence de `vue-virtual-scroller` et `zod` dans `frontend/package.json` ; ajouter les manquants via `npm install vue-virtual-scroller zod` (FR-021, FR-023, R3, R4)
- [ ] T004 [P] Mettre à jour `CLAUDE.md` section Active Technologies avec python-magic, vue-virtual-scroller, zod (déjà fait par script `update-agent-context.sh`, vérifier propre)

**Checkpoint** : dépendances installées, CI verte sur la branche `feat/F10-widgets-bottom-sheet-complets`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration BDD, modèle SQLAlchemy étendu, schémas Pydantic discriminés, helpers backend. Ces tâches sont préalables à TOUTES les user stories.

**CRITICAL**: Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Phase 2 (TDD strict — RED first)

- [ ] T005 [P] Tests unitaires des schémas Pydantic discriminés (9 payload + 9 response) dans `backend/tests/unit/schemas/test_interactive_question_payloads.py` — vérifier `extra="forbid"`, bornes, validation discriminée par `question_type` (FR-002, FR-003, data-model.md)
- [ ] T006 [P] Test du helper `requires_destructive_confirmation` dans `backend/tests/unit/graph/tools/test_destructive_pattern.py` — vérifier format JSON retour, validation de `DESTRUCTIVE_ACTIONS`, levée de `ValueError` sur action non enregistrée (FR-011, FR-012, contracts/destructive_pattern.md)
- [ ] T007 [P] Test up/down/up de la migration Alembic 031 dans `backend/tests/integration/test_alembic_031_up_down_up.py` — vérifier idempotence, refus du downgrade en présence de lignes utilisant les nouvelles valeurs d'enum, conservation des 4 valeurs F18 existantes (FR-004, SC-009)

### Implementation Phase 2

- [ ] T008 Créer la migration Alembic `backend/alembic/versions/031_extend_interactive_questions.py` avec `revision="031_extend_interactive_questions"` et `down_revision="030_create_referential_scores"`. Up : ajouter 9 valeurs à l'enum `interactivequestiontype` via `ALTER TYPE ... ADD VALUE IF NOT EXISTS` dans `autocommit_block`, ajouter colonnes `payload jsonb NOT NULL DEFAULT '{}'` et `response_payload jsonb NULL`, remplacer `ck_iq_max_le_8` par `ck_iq_max_le_8_or_select_form`. Down : refuser si lignes utilisent les nouvelles valeurs, restaurer la contrainte initiale, drop colonnes (FR-001, FR-002, FR-003, FR-004, FR-005, R9)
- [ ] T009 Étendre `backend/app/models/interactive_question.py` : ajouter 9 valeurs à l'enum `InteractiveQuestionType` (yes_no, select, number, date, date_range, rating, file_upload, form, summary_card), ajouter colonnes Mapped `payload: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict, server_default="{}")` et `response_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)` (FR-001, FR-002, FR-003)
- [ ] T010 Étendre `backend/app/schemas/interactive_question.py` avec les 9 schémas Pydantic Payload (`YesNoPayload`, `SelectPayload`, `NumberPayload`, `DatePayload`, `DateRangePayload`, `RatingPayload`, `FileUploadPayload`, `FormPayload`, `SummaryCardPayload`) et la union discriminée `InteractiveQuestionPayload`. Inclure types support (`SelectOption`, `FormField`, `FormFieldValidation`, `SummaryCardItem`) avec `extra="forbid"` strict (FR-002, data-model.md, contracts/widget_payloads.md)
- [ ] T011 Étendre `backend/app/schemas/interactive_question.py` avec les 9 schémas Pydantic Response (`YesNoResponse`, `SelectResponse`, `NumberResponse`, `DateResponse`, `DateRangeResponse`, `RatingResponse`, `FileUploadResponse`, `FormResponse`, `SummaryCardResponse`) et la union discriminée `InteractiveQuestionResponse`. Inclure types support (`UploadedDocument`, `SummaryCardModification`) (FR-003, contracts/widget_responses.md)
- [ ] T012 Ajouter le helper `requires_destructive_confirmation(action_name: str) -> str` dans `backend/app/graph/tools/common.py` avec liste `DESTRUCTIVE_ACTIONS` initiale (`delete_project`, `delete_application`, `delete_assessment`, `delete_carbon_assessment`, `revoke_attestation`, `cancel_application`) et test garde-fou contre actions non enregistrées (FR-011, FR-012, contracts/destructive_pattern.md)
- [ ] T013 [P] Créer le helper `backend/app/core/fx_rates.py` avec constantes `XOF_PER_EUR=655.957`, `XOF_PER_USD=600.0`, `XOF_PER_CDF=0.35` et fonction `get_fx_rates() -> dict[str, float]` qui fallback sur ces constants si la table `referential_fx_rates` n'existe pas (FR-022, R7)
- [ ] T014 [P] Étendre `backend/app/api/routers/documents.py` (POST upload) avec validation MIME via `python-magic` : `magic.from_buffer(content, mime=True)`, mapping extension → MIME attendu, refus HTTP 415 « Type de fichier incohérent » en cas de discordance (FR-025, SC-012, R5)

**Checkpoint** : migration appliquée localement, modèles/schémas validés par tests unitaires, helper destructif fonctionnel. Toutes les user stories peuvent commencer en parallèle.

---

## Phase 3: User Story 1 — Confirmation d'une action destructive (Priority: P1) 🎯 MVP

**Goal**: Permettre au LLM de demander une confirmation utilisateur via `ask_yes_no(destructive=True)` avant toute action de suppression/révocation, avec UX click-and-hold 2s et trace audit_log.

**Independent Test**: Lancer une conversation, demander « supprime mon projet test ». Vérifier : (1) le LLM appelle `delete_project(confirm=False)` qui retourne le marker `requires_confirmation`, (2) `ask_yes_no(destructive=True)` génère un widget rouge en bottom sheet, (3) hold 2s sur « Oui, supprimer » exécute la suppression, (4) audit_log contient une entrée avec `metadata.confirm=true`.

### Tests US1 (RED first)

- [ ] T015 [P] [US1] Test backend du tool `ask_yes_no` dans `backend/tests/unit/graph/tools/test_interactive_tools_yes_no.py` — args validation, persistence en BDD avec `payload` correct, marker SSE format, journalisation `tool_call_logs` (FR-006, FR-008, FR-009)
- [ ] T016 [P] [US1] Test backend du pattern destructif end-to-end dans `backend/tests/integration/test_widget_e2e_yes_no_destructive.py` — `delete_project(confirm=False)` retourne marker, `ask_yes_no(destructive=True)` crée question pending, simulation réponse user `value=true`, re-appel `delete_project(confirm=True)` exécute suppression, audit_log contient `metadata.confirm=true` (FR-011, FR-013, SC-001, SC-011)
- [ ] T017 [P] [US1] Test Vitest unitaire `frontend/tests/unit/components/chat/widgets/YesNoWidget.spec.ts` — rendu mode normal vs destructif (bouton rouge), hold 2s déclenche submit, click court (< 2s) ne soumet pas, accessibilité ARIA, dark mode, `prefers-reduced-motion` respecté (FR-018, FR-019, FR-030, FR-031)
- [ ] T018 [US1] Scénario E2E (a) dans `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` — flow conversation : user demande suppression projet → LLM appelle `delete_project(confirm=False)` → widget rouge apparaît → hold 2s sur « Oui, supprimer » → projet supprimé en BDD + audit_log (FR-039, SC-001, SC-011, US1 acceptance scenarios 1-4)

### Implementation US1

- [ ] T019 [P] [US1] Implémenter le tool `ask_yes_no` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `AskYesNoArgs`, pattern uniforme (db, conversation_id, expire pending, insert avec payload, journaliser, retour string + marker SSE) (FR-006, FR-007, FR-008, FR-009, contracts/interactive_tools_schemas.md)
- [ ] T020 [P] [US1] Étendre `backend/app/graph/tools/project_tools.py` (déjà existant suite à F25 : `delete_project` présent) en ajoutant le paramètre `confirm: bool = False` à `delete_project`. Comportement : si `confirm=False`, retourne `requires_destructive_confirmation("delete_project")` SANS toucher la BDD ; si `confirm=True`, exécute la suppression effective (logique existante de soft-delete avec garde-fou `force` conservée), trace `metadata.confirm=True` dans audit_log (FR-011, FR-013, SC-001)
- [ ] T021 [US1] Étendre les autres tools destructifs existants avec `confirm: bool = False` : `backend/app/graph/tools/application_tools.py` (delete_application, cancel_application si présents), `backend/app/graph/tools/esg_tools.py` (delete_esg_assessment si présent), `backend/app/graph/tools/carbon_tools.py` (delete_carbon_assessment si présent). Pour chaque tool : retour `requires_destructive_confirmation(...)` si `confirm=False`, audit_log avec `metadata.confirm=True` si `confirm=True`. Si un tool destructif identifié n'existe pas encore, créer un stub minimal qui implémente le pattern (FR-011, FR-013, SC-001)
- [ ] T022 [P] [US1] Créer le composable `frontend/app/composables/useHoldToConfirm.ts` exposant `{ isHolding, progress, onPointerDown, onPointerUp, onPointerCancel, onKeyDown, onKeyUp }` avec animation CSS keyframes 2s et fallback `prefers-reduced-motion` (compteur textuel) (FR-030, FR-031, R2)
- [ ] T023 [US1] Créer le composant `frontend/app/components/chat/widgets/YesNoWidget.vue` avec deux gros boutons côte-à-côte, variante destructive (rouge + tooltip ARIA « Action irréversible » + animation hold via `useHoldToConfirm`), bouton « Répondre librement », dark mode complet (FR-018, FR-019, FR-030, FR-031)
- [ ] T024 [US1] Mettre à jour `frontend/app/types/interactive-question.ts` avec types `YesNoPayload`, `YesNoResponse`, et l'union discriminée TypeScript (déjà préparée pour les 8 autres types ; ajouter aussi les payloads/responses des US2-US8) (FR-026, contracts/sse_events.md)
- [ ] T025 [US1] Étendre `frontend/app/composables/useChat.ts` : `submitInteractiveAnswer` accepte `YesNoResponse`, génère le message texte « ✓ Oui » / « ✗ Non » (avec confirm_label/deny_label personnalisés), passe `interactive_question_response_payload` au backend. Supprimer l'heuristique fragile de mapping QCU « Oui/Non » des lignes 121-130 (FR-028, FR-029, FR-034)

**Checkpoint** : US1 fonctionnellement complet et testable indépendamment. Le pattern destructif est livré et activable sur les tools concrets en F25/F26.

---

## Phase 4: User Story 2 — Sélection dans une liste longue avec recherche (Priority: P1)

**Goal**: Permettre au LLM de demander un choix structuré dans une liste de 8 à 200 options via `ask_select` avec recherche full-text et virtualisation.

**Independent Test**: Lancer conversation, demander « dans quel pays UEMOA ? ». Vérifier : (1) widget avec champ recherche, (2) 8 options groupées, (3) tap « Cote » filtre à « Côte d'Ivoire », (4) clic envoie message « ✓ Côte d'Ivoire ».

### Tests US2 (RED first)

- [ ] T026 [P] [US2] Test backend du tool `ask_select` dans `backend/tests/unit/graph/tools/test_interactive_tools_select.py` — validation min/max selections, max 200 options, allow_other, groupement (FR-006)
- [ ] T027 [P] [US2] Test Vitest `frontend/tests/unit/components/chat/widgets/SelectWidget.spec.ts` — rendu options, recherche full-text insensible casse/accents, virtualisation conditionnelle si > 50 options, multi-sélection avec compteur, allow_other input ouvert (FR-021)
- [ ] T028 [US2] Scénario E2E (b) dans `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` — user demande pays UEMOA → widget recherche → tape « Cote » → « Côte d'Ivoire » surligné → clic → message dans le fil (FR-039, US2 acceptance scenarios)

### Implementation US2

- [ ] T029 [P] [US2] Implémenter le tool `ask_select` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `AskSelectArgs`, validation min/max, refus si > 200 options (FR-006, contracts/interactive_tools_schemas.md)
- [ ] T030 [US2] Créer le composant `frontend/app/components/chat/widgets/SelectWidget.vue` avec champ recherche (`String.normalize('NFD').replace(/[̀-ͯ]/g, '')` pour insensibilité accents), liste virtualisée via `<DynamicScroller>` de vue-virtual-scroller si `options.length > 50`, groupement par `group`, multi-sélection avec compteur, option « Autre, préciser » si `allow_other=true`, dark mode, ARIA `combobox` + `listbox` (FR-021, SC-006)
- [ ] T031 [US2] Étendre `useChat.ts:submitInteractiveAnswer` pour `SelectResponse` : générer message « ✓ Côte d'Ivoire » (mono) ou « ✓ Côte d'Ivoire, Sénégal, Mali » (multi) ou « ✓ Autre : Tchad » (other) (FR-028, FR-034)

**Checkpoint** : US2 fonctionnellement complet, virtualisation testée à 200 options.

---

## Phase 5: User Story 3 — Saisie d'un montant monétaire avec devise (Priority: P1)

**Goal**: Permettre la saisie d'un montant monétaire structuré (CA, capital, montant projet) avec devise, formatage milliers, équivalent affiché.

**Independent Test**: Demander « quel est votre CA annuel ? ». Vérifier : input numérique formaté, sélecteur XOF/EUR/USD/CDF, bornes respectées, équivalent EUR affiché sous la valeur, message « ✓ 1 200 000 FCFA » dans le fil.

### Tests US3 (RED first)

- [ ] T032 [P] [US3] Test backend du tool `ask_number` dans `backend/tests/unit/graph/tools/test_interactive_tools_number.py` — validation bornes, currency optionnelle, default dans bornes, step > 0 (FR-006)
- [ ] T033 [P] [US3] Test Vitest `frontend/tests/unit/components/chat/widgets/NumberWidget.spec.ts` — formatage milliers, validation bornes côté client, sélecteur devise, équivalent monétaire via `<MoneyDisplay>`, boutons +/- avec step, indicateur « approx. » si fallback constants (FR-022, R7)
- [ ] T034 [US3] Scénario E2E (c) dans `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` — user demande CA → widget XOF → saisit 1000000 → affichage formaté + équivalent EUR → submit → message « ✓ 1 200 000 FCFA » (FR-039, US3 acceptance scenarios)

### Implementation US3

- [ ] T035 [P] [US3] Implémenter le tool `ask_number` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `AskNumberArgs`, validation `min <= max`, `default in [min, max]` si fournis (FR-006)
- [ ] T036 [P] [US3] Ajouter endpoint `GET /api/referential/fx-rates` (router à créer ou réutiliser `backend/app/api/routers/referential.py` si présent) qui retourne les taux XOF↔EUR/USD/CDF depuis `get_fx_rates()`, avec header `Cache-Control: max-age=3600` (FR-022, R7)
- [ ] T037 [US3] Créer le composant `frontend/app/components/chat/widgets/NumberWidget.vue` avec input numérique, sélecteur devise (XOF/EUR/USD/CDF), formatage milliers via `Intl.NumberFormat('fr-FR')`, validation bornes inline, boutons +/- avec step, intégration `<MoneyDisplay>` pour équivalent (cache 1h), indicateur « approx. » si fallback, dark mode, ARIA `spinbutton` (FR-022, SC-006, R7, R8)
- [ ] T038 [US3] Étendre `useChat.ts:submitInteractiveAnswer` pour `NumberResponse` : générer message « ✓ 1 200 000 FCFA » avec formatage devise approprié (FR-028, FR-034)

**Checkpoint** : US3 fonctionnellement complet, équivalents EUR affichés.

---

## Phase 6: User Story 4 — Création d'une entité en un seul formulaire (Priority: P1)

**Goal**: Remplacer 8 questions séquentielles par un seul `show_form` validable en un clic.

**Independent Test**: Demander la création d'un projet à partir d'éléments accumulés. Vérifier : formulaire 8 champs préremplis, validation client, soumission groupée, projet en BDD, message « ✓ Projet créé : ... ».

### Tests US4 (RED first)

- [ ] T039 [P] [US4] Test backend du tool `show_form` dans `backend/tests/unit/graph/tools/test_interactive_tools_form.py` — validation max 10 fields, types whitelist (text/number/select/date/textarea/money), pattern name regex, default cohérent avec type (FR-006, FR-023)
- [ ] T040 [P] [US4] Test Vitest `frontend/tests/unit/components/chat/widgets/FormWidget.spec.ts` — rendu de chaque type de champ via composants enfants, validation zod par champ, bouton submit désactivé si invalid, bouton Annuler ferme le widget (FR-023)
- [ ] T041 [US4] Scénario E2E (d) dans `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` — user trigger création projet → formulaire 8 champs → user remplit/corrige → submit → projet créé en BDD + message dans le fil (FR-039, US4 acceptance scenarios)

### Implementation US4

- [ ] T042 [P] [US4] Implémenter le tool `show_form` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `ShowFormArgs`, validation max 10 fields, types whitelist (FR-006, FR-023)
- [ ] T043 [US4] Créer le composant `frontend/app/components/chat/widgets/FormWidget.vue` qui rend chaque field selon son type via réutilisation de `NumberWidget`, `DateWidget`, `SelectWidget` inline. Validation client zod par champ (mapping `FormFieldValidation` → schéma zod). Bouton submit désactivé si invalid, bouton Annuler. Dark mode, ARIA `form` + `aria-describedby` (FR-023)
- [ ] T044 [US4] Étendre `useChat.ts:submitInteractiveAnswer` pour `FormResponse` : générer message « ✓ Projet créé : Panneaux solaires PME, 5 000 000 FCFA, énergie » à partir du `summary_label` retourné par le backend (FR-028, FR-034)

**Checkpoint** : US4 fonctionnellement complet, US1-US4 = MVP livrable.

---

## Phase 7: User Story 5 — Validation/correction d'extractions (Priority: P2)

**Goal**: Après extraction document, afficher une carte récapitulative avec édition inline.

**Independent Test**: Upload un document → extraction LLM → summary card → user corrige un champ → submit → message « ✓ Corrigé : ... ».

### Tests US5 (RED first)

- [ ] T045 [P] [US5] Test backend du tool `show_summary_card` dans `backend/tests/unit/graph/tools/test_interactive_tools_summary_card.py` — validation max 20 items, mix éditable/non-éditable, types valeur (FR-006)
- [ ] T046 [P] [US5] Test Vitest `frontend/tests/unit/components/chat/widgets/SummaryCardWidget.spec.ts` — mode lecture par défaut, basculement édition au clic « Corriger », bouton « Valider mes corrections », payload modifications structuré (FR-024)
- [ ] T047 [US5] Scénario E2E (e) dans `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` — user upload document → summary card → clic « Corriger » sur capital → édite valeur → submit → message corrigé dans le fil (FR-039, US5 acceptance scenarios)

### Implementation US5

- [ ] T048 [P] [US5] Implémenter le tool `show_summary_card` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `ShowSummaryCardArgs`, max 20 items (FR-006)
- [ ] T049 [US5] Créer le composant `frontend/app/components/chat/widgets/SummaryCardWidget.vue` avec liste items, icône crayon sur items `editable=true`, mode édition global (clic « Corriger »), bouton « Valider » et « Valider mes corrections », payload `{validated, modifications}`, dark mode (FR-024)
- [ ] T050 [US5] Étendre `useChat.ts:submitInteractiveAnswer` pour `SummaryCardResponse` : générer message « ✓ Validé » (sans modifications) ou « ✓ Corrigé : Capital social 6 000 000 FCFA (au lieu de 5 000 000 FCFA) » (FR-028, FR-034)

**Checkpoint** : US5 fonctionnellement complet.

---

## Phase 8: User Story 6 — Saisie d'une date (Priority: P2)

**Goal**: Date picker structuré avec validation min/max et format français.

**Independent Test**: Demander une date d'attestation → date picker → user choisit → message « ✓ 15 mars 2026 ».

### Tests US6 (RED first)

- [ ] T051 [P] [US6] Tests backend `ask_date` et `ask_date_range` dans `backend/tests/unit/graph/tools/test_interactive_tools_date.py` et `test_interactive_tools_date_range.py` — validation bornes, format ISO 8601 (FR-006)
- [ ] T052 [P] [US6] Tests Vitest `frontend/tests/unit/components/chat/widgets/DateWidget.spec.ts` et `DateRangeWidget.spec.ts` — date picker natif HTML5, validation min/max, format `Intl.DateTimeFormat('fr-FR', {dateStyle: 'long'})` (R8)

### Implementation US6

- [ ] T053 [P] [US6] Implémenter les tools `ask_date` et `ask_date_range` dans `backend/app/graph/tools/interactive_tools.py` avec args_schemas `AskDateArgs` et `AskDateRangeArgs` (FR-006)
- [ ] T054 [P] [US6] Créer les composants `frontend/app/components/chat/widgets/DateWidget.vue` et `DateRangeWidget.vue` avec `<input type="date">` natif HTML5 (lang="fr"), validation min/max, formatage français via `Intl.DateTimeFormat`, dark mode, ARIA `datepicker` (FR-018, R8)
- [ ] T055 [US6] Étendre `useChat.ts:submitInteractiveAnswer` pour `DateResponse` (« ✓ 15 mars 2026 ») et `DateRangeResponse` (« ✓ Du 1 janvier au 31 décembre 2026 ») (FR-028, FR-034)

**Checkpoint** : US6 complet.

---

## Phase 9: User Story 7 — Notation/évaluation (Priority: P2)

**Goal**: Auto-évaluation 1-5 / 1-10 avec étoiles/points.

**Independent Test**: Demander une auto-évaluation → étoiles avec hover preview → user clique → message « ✓ 4/5 (Très bien) ».

### Tests US7 (RED first)

- [ ] T056 [P] [US7] Test backend `ask_rating` dans `backend/tests/unit/graph/tools/test_interactive_tools_rating.py` — validation scale ∈ [2,10], `len(labels)==scale` si fourni (FR-006)
- [ ] T057 [P] [US7] Test Vitest `frontend/tests/unit/components/chat/widgets/RatingWidget.spec.ts` — étoiles (scale=5) ou points (scale=10), hover preview avec label, ARIA `radiogroup`, dark mode (FR-018)

### Implementation US7

- [ ] T058 [P] [US7] Implémenter le tool `ask_rating` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `AskRatingArgs` (FR-006)
- [ ] T059 [P] [US7] Créer le composant `frontend/app/components/chat/widgets/RatingWidget.vue` avec étoiles/points cliquables, hover preview, labels textuels optionnels sous chaque cran, dark mode (FR-018)
- [ ] T060 [US7] Étendre `useChat.ts:submitInteractiveAnswer` pour `RatingResponse` : message « ✓ 4/5 (Très bien) » ou « ✓ 7/10 » (FR-028, FR-034)

**Checkpoint** : US7 complet.

---

## Phase 10: User Story 8 — Upload de fichier contextualisé (Priority: P2)

**Goal**: Drag-and-drop d'un fichier directement dans le bottom sheet.

**Independent Test**: Demander un business plan → drop zone → user dépose PDF → progress bar → message « ✓ business_plan.pdf (uploaded) ».

### Tests US8 (RED first)

- [ ] T061 [P] [US8] Test backend `ask_file_upload` dans `backend/tests/unit/graph/tools/test_interactive_tools_file_upload.py` — validation accept whitelist, max_size_mb ≤ 10, multi (FR-006)
- [ ] T062 [P] [US8] Test backend validation MIME signature dans `backend/tests/integration/test_documents_upload_mime.py` — fichier `.pdf` portant un binaire Windows refusé HTTP 415, fichier valide accepté (FR-025, SC-012)
- [ ] T063 [P] [US8] Test Vitest `frontend/tests/unit/components/chat/widgets/FileUploadWidget.spec.ts` — drag-and-drop, refus type MIME non-listé, refus taille > max_size_mb, progress bar, dark mode (FR-025)

### Implementation US8

- [ ] T064 [P] [US8] Implémenter le tool `ask_file_upload` dans `backend/app/graph/tools/interactive_tools.py` avec args_schema `AskFileUploadArgs` (FR-006)
- [ ] T065 [US8] Créer le composant `frontend/app/components/chat/widgets/FileUploadWidget.vue` avec drag-and-drop zone, validation client (extension + taille), progress bar lors de l'upload, intégration avec API `POST /api/documents/upload` existante, payload retour `{document_id, filename, size, mime_type}`, dark mode, ARIA `region` + `aria-busy` pendant upload (FR-025)
- [ ] T066 [US8] Étendre `useChat.ts:submitInteractiveAnswer` pour `FileUploadResponse` : message « ✓ statuts.pdf (uploaded) » (1 fichier) ou « ✓ statuts.pdf, business_plan.pdf (2 fichiers uploaded) » (multi) (FR-028, FR-034)

**Checkpoint** : US8 complet, validation MIME backend opérationnelle.

---

## Phase 11: User Story 9 — Compatibilité dégradée et routing (Priority: P3)

**Goal**: Bouton « Répondre librement » sur tous les widgets + fallback `UnsupportedWidget` pour types inconnus.

**Independent Test**: Pour chaque widget : vérifier bouton « Répondre librement » fonctionnel → ferme widget, ouvre textarea, envoie message texte, marque question `expired`. Pour un type d'enum inconnu (mock) : `UnsupportedWidget` rendu avec textarea.

### Tests US9 (RED first)

- [ ] T067 [P] [US9] Test Vitest unitaire `frontend/tests/unit/components/chat/widgets/UnsupportedWidget.spec.ts` — rendu pour type inconnu, textarea, bouton Envoyer, marquage question `expired` (FR-026)
- [ ] T068 [P] [US9] Test Vitest unitaire `frontend/tests/unit/composables/useInteractiveQuestion.spec.ts` — extension états, helpers formatage devise, validation client, dispatcher type → composant (FR-027)
- [ ] T069 [P] [US9] Test E2E de non-régression QCU/QCM dans `frontend/tests/e2e/F10-widgets-bottom-sheet-complets.spec.ts` — un test par variante F18 (qcu, qcm, qcu_justification, qcm_justification) vérifiant que le rendu et l'envoi fonctionnent toujours après refactor du dispatcher (FR-040, SC-004)

### Implementation US9

- [ ] T070 [P] [US9] Créer le composant `frontend/app/components/chat/widgets/UnsupportedWidget.vue` (textarea + libellé « Type de widget non supporté, répondez librement » + bouton « Envoyer »), logger console.warn, marquer question `expired` (FR-026)
- [ ] T071 [US9] Refactorer `frontend/app/components/chat/InteractiveQuestionInputBar.vue` en dispatcher avec `<component :is="widgetComponent">` et mapping `TYPE_TO_COMPONENT: Record<InteractiveQuestionType, Component>` couvrant les 4 types F18 (vers `SingleChoiceWidget` / `MultipleChoiceWidget`) et les 9 nouveaux types F10. Fallback sur `UnsupportedWidget` pour les types inconnus. Préserver les props (`question`, `loading`, `disabled`) et events (`submit`, `abandon-and-send`) — aucun breaking change pour le parent `InteractiveQuestionHost.vue`. Si la complexité dépasse 800 lignes, extraire la logique QCU/QCM héritée dans `SingleChoiceWidget.vue` et `MultipleChoiceWidget.vue` directement (FR-026, SC-004, R10)
- [ ] T072 [US9] Étendre `frontend/app/composables/useInteractiveQuestion.ts` avec helpers `formatNumberFr`, `formatCurrencyFr`, `formatDateFr`, `formatDateRangeFr`, validation client zod par type, dispatcher type → schéma response. Conserver l'API existante (FR-027, R8)

**Checkpoint** : US9 complet, dispatcher actif, fallback opérationnel, zéro régression sur F18.

---

## Phase 12: Tool Selector & Prompts

**Purpose**: Exposer les nouveaux tools selon une matrice de visibilité par contexte et instruire le LLM via les prompts.

- [ ] T073 [P] Mettre à jour `backend/app/graph/tool_selector_config.py` avec la matrice de visibilité : `ask_yes_no`, `ask_select`, `ask_number`, `ask_date`, `ask_date_range`, `ask_rating`, `ask_file_upload` exposés sur tous les nœuds (chat + 8 spécialistes) ; `show_form` exposé sur profiling, project_tools (US1 stub), application, carbon ; `show_summary_card` exposé sur document, esg_scoring, financing (FR-014, FR-015)
- [ ] T074 Étendre le helper EXISTANT `backend/app/prompts/widget.py` (constante `WIDGET_INSTRUCTION` existante depuis F18) en ajoutant les 9 nouveaux tools dans le decision tree avec exemples concrets, ET en intégrant la **RÈGLE D'OR ACTIONS DESTRUCTIVES** (cf. contracts/destructive_pattern.md). Conserver le contenu F18 existant. En français accentué (FR-016, FR-017, FR-010)
- [ ] T075 [P] Vérifier l'injection effective de `WIDGET_INSTRUCTION` étendu dans les 7 prompts modules : `backend/app/prompts/system.py` (chat global), `esg_scoring.py`, `carbon.py`, `financing.py`, `application.py`, `credit.py`, `action_plan.py`. Pour les 6 modules métier, l'injection est déjà active (vérifié : `from app.prompts.widget import WIDGET_INSTRUCTION` puis concaténation). Si certains modules n'injectent pas encore le helper, l'ajouter. Note : si le « prompt chat » est dans `system.py` ou autre fichier, ajuster le ciblage en Phase B (FR-017)

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Couverture, doc, validation finale.

- [ ] T076 [P] Vérifier la couverture pytest backend ≥ 80 % sur les nouveaux fichiers (`interactive_tools.py`, `interactive_question.py` schémas, `common.py` helper, `documents.py` validation MIME) via `pytest --cov=app.graph.tools.interactive_tools --cov=app.schemas.interactive_question --cov=app.api.routers.documents --cov-report=term-missing` (SC-005)
- [ ] T077 [P] Vérifier la couverture Vitest frontend ≥ 80 % sur les widgets et composables via `npm run test -- --coverage` ; cible composants `chat/widgets/*.vue` et `composables/useInteractiveQuestion.ts`, `composables/useChat.ts` (SC-005)
- [ ] T078 [P] Vérifier l'audit Lighthouse a11y ≥ 95 sur la page chat avec un widget actif (FR-032, FR-033, SC-007)
- [ ] T079 [P] Vérifier que les 9 nouveaux composants supportent `prefers-reduced-motion: reduce` (test manuel ou Playwright avec `await page.emulateMedia({reducedMotion: 'reduce'})`) (FR-031)
- [ ] T080 [P] Vérifier les screenshot tests Playwright pour dark mode sur les 9 widgets (`await page.evaluate(() => document.documentElement.classList.add('dark'))`) (FR-018, SC-008)
- [ ] T081 Mettre à jour `frontend/playwright.config.ts` si nécessaire pour ajouter le projet « F10 widgets » avec retries=2, timeout=30s (FR-039)
- [ ] T082 Vérifier les invariants ESG Mefali sur les nouveaux fichiers : pas de secret hardcodé, multi-tenant (account_id), audit_log F03 sur destructifs, accents français corrects (Constitution + .cc-orchestrator §INVARIANTS)
- [ ] T083 Exécuter le quickstart `specs/031-widgets-bottom-sheet-complets/quickstart.md` étapes 4-6 (démos manuelles + tests intégrés)
- [ ] T084 Final Constitution Re-Check : vérifier les 7 principes, document complexity tracking dans `plan.md` si violation introduite (devrait rester PASS)
- [ ] T085 [P] Vérifier qu'aucun tool destructif n'oublie d'invoquer `log_tool_call` avec `tools_offered` correct (vérification systématique sur les 9 nouveaux tools + 4 destructifs étendus). Couvre l'invariant SC-010 (100 % des nouveaux tools journalisés) (FR-009, SC-010)
- [ ] T086 [P] Vérifier que chaque widget Vue valide la prop `disabled` qui verrouille tous les contrôles en cas de perte SSE — ajouter un test Vitest dédié si non couvert par les tests unitaires composants existants (FR-020)
- [ ] T087 [P] Persister le `response_payload` structuré en métadonnée du message côté `messages` table : étendre le router `POST /api/chat/messages` pour accepter `interactive_question_response_payload: dict | None` et le stocker sur le `Message` (colonne JSONB ou champ existant). Ajouter test backend dédié (FR-035, contracts/sse_events.md)
- [ ] T088 [P] Vérifier que le test Playwright E2E inclut une mesure du nombre de tours de conversation pour la création d'un projet (US4) — confirme la réduction de 8 tours à ≤ 2 tours via `show_form` (SC-002, FR-039 scénario d)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** : pas de dépendance, peut commencer immédiatement.
- **Phase 2 (Foundational)** : dépend de Phase 1. Bloque toutes les user stories. Tests Pydantic + helper destructive + migration en parallèle.
- **Phase 3-11 (User Stories US1-US9)** : peuvent commencer après Phase 2. Indépendantes les unes des autres pour la majorité (US9 dépend des US1-US8 pour le test de dispatcher complet).
- **Phase 12 (Tool Selector & Prompts)** : peut commencer une fois les tools des phases 3-11 implémentés.
- **Phase 13 (Polish)** : finale, dépend de toutes les phases.

### User Story Dependencies

- **US1** (P1, MVP) : indépendante. Démarre après Phase 2.
- **US2** (P1) : indépendante.
- **US3** (P1) : indépendante (T036 endpoint fx_rates peut être différé si fallback constants suffisent).
- **US4** (P1) : indépendante. Réutilise `NumberWidget`, `DateWidget`, `SelectWidget` mais peut commencer en parallèle avec stubs.
- **US5** (P2) : indépendante.
- **US6** (P2) : indépendante.
- **US7** (P2) : indépendante.
- **US8** (P2) : indépendante. Couplée à T014 (validation MIME backend) qui est en Phase 2.
- **US9** (P3) : dépend de la livraison des autres widgets pour le dispatcher complet et les tests régression.

### Within Each User Story

- Tests RED first (RED → GREEN strict).
- Backend tool avant composant Vue.
- Composant Vue avant extension `useChat.ts`.
- Extension `useChat.ts` avant test E2E Playwright.

### Parallel Opportunities

- **Phase 1** : T002, T003, T004 en parallèle.
- **Phase 2** : T005, T006, T007 (tests) en parallèle ; T013, T014 indépendants des autres.
- **Stories** : US1, US2, US3, US4 peuvent démarrer en parallèle après Phase 2 (4 développeurs).
- **Phase 13** : T076-T080 en parallèle.

---

## Parallel Example: User Story 1 (MVP)

```bash
# Lancer les tests US1 en parallèle (RED first):
Task: "T015 Test backend ask_yes_no in backend/tests/unit/graph/tools/test_interactive_tools_yes_no.py"
Task: "T016 Test backend pattern destructif e2e in backend/tests/integration/test_widget_e2e_yes_no_destructive.py"
Task: "T017 Test Vitest YesNoWidget in frontend/tests/unit/components/chat/widgets/YesNoWidget.spec.ts"

# Puis lancer les implémentations indépendantes en parallèle:
Task: "T019 Implémenter ask_yes_no tool"
Task: "T020 Créer stub project_tools.py avec delete_project"
Task: "T022 Composable useHoldToConfirm"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 + US4)

1. Phase 1 (Setup) : 1-2 jours, dépendances installées.
2. Phase 2 (Foundational) : 2-3 jours, migration + modèles + schémas + helpers.
3. Phases 3-6 (US1-US4 P1) : 5-7 jours en parallèle (4 devs) ou 10-12 jours sequentiel.
4. **STOP & VALIDATE** : tests E2E Playwright (a) (b) (c) (d) verts → MVP livrable.
5. Démo / déploiement.

### Incremental Delivery

1. MVP → déploiement.
2. Phase 7 (US5 P2) : summary card + extraction → déploiement.
3. Phase 8-10 (US6-US8 P2) : date, rating, upload → déploiement.
4. Phase 11 (US9 P3) : fallback + non-régression → déploiement.
5. Phase 12-13 : prompts + polish → déploiement final.

### Parallel Team Strategy (4 devs après Phase 2)

- Dev A : US1 (destructif, le plus critique)
- Dev B : US2 (select)
- Dev C : US3 (number) + Phase 12 (tool_selector)
- Dev D : US4 (form)

---

## Notes

- **TDD strict obligatoire** (constitution IV NON-NEGOTIABLE) : tests rouges écrits AVANT toute implémentation.
- **Couverture cible** : ≥ 80 % sur les nouveaux fichiers (constitution IV + SC-005).
- **Dark mode + accessibilité** : non négociable pour chaque composant Vue (constitution VI + FR-018).
- **Pattern destructif** : applicable à tous les tools de mutation futurs ; le helper `requires_destructive_confirmation` est le seul vecteur autorisé.
- **Rétro-compatibilité F18** : les 4 widgets QCU/QCM existants doivent rester intacts ; le test de non-régression (T069) garantit zéro casse.
- **Multi-tenant F02 / Audit log F03 / Money typed F04 / RGPD F05** : tous les invariants `.cc-orchestrator.md` sont préservés.
- **Stubs project_tools.py et autres** : à raccrocher à F25 (projet vert) et F26 (attestation) lors de leur livraison ; en attendant, les tests E2E utilisent des fixtures.
- **Commiter après chaque task ou groupe logique** ; éviter les conflits de fichiers (un fichier = une task à la fois sauf marqué [P]).
