---

description: "Task list — F06 Entité Projet Vert (Module 1.3)"
---

# Tasks: F06 — Entité Projet Vert (Module 1.3)

**Input** : Design documents from `/specs/025-entite-projet-vert/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Branch** : `feat/F06-entite-projet-vert` (alias SpecKit `025-entite-projet-vert`)

**Tests** : Tests TDD obligatoires (cycle Red-Green-Refactor enforce, couverture ≥ 80 %).

**Organization** : Tasks groupées par user story (US1, US2, US3, US4) pour livraison incrémentale.

## Format : `[ID] [P?] [Story] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance bloquante)
- **[Story]** : Rattachement user story (US1, US2, US3, US4) ; absent pour Setup/Foundational/Polish
- Chemins absolus depuis racine repo

## Path Conventions

- **Backend** : `backend/app/`, `backend/tests/`, `backend/alembic/versions/`
- **Frontend** : `frontend/app/`, `frontend/tests/`
- **Specs** : `specs/025-entite-projet-vert/`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer l'environnement de développement et vérifier les prérequis.

- [ ] T001 Vérifier l'activation du venv backend (`source backend/venv/bin/activate`) et des dépendances installées (`pip install -r backend/requirements.txt`) ; vérifier `which python` pointe vers `backend/venv/bin/python`.
- [ ] T002 Vérifier que les migrations F01/F02/F03/F04/F12/F17 sont appliquées localement (`cd backend && alembic current` doit afficher au moins `024_carbone_mix_uemoa`) et que les tables F02 (`accounts`, `refresh_tokens`, `account_invitations`) existent ainsi que la table `audit_log` (F03), `exchange_rates` (F04).
- [ ] T003 [P] Vérifier que les dépendances frontend sont à jour (`cd frontend && npm install`) et que Playwright est installé (`npx playwright install`).

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Migration Alembic, modèles SQLAlchemy, schémas Pydantic, service core et router REST squelette — prérequis bloquants pour toutes les user stories.

**⚠️ CRITICAL** : Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Foundational (TDD — écrire AVANT implémentation, vérifier qu'ils ÉCHOUENT)

- [ ] T004 [P] Écrire `backend/tests/unit/test_project_model.py` : modèle `Project` avec contraintes CHECK (target_amount_pair, status_chk, maturity_chk, financing_structure_chk, location_country_chk, expected_*_positive_chk) ; modèle `ProjectDocument` avec UNIQUE constraint et doc_type_chk ; whitelists `PROJECT_OBJECTIVE_ENV_VALUES`, `PROJECT_MATURITY_VALUES`, `PROJECT_STATUS_VALUES`, `PROJECT_FINANCING_STRUCTURE_VALUES`, `PROJECT_DOC_TYPE_VALUES`.
- [ ] T005 [P] Écrire `backend/tests/unit/test_project_schemas.py` : schémas Pydantic `ProjectCreate`, `ProjectUpdate`, `ProjectSummary`, `ProjectDetail`, `DeleteResult`, `BlockedApplication`, `DuplicateProjectRequest`, `ProjectFilters`, `ProjectListResponse` (validation enum, bornes numériques, validateur Money pair, validateur ISO country alpha-2 majuscules).
- [ ] T006 [P] Écrire `backend/tests/migrations/test_alembic_f06.py` : (a) up/down/up sans erreur ; (b) tables `projects` et `project_documents` créées avec bons types ; (c) colonne `fund_applications.project_id` ajoutée avec FK + index ; (d) backfill : 3 fund_applications orphelines préexistantes → 3 projets auto_generated=true créés, status mappé selon application.status (1 accepted → funded, 2 autres → seeking_funding) ; (e) après backfill, `fund_applications.project_id IS NOT NULL` partout ; (f) idempotence : exécution répétée du backfill ne crée pas de doublons.
- [ ] T007 [P] Écrire `backend/tests/integration/test_project_rls_cross_tenant.py` : 5 cas (PME-A liste / get / update / delete / duplicate sur projet PME-B) → tous échouent en 0 résultat ou 404 ; PME-A INSERT avec account_id=PME-B → RowLevelSecurityViolation. Helper `set_rls_context` (F02) utilisé.

### Implementation Foundational

- [ ] T008 Créer `backend/app/models/project.py` avec classe `Project(Auditable, UUIDMixin, TimestampMixin, Base)` selon `data-model.md` § 2.1 (toutes colonnes, indexes, CHECK contraintes, relation `project_documents`). Inclure les whitelists `PROJECT_*_VALUES` au top du module.
- [ ] T009 Créer `backend/app/models/project_document.py` avec classe `ProjectDocument(UUIDMixin, TimestampMixin, Base)` selon `data-model.md` § 2.2 (UNIQUE constraint, indexes, CHECK doc_type, back_populates `project`).
- [ ] T010 Modifier `backend/app/models/application.py` : ajouter colonne `project_id: Mapped[uuid.UUID]` (UUID FK projects.id ondelete='RESTRICT', nullable=False post-migration, index=True) + relation `project: Mapped["Project"]`.
- [ ] T011 Modifier `backend/app/core/auditable.py` : ajouter `"Project"` dans `AUDITABLE_MODELS` ; ajouter `"ProjectDocument"` dans `EXEMPT_MODELS`.
- [ ] T012 Créer la migration Alembic `backend/alembic/versions/025_create_projects.py` (revision=`025_create_projects`, down_revision=`024_carbone_mix_uemoa`) selon `data-model.md` § 3 : (1) CREATE TABLE projects + indexes + CHECK ; (2) CREATE TABLE project_documents + indexes + UNIQUE + CHECK ; (3) ALTER TABLE fund_applications ADD COLUMN project_id NULL + FK + INDEX ; (4) backfill SQL CTE PostgreSQL + fallback Python loop SQLite ; (5) ALTER COLUMN project_id SET NOT NULL ; (6) RLS ENABLE+FORCE + 2 policies par table (skip SQLite). Downgrade symétrique. Tester localement `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.
- [ ] T013 Créer `backend/app/modules/projects/__init__.py` (vide).
- [ ] T014 Créer `backend/app/modules/projects/schemas.py` avec tous les schémas Pydantic v2 strict de `data-model.md` § 4 (ProjectBase, ProjectCreate, ProjectUpdate, ProjectSummary, ProjectDetail, ProjectDocumentRead, DeleteResult, BlockedApplication, DuplicateProjectRequest, ProjectFilters, ProjectListResponse), avec field_validators pour les enums + model_validator Money pair pour ProjectBase.

---

## Phase 3 : User Story 1 — Modéliser plusieurs projets verts distincts (Priority: P1)

**Goal** : Permettre à une PME de créer/lire/modifier/supprimer plusieurs projets verts distincts via UI et API REST, avec audit log F03 et RLS F02 actifs.

**Independent Test** : Créer 3 projets via UI, vérifier en BDD que les 3 lignes ont `account_id` correct, que l'audit log F03 contient 3 entrées `create source_of_change='manual'`, et que `/profile/projects` affiche les 3 cards.

### Tests for User Story 1 (TDD — écrire AVANT implémentation)

- [ ] T015 [P] [US1] Écrire `backend/tests/integration/test_project_crud.py` : POST /api/projects (création valide → 201 avec id généré ; payload invalide → 400) ; GET /api/projects (liste paginée 25/page, filtre status/maturity/objective_env/auto_generated, tri created_at DESC) ; GET /api/projects/{id} (détail avec project_documents joints + applications_count) ; PATCH /api/projects/{id} (mise à jour partielle, vérifie 1 audit_log par champ modifié) ; DELETE /api/projects/{id}?force=false sans applications → soft-delete (status='cancelled').
- [ ] T016 [P] [US1] Écrire `backend/tests/integration/test_project_audit_log.py` : (a) POST UI manual → audit_log create source='manual' ; (b) PATCH 2 champs → 2 audit_log update ; (c) DELETE soft → audit_log update field=status old=draft new=cancelled ; (d) actor_metadata contient `tool_name=null` pour mutations UI.
- [ ] T017 [P] [US1] Écrire `frontend/tests/unit/ProjectCard.spec.ts` : props (project), affichage nom/status/maturity/montant via `<MoneyDisplay>`/objective_env via `<ProjectImpactBadges>` (mock)/applications_count badge ; emits `view-applications` clic bouton ; dark mode classes (`dark:bg-dark-card`, `dark:text-surface-dark-text`).
- [ ] T018 [P] [US1] Écrire `frontend/tests/unit/ProjectForm.spec.ts` : modes `create | edit | duplicate` ; validation Pydantic-équivalent (name required, target_amount Money pair) ; emits `submit` avec payload normalisé ; `<ProjectStatusSelector>` mock.
- [ ] T019 [P] [US1] Écrire `frontend/tests/unit/ProjectStatusSelector.spec.ts` : ARIA `role="combobox"` + `aria-expanded` ; selection par clavier (flèches + Enter) ; libellés français.
- [ ] T020 [P] [US1] Écrire `frontend/tests/unit/useProjects.spec.ts` : composable expose `listProjects(filters)`, `getProject(id)`, `createProject(payload)`, `updateProject(id, fields)`, `deleteProject(id, force)`, `duplicateProject(id, newName)`, `linkDocument(...)`, `getProjectApplications(id)` ; mock `$fetch` ; gestion error.

### Implementation for User Story 1

- [ ] T021 [US1] Créer `backend/app/modules/projects/service.py` avec fonctions async (utilisant `AsyncSession`) :
  - `list_projects(db, account_id, filters: ProjectFilters) -> ProjectListResponse` (LIMIT/OFFSET, count distinct, applications_count via sous-select).
  - `get_project(db, account_id, project_id: UUID) -> ProjectDetail | None` (selectinload `project_documents`).
  - `create_project(db, account_id, user_id, payload: ProjectCreate) -> ProjectDetail` (insert avec account_id).
  - `update_project(db, account_id, project_id, payload: ProjectUpdate) -> ProjectDetail | None`.
  - `soft_delete_project(db, account_id, project_id, force: bool) -> DeleteResult` (vérifie applications actives, puis status='cancelled').
- [ ] T022 [US1] Créer `backend/app/modules/projects/router.py` avec 5 endpoints (GET liste, GET détail, POST create, PATCH update, DELETE soft) protégés par `Depends(get_current_user)`. Inclure tag OpenAPI `["projects"]`.
- [ ] T023 [US1] Modifier `backend/app/main.py` (zone interdite — modification minimale) : ajouter `from app.modules.projects.router import router as projects_router` et `app.include_router(projects_router, prefix="/api/projects", tags=["projects"])`. AUCUNE autre modification de main.py.
- [ ] T024 [US1] Vérifier en local : démarrer backend + tester via curl les 5 endpoints CRUD selon `quickstart.md` § 2-3.
- [ ] T025 [US1] [P] Créer `frontend/app/types/project.ts` avec types TypeScript `Project`, `ProjectSummary`, `ProjectDetail`, `ProjectFilters`, `ObjectiveEnvValue`, `ProjectStatus`, `ProjectMaturity`, `FinancingStructure`, `DocType`, `Money` (réutilisé F04).
- [ ] T026 [US1] Créer `frontend/app/composables/useProjects.ts` selon `data-model.md` API REST § 4 (8 méthodes : listProjects, getProject, createProject, updateProject, deleteProject, duplicateProject, linkDocument, getProjectApplications) avec `useFetchAuth`.
- [ ] T027 [US1] Créer `frontend/app/stores/projects.ts` (Pinia) avec state (`projects`, `currentProject`, `filters`, `loading`, `error`), actions wrappant `useProjects`, getters `activeProjects` (status ≠ cancelled/closed), `archivedProjects`, `byStatus`.
- [ ] T028 [US1] [P] Créer `frontend/app/components/projects/ProjectStatusSelector.vue` : sélecteur ARIA-conforme avec props `:modelValue` et `:statuses` (liste paramétrable), libellés FR, dark mode complet.
- [ ] T029 [US1] [P] Créer `frontend/app/components/projects/ProjectImpactBadges.vue` : badges visuels pour `objective_env` + impacts (`expected_jobs_created`, `expected_impact_tco2e`, etc.) ; props `:project`, ARIA `role="list"`, dark mode.
- [ ] T030 [US1] Créer `frontend/app/components/projects/ProjectCard.vue` : card complète réutilisant `<MoneyDisplay>` (F04), `<ProjectImpactBadges>` (T029), bouton « Voir candidatures » avec `applications_count` badge ; emits `view-applications` ; dark mode.
- [ ] T031 [US1] Créer `frontend/app/components/projects/ProjectForm.vue` : formulaire multi-mode (`create | edit | duplicate`), validation côté client miroir Pydantic ; champs : name, description, objective_env (multi-select), maturity, status (`<ProjectStatusSelector>`), target_amount Money paire, duration_months, financing_structure, expected_*, location_country/region ; emits `submit` ; dark mode.
- [ ] T032 [US1] Créer `frontend/app/components/projects/ProjectFilters.vue` : filtres (status, maturity, objective_env, auto_generated) URL-synchronisés via query params ; dark mode.
- [ ] T033 [US1] Créer `frontend/app/components/projects/ProjectList.vue` : grid de `<ProjectCard>` + pagination + état vide + état chargement ; dark mode.
- [ ] T034 [US1] Créer `frontend/app/pages/profile/projects/index.vue` : page liste avec `<ProjectFilters>` + `<ProjectList>` ; titre H1 « Mes Projets » ; bouton CTA « Créer un projet » → `/profile/projects/new` ; dark mode.
- [ ] T035 [US1] Créer `frontend/app/pages/profile/projects/new.vue` : page création avec `<ProjectForm mode="create">` ; après submit OK → redirect vers `/profile/projects/[id]` ; dark mode.
- [ ] T036 [US1] Créer `frontend/app/pages/profile/projects/[id].vue` : page édition avec `<ProjectForm mode="edit" :initial-project="project">` + bouton « Dupliquer » → `/profile/projects/[id]/duplicate` ; dark mode.
- [ ] T037 [US1] Créer `frontend/app/pages/profile/company.vue` en y déplaçant le contenu actuel de `frontend/app/pages/profile.vue` (fiche entreprise existante).
- [ ] T038 [US1] Refactorer `frontend/app/pages/profile.vue` en page index avec navigation onglets (« Entreprise » → `/profile/company`, « Mes Projets » → `/profile/projects`) ; redirige par défaut vers `/profile/company` si aucune sous-route.
- [ ] T039 [US1] Modifier `frontend/app/layouts/default.vue` (zone interdite — modification minimale) : ajouter lien sidebar « Mes Projets » avec icône arbre/feuille verte et badge compte projets actifs (lecture via store).

**Checkpoint** : User story 1 doit être testable indépendamment. Tests d'intégration backend (T015-T016) et frontend (T017-T020) passent. CRUD UI complet et fonctionnel.

---

## Phase 4 : User Story 2 — Candidater à plusieurs offres en parallèle pour le même projet (Priority: P1)

**Goal** : Lier les `FundApplication` au `Project` via `project_id` (NOT NULL post-backfill), exposer `GET /api/projects/{id}/applications`, modifier la création d'application pour exiger `project_id`.

**Independent Test** : Créer un projet via US1, lancer 2 applications vers 2 fonds différents en sélectionnant le projet, vérifier `GET /api/projects/{id}/applications` retourne 2 entrées.

### Tests for User Story 2 (TDD)

- [ ] T040 [P] [US2] Écrire `backend/tests/integration/test_project_applications.py` : (a) GET /api/projects/{id}/applications avec 2 applications → 200 + 2 entrées ; (b) GET avec 0 application → 200 + [] ; (c) GET sur projet PME-B → 404 (RLS) ; (d) après création application avec project_id → la liste s'incrémente.
- [ ] T041 [P] [US2] Écrire `backend/tests/integration/test_application_requires_project.py` : POST /api/applications sans project_id → 400 (validation Pydantic) ; POST avec project_id d'un autre account → 404 (RLS) ; POST OK → application liée correctement.

### Implementation for User Story 2

- [ ] T042 [US2] Modifier `backend/app/modules/applications/schemas.py` (si existe) ou équivalent (`backend/app/modules/financing/schemas.py` selon le module qui héberge ApplicationCreate) : ajouter `project_id: UUID` REQUIRED dans `FundApplicationCreate`.
- [ ] T043 [US2] Modifier `backend/app/modules/applications/service.py` (ou équivalent) : `create_fund_application` reçoit `project_id`, vérifie que le projet appartient au `account_id` (via SELECT + RLS), insère avec `project_id`.
- [ ] T044 [US2] Ajouter au router projets : `GET /api/projects/{project_id}/applications` qui retourne `list[ApplicationSummary]` (mock-up ou réutilise le schéma existant).
- [ ] T045 [US2] Modifier `backend/app/graph/tools/financing_tools.py` ou `backend/app/graph/tools/application_tools.py` : le tool `create_fund_application` (existant) reçoit désormais `project_id` REQUIRED dans son args_schema ; la docstring instruit le LLM d'appeler `list_projects` au préalable et de demander confirmation à l'utilisateur si plusieurs projets sont éligibles.
- [ ] T046 [US2] [P] Modifier `frontend/app/pages/financing/[id].vue` (ou équivalent — la page de détail fonds avec bouton « Candidater ») : ajouter un sélecteur de projet (dropdown) avant la création de candidature ; charger la liste via `useProjects().listProjects({status: 'seeking_funding,funded,in_execution'})`. Bloquer l'envoi si aucun projet sélectionné.
- [ ] T047 [US2] [P] Modifier `frontend/app/pages/applications/new.vue` (ou équivalent) : sélecteur projet ; si l'utilisateur arrive depuis `/profile/projects/[id]` avec un query param `?project_id=X`, pré-sélectionner.

**Checkpoint** : User stories 1 et 2 sont indépendamment livrables. Aucune `FundApplication` n'est créée sans `project_id`.

---

## Phase 5 : User Story 3 — Le LLM propose la création d'un projet vert pré-rempli depuis le chat (Priority: P2)

**Goal** : Implémenter les 7 tools LangChain projet, instruire le chat node à proposer la création de projets pré-remplis via `ask_interactive_question` (F18).

**Independent Test** : Lancer une conversation où la PME mentionne une activité polluante, observer que le LLM appelle `ask_interactive_question`, répondre « Oui », observer `create_project` invoqué, vérifier audit log avec `source_of_change='llm'` et `tool_name='create_project'`.

### Tests for User Story 3 (TDD)

- [ ] T048 [P] [US3] Écrire `backend/tests/unit/test_project_tools_unit.py` : 7 tools mocked (list_projects, get_project, create_project, update_project, delete_project, duplicate_project, link_document_to_project) — sérialisation JSON, gestion erreurs (`{ok: false, error: "..."}`).
- [ ] T049 [P] [US3] Écrire `backend/tests/integration/test_project_tools_integration.py` : tools via graph LangGraph avec scope `source_of_change('llm')` ; vérifie `audit_log.source_of_change='llm'` et `actor_metadata.tool_name=<tool>` ; vérifie RLS appliquée (cross-tenant échoue).
- [ ] T050 [P] [US3] Écrire `backend/tests/integration/test_create_project_with_source.py` : conversation où LLM appelle `cite_source(source_id_X)` puis `create_project(target_amount=...)` → projet créé avec montants ; pas de retry validator.
- [ ] T051 [P] [US3] Écrire `backend/tests/integration/test_create_project_without_source.py` : conversation où LLM appelle `create_project(target_amount=...)` sans `cite_source` → validator `source_required.py` retry 1x ; échec retry → fallback texte « [montant à confirmer par la PME] » et target_amount NULL.
- [ ] T052 [P] [US3] Écrire `backend/tests/integration/test_delete_project_blocked_by_applications.py` : tool `delete_project(force=False)` avec applications actives → retourne `{ok: false, blocked_by: [...], hint: "..."}` ; tool `delete_project(force=True)` → retourne `{ok: true}` + log structuré INFO `project_force_deleted`.

### Implementation for User Story 3

- [ ] T053 [US3] Créer `backend/app/graph/tools/project_tools.py` selon `contracts/project-tools-langchain.md` § 1-7 : 7 tools async décorés `@tool` avec args_schema Pydantic, lecture account_id/user_id depuis `RunnableConfig.configurable`, appel des fonctions service de `app.modules.projects.service`. Logger structuré pour `delete_project` avec `force=True`. Inclure le `__all__ = ["PROJECT_TOOLS"]` listant les 7 tools.
- [ ] T054 [US3] Étendre `backend/app/modules/projects/service.py` avec :
  - `duplicate_project(db, account_id, user_id, source_id, new_name) -> ProjectDetail` : SELECT source, INSERT copie sans id/created_at/updated_at/auto_generated/project_documents, status='draft', name= new_name OR f"{source.name} (copie)"[:200].
  - `link_document(db, account_id, project_id, document_id, doc_type) -> ProjectDocumentRead` : vérifie project + document appartiennent à l'account (via RLS), INSERT (UNIQUE constraint).
  - `list_project_applications(db, account_id, project_id) -> list[ApplicationSummary]`.
- [ ] T055 [US3] Étendre `backend/app/modules/projects/router.py` avec 2 endpoints supplémentaires : `POST /api/projects/{id}/duplicate` et `GET /api/projects/{id}/applications`.
- [ ] T056 [US3] Modifier `backend/app/graph/tool_selector_config.py` (zone semi-protégée — modification ciblée) :
  - Ajouter `"list_projects"` dans `MODULE_TOOL_MAPPING['chat']` et `PAGE_TOOL_MAPPING['chat_global']`.
  - Ajouter `"list_projects"`, `"get_project"` dans `PAGE_TOOL_MAPPING['profile']`.
  - Créer nouvelle entrée `PAGE_TOOL_MAPPING['profile_projects']` avec les 7 tools projet.
  - Ajouter pattern `(re.compile(r"^/profile/projects(?:/|$)"), "profile_projects")` dans `_PATH_TO_SLUG_PATTERNS` AVANT `(re.compile(r"^/profile(?:/|$)"), "profile")` (l'ordre compte).
  - Vérifier que `MAX_TOOLS_PER_TURN=14` reste respecté (les 7 tools projet sont mutuellement exclusifs avec `chat_global`).
- [ ] T057 [US3] Modifier `backend/app/graph/nodes.py` : injecter `PROJECT_TOOLS` dans le `chat` ToolNode (cf. pattern existant pour memory_tools F12). Aucune autre modification.
- [ ] T058 [US3] Modifier `backend/app/api/chat.py` : renommer `_load_profile_for_state` en `_load_full_context_for_state` (ou ajouter `_load_projects_for_state`) qui retourne `{"profile": {...}, "projects": [list of active projects]}` ; injecter dans le state LangGraph. Mettre à jour les 2 appels existants à `_load_profile_for_state` (ligne ~366 et ~925 selon grep).
- [ ] T059 [US3] [P] Modifier `backend/app/prompts/application.py` : ajouter section « PROJET CIBLE — OBLIGATOIRE AVANT CANDIDATURE : Avant de créer un dossier de candidature (`create_fund_application`), tu DOIS identifier le projet de la PME concerné. Appelle `list_projects` pour voir les projets actifs. Si aucun projet n'existe ou si la PME hésite, propose `ask_interactive_question` avec choix « Créer un nouveau projet » / « Choisir un projet existant ». Ne jamais créer une candidature sans `project_id`. ».
- [ ] T060 [US3] [P] Modifier `backend/app/prompts/financing.py` : section similaire à T059 avec adaptation au contexte du module financement.
- [ ] T061 [US3] Modifier `backend/app/graph/validators/source_required.py` : ajouter `create_project` et `update_project` à la whitelist des tools dont les chiffres `target_amount_*`/`expected_impact_*` sont vérifiés. (Vérifier l'existence de cette whitelist ; ajouter si nécessaire.)
- [ ] T062 [US3] [P] Créer `frontend/app/components/projects/DuplicateProjectModal.vue` : modale avec input « Nouveau nom » + boutons « Annuler / Dupliquer » ; `useFocusTrap` ; ARIA `role="dialog" aria-modal="true"` ; dark mode.
- [ ] T063 [US3] Créer `frontend/app/pages/profile/projects/[id]/duplicate.vue` : page dédiée avec `<ProjectForm mode="duplicate" :source-project="project">` (le formulaire est pré-rempli) + bouton submit qui appelle `useProjects().duplicateProject(id, newName)` ; redirige vers `/profile/projects/[newId]`.

**Checkpoint** : User stories 1, 2 et 3 fonctionnent. Le LLM peut créer un projet via tool ; audit log capture `source_of_change='llm'`.

---

## Phase 6 : User Story 4 — Dupliquer un projet existant (Priority: P2)

**Goal** : Implémenter le flux UI complet de duplication (déjà partiellement couvert par US3 côté backend/tool ; complète le côté UI et tests E2E).

**Independent Test** : Créer un projet via US1, accéder à `/profile/projects/[id]/duplicate`, soumettre avec nouveau nom, vérifier nouveau projet en BDD avec champs identiques sauf id, name, status='draft', auto_generated=false ; project_documents non copiés.

### Tests for User Story 4 (TDD)

- [ ] T064 [P] [US4] Écrire `backend/tests/integration/test_project_duplicate.py` : (a) duplique projet complet → nouveau projet avec tous champs métier copiés sauf id/created_at/auto_generated ; (b) status forcé draft (même si source='funded') ; (c) project_documents NON copiés ; (d) actor_metadata contient `duplicated_from=<source_id>` ; (e) suffix `' (copie)'` automatique si new_name absent.
- [ ] T065 [P] [US4] Écrire `frontend/tests/unit/DuplicateProjectModal.spec.ts` : rendu modale, focus trap, validation new_name (max 200 chars), emits `submit` et `cancel` ; dark mode.

### Implementation for User Story 4

- [ ] T066 [US4] Vérifier que T054 (service `duplicate_project`) et T055 (endpoint POST duplicate) sont complets et alignés avec FR-016.
- [ ] T067 [US4] Vérifier que T056 (tool selector) inclut `duplicate_project` dans `profile_projects`.
- [ ] T068 [US4] Vérifier que T063 (page `[id]/duplicate.vue`) appelle correctement `useProjects().duplicateProject` et redirige vers le nouveau projet.

**Checkpoint** : Toutes user stories US1-US4 fonctionnent.

---

## Phase 7 : Polish & Cross-Cutting Concerns

**Purpose** : Tests E2E Playwright, finitions de couverture, vérification accessibilité, vérification performance.

### Tests E2E Playwright

- [ ] T069 [P] Créer `frontend/tests/e2e/F06-helpers.ts` : helpers mock backend (login mock, crée fixture user, mock POST /api/projects, mock GET /api/projects, mock POST duplicate, mock DELETE).
- [ ] T070 Créer `frontend/tests/e2e/F06-entite-projet-vert.spec.ts` avec 4 scénarios indépendants :
  - **Scenario US1** « Création projet via UI + audit log » : login → /profile/projects/new → remplir formulaire complet (name, description, objective_env=[renewable_energy,mitigation], maturity=pilot, target_amount={50000000, XOF}, expected_impact_tco2e=120) → submit → redirect /profile/projects/[id] → vérifier la card visible sur /profile/projects → naviguer vers /historique?entity_type=projects → vérifier 1 entrée create source_of_change='manual'.
  - **Scenario US3** « Création projet via tool LLM + audit log » : login → /chat → envoyer message « J'ai un atelier qui utilise des générateurs diesel » → mock SSE LLM appelle `ask_interactive_question` → cliquer choix « Oui, crée le projet pré-rempli » → mock SSE LLM appelle `cite_source(...)` puis `create_project(...)` → vérifier toast « Projet créé » → naviguer /profile/projects → vérifier nouvelle card avec badge « Créé par l'IA » → naviguer /historique → vérifier entrée source_of_change='llm' tool_name='create_project'.
  - **Scenario US4** « Duplication projet champ-à-champ » : login (avec projet seedé) → /profile/projects/[id] → cliquer « Dupliquer » → /profile/projects/[id]/duplicate → modifier new_name='Site B' → submit → redirect vers nouveau projet → vérifier statut='draft' (forcé) + tous autres champs identiques (description, objective_env, target_amount, expected_*) + project_documents vides.
  - **Scenario US1+US2** « Refus suppression projet avec applications actives » : login (avec projet ayant 1 application active seedée) → /profile/projects/[id] → cliquer « Supprimer » → mock 409 conflict + payload blocked_by → vérifier dialog « Cette suppression est bloquée par 1 candidature active » + bouton « Forcer la suppression » → cliquer « Forcer » → mock 200 → vérifier statut projet='cancelled' (badge « Annulé ») + application conservée.

### Couverture & lint

- [ ] T071 Lancer `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app/modules/projects --cov=app/graph/tools/project_tools --cov=app/models/project --cov=app/models/project_document --cov-report=term-missing` ; vérifier couverture ≥ 80 % sur les modules F06.
- [ ] T072 Lancer `cd frontend && npm run test -- --coverage` ; vérifier couverture composants/composable/store F06 ≥ 80 %.
- [ ] T073 Vérifier syntaxe Python : `cd backend && source venv/bin/activate && python -m py_compile $(find app -name '*.py')`.
- [ ] T074 [P] Vérifier syntaxe TypeScript : `cd frontend && npx nuxt typecheck` (si dispo) ou `npm run build` doit passer sans erreur.

### Accessibilité

- [ ] T075 [P] Audit aXe sur les pages `/profile`, `/profile/projects`, `/profile/projects/new`, `/profile/projects/[id]` : 0 violation `serious` ou `critical`.
- [ ] T076 [P] Vérifier ARIA roles sur les 7 composants (`ProjectCard role="article"`, `ProjectStatusSelector role="combobox"`, `DuplicateProjectModal role="dialog" aria-modal="true"`, `ProjectImpactBadges role="list"`, `ProjectFilters role="search"` ou `region`).

### Dark mode

- [ ] T077 [P] Audit visuel des 7 composants dans 3 thèmes (light, dark, mixed) : aucun élément à fond clair sans variante `dark:` correspondante.

### Performance

- [ ] T078 Mesurer p95 sur les 5 endpoints REST principaux via `wrk` ou `ab` ; cibles : list < 80 ms, get/create < 100 ms, duplicate < 150 ms.
- [ ] T079 Mesurer durée migration Alembic up/down/up sur PostgreSQL local avec ~1000 fund_applications historiques ; cible < 30 s.

### Documentation

- [ ] T080 [P] Mettre à jour `CLAUDE.md` section « Active Technologies » et « Recent Changes » avec entrée F06 (date 2026-05-07, format identique à F17).
- [ ] T081 [P] Vérifier que `quickstart.md` reflète l'implémentation finale et que les exemples curl fonctionnent.

---

## Synthèse phases & dépendances

```
Phase 1 (Setup)              T001-T003
       │
       ▼
Phase 2 (Foundational)       T004-T014
       │
       ▼
Phase 3 (US1 P1)             T015-T039
       │
       ▼
Phase 4 (US2 P1)             T040-T047
       │
       ▼
Phase 5 (US3 P2)             T048-T063
       │
       ▼
Phase 6 (US4 P2)             T064-T068
       │
       ▼
Phase 7 (Polish)             T069-T081
```

### Tâches parallélisables intra-phase

- Phase 2 : T004, T005, T006, T007 (tests TDD différents fichiers).
- Phase 3 : T015, T016, T017, T018, T019, T020 (tests TDD ; T028, T029 (composants indépendants).
- Phase 4 : T040, T041 (tests indép.) ; T046, T047 (pages indép.).
- Phase 5 : T048-T052 (tests indép.) ; T059, T060, T062 (fichiers indép.).
- Phase 7 : T069, T080, T081 (fichiers indép.) ; T071, T072 (différentes commandes).

### Couverture cible
- Modules F06 backend : ≥ 80 %.
- Composants frontend F06 : ≥ 80 %.
- 4 scénarios E2E Playwright passants en CI.
- 0 régression sur les 1674 tests baseline F17.
