---
description: "Task list for F09 — Back-Office Admin Complet (Module 9)"
---

# Tasks: F09 — Back-Office Admin Complet

**Input**: Design documents from `/specs/035-f09-back-office-admin/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: TDD obligatoire (rule globale projet, 80 % coverage min). Tests E2E (4 obligatoires) + tests d'intégration triggers PostgreSQL inclus.

**Organization**: Tasks groupées par sprint (4 sprints) puis par user story pour permettre implémentation/test/livraison incrémentale.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallèle (fichiers différents, aucune dépendance)
- **[Story]**: US1 / US2 / US3 / US4 / US5 / US6 / US7 / US8 / US9 (cf. spec.md)
- Chemins absolus des fichiers (par convention projet)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Préparer l'environnement et les outils de mesure communs.

- [ ] **T001** [P] Créer le dossier vide `backend/app/modules/admin/` (existe partiellement via F02). Vérifier présence de `router.py` et `middleware.py` (créés F02). Si absents, créer squelette router central qui include les sous-routers à venir.
- [ ] **T002** [P] Vérifier `bcrypt`, `secrets`, `Jinja2`, `aiosmtplib` sont dans `backend/requirements.txt`. Ajouter si absents.
- [ ] **T003** [P] Créer le dossier vide `backend/tests/integration/admin/` (créer si absent), `backend/tests/integration/triggers/` (NOUVEAU), `backend/tests/e2e/` (créer si absent), `backend/tests/integration/conformity/` (NOUVEAU).
- [ ] **T004** [P] Créer le dossier vide `frontend/app/components/admin/` (existe partiellement via F23 pour skills/). Préparer sous-dossiers `badges/`, `forms/`, `companies/`.
- [ ] **T005** [P] Créer le dossier vide `frontend/app/pages/admin/` (existe partiellement via F02/F03/F23). Préparer sous-dossiers selon plan.md.
- [ ] **T006** [P] Vérifier que la palette accentuée admin (rouge foncé) est définie dans `frontend/app/assets/css/main.css` via `@theme` (ex `dark:border-admin-accent`). Si absente, ajouter les variables.

---

## Phase 2: Foundational (Migration + Infrastructure Sécurité)

**Purpose**: Migration BDD + table password_reset_tokens + service email + helper sécurité token + audit log helpers admin (pas encore branchés aux routers).

**CRITICAL**: Aucune US ne peut commencer avant Phase 2.

- [ ] **T007** Créer migration Alembic `backend/alembic/versions/035_admin_publication_status_workflow.py` :
  - `revision = "035_admin_publication_status_workflow"`
  - `down_revision = "033_create_skills"`
  - Ajoute colonne `publication_status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK IN ('draft','published')` sur 10 tables (funds, intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills) avec `ADD COLUMN IF NOT EXISTS`.
  - Crée index `ix_<table>_publication_status` sur chaque table.
  - Crée table `password_reset_tokens(id UUID PK, user_id FK users.id ON DELETE CASCADE, token_hash VARCHAR(128) UNIQUE NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())` avec 2 indexes.
  - Crée fonction PL/pgSQL `before_publish_check_sources_verified()` (PG only) + 10 triggers BEFORE UPDATE.
  - Crée fonction PL/pgSQL `before_verify_source_check_different_admin()` + 1 trigger BEFORE UPDATE sur `sources`.
  - Tester up/down sur SQLite (skip triggers PG) et PostgreSQL (full triggers).
- [ ] **T008** Créer modèle SQLAlchemy `backend/app/models/password_reset_token.py` :
  - Classe `PasswordResetToken(UUIDMixin, Base)` avec colonnes user_id, token_hash, expires_at, used_at, created_at, relations user FK.
  - Pas de `TimestampMixin` (created_at suffit, pas d'updated_at car immutable hors used_at).
- [ ] **T009** [P] Créer test unitaire `backend/tests/unit/models/test_password_reset_token_model.py` (TDD — écrire AVANT T008 finalisé) :
  - Test : création avec champs minimum requis OK.
  - Test : violation UNIQUE token_hash → IntegrityError.
  - Test : violation FK user_id (user inexistant) → IntegrityError.
  - Test : DELETE CASCADE depuis users → token supprimé.
  - Test : default created_at = now().
- [ ] **T010** Créer service token sécurité `backend/app/core/security.py` (étendre si existant) :
  - Fonction `generate_reset_token() -> str` : utilise `secrets.token_urlsafe(32)`.
  - Fonction `hash_token(token: str) -> str` : sha256 hex digest.
  - Fonction `verify_token_match(plain: str, hashed: str) -> bool` : compare hash.
- [ ] **T011** [P] Créer test unitaire `backend/tests/unit/core/test_security_token.py` :
  - Test : `generate_reset_token()` retourne string ≥ 32 chars URL-safe.
  - Test : `hash_token(token)` est déterministe (même input → même hash).
  - Test : `hash_token(token)` est différent pour 2 tokens distincts.
  - Test : `verify_token_match(plain, hash)` True si match.
  - Test : `verify_token_match(plain, autre_hash)` False.
- [ ] **T012** Créer service email `backend/app/core/email_service.py` :
  - Classe `EmailService` avec backend pluggable (`console` dev, `smtp` staging, `noop` tests).
  - Méthode `async def send_password_reset_email(user_email: str, reset_link: str)`.
  - Templates Jinja2 dans `backend/app/templates/emails/password_reset.html` et `.txt`.
  - Configuration via env vars `EMAIL_BACKEND`, `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, etc.
- [ ] **T013** [P] Créer test unitaire `backend/tests/unit/core/test_email_service.py` :
  - Test : backend `console` → log dans stdout, retourne success.
  - Test : backend `noop` → ne fait rien, retourne success (pour tests d'intégration).
  - Test : backend `smtp` mocké → vérifie appel SMTP avec bons paramètres.
  - Test : template Jinja2 rendu correctement avec `reset_link`.
- [ ] **T014** Créer helper audit log admin `backend/app/modules/admin/audit_helpers.py` :
  - Fonction `async def log_admin_action(db, admin_id, action: str, entity_type: str, entity_id: UUID, metadata: dict)` qui appelle `audit_log_entry()` (F03) avec préfixe admin standardisé.
  - Fonction `async def log_view_admin_dedup(db, admin_id, account_id)` qui dedup 1/jour : query audit_log entries avec action="view_admin", actor_id=admin_id, entity_id=account_id, created_at >= today_start. Si déjà existant → skip. Sinon → log.
- [ ] **T015** [P] Créer test unitaire `backend/tests/unit/modules/admin/test_audit_helpers.py` :
  - Test : log_admin_action crée 1 entry audit_log.
  - Test : log_view_admin_dedup première fois → crée entry.
  - Test : log_view_admin_dedup même jour 2e fois → skip (pas de nouvelle entry).
  - Test : log_view_admin_dedup même admin different account → crée entry distincte.
  - Test : log_view_admin_dedup nouveau jour → crée entry.

**Checkpoint Phase 2** : Migration prête, infrastructure sécurité (token + email + audit dedup) validée. Aucun router admin encore branché. Phase 3 peut démarrer.

---

## Phase 3: Sprint 1 — Sources Workflow + 4-Yeux Triggers (P1) MVP CRITICAL

**Goal**: Workflow 4-yeux validation source + triggers PostgreSQL + impact analysis. Sans cela, les sprints suivants ne peuvent pas tester le publish gating.

**Independent Test**: Test E2E `test_admin_4_eyes_source_flow.py` — Admin A crée source → Admin A tente verify → 400 → Admin B verify → 200.

### Tests for User Story 2 (4-Yeux Sources) (TDD)

- [ ] **T016** [P] [US2] Créer `backend/tests/integration/triggers/test_trigger_4_eyes_source.py` :
  - Fixture : 2 admins A et B en BDD.
  - Test : Source créée par A en pending → UPDATE verification_status='verified' avec verified_by=A → IntegrityError P0001.
  - Test : Source créée par A en pending → UPDATE verification_status='verified' avec verified_by=B → success.
  - Test : Source en pending → UPDATE verification_status='outdated' (pas verified) → success (trigger n'agit que sur pending→verified).
  - Test : Source verified → UPDATE en outdated par captured_by → success (trigger ne re-fire pas).
  - Test : verified_by_user_id NULL → error message clair.
  - Marker `pytest.mark.requires_postgres`.
- [ ] **T017** [P] [US2] Créer `backend/tests/integration/admin/test_admin_sources_router.py` :
  - Fixture : admin A et B authentifiés.
  - Test : POST `/api/admin/sources` par A → status pending, captured_by=A.
  - Test : PATCH `/api/admin/sources/{id}` par A avec verification_status=verified → 400 + message 4-eyes.
  - Test : PATCH par B avec verification_status=verified → 200, verified_by=B, audit log entry source_verified.
  - Test : GET `/api/admin/sources` filtre par status=pending → ne retourne que pending.
  - Test : GET `/api/admin/sources/{id}/dependents` → retourne dict groupé par type.
  - Test : DELETE `/api/admin/sources/{id}` avec dépendants → 400 sans force, 200 avec force=true.
  - Test : user PME tente GET → 403.

### Implementation US2

- [ ] **T018** [US2] Créer schemas Pydantic `backend/app/modules/admin/schemas.py` (partagés tous sous-routers) :
  - `MetricsOverview`, `DependentsReport`, `PaginatedResponse[T]`, `PublicationStatusEnum`, `VerificationStatusEnum`.
- [ ] **T019** [US2] Créer service sources `backend/app/modules/admin/sources_service.py` :
  - `async def get_dependents(source_id, db) -> DependentsReport` : agrège références depuis 6 tables (indicators, criteria, formulas, emission_factors, simulation_factors, skills) via asyncio.gather.
  - `async def can_delete_source(source_id, db) -> tuple[bool, list[str]]` : retourne (can_delete=False si dépendants existent, list de blockers).
  - `async def soft_delete_with_cascade(source_id, db, force=False, admin_id)` : si force=True, cascade `valid_to=today()` sur dépendants et la source elle-même. Audit log entries pour chaque.
  - `async def create_source(payload, admin_id, db)` : insert source en pending, captured_by=admin_id.
  - `async def update_source(source_id, payload, admin_id, db)` : update avec gestion verification_status (4-yeux respecté par trigger BDD).
- [ ] **T020** [US2] Créer router `backend/app/modules/admin/sources_router.py` :
  - 6 endpoints REST (cf. plan.md FR-008) protégés par `Depends(get_current_admin)`.
  - Gestion `IntegrityError` (P0001) → 400 avec message structuré (parser le message PG pour extraire les infos).
  - Audit log automatique sur create/update/delete via helpers (T014).
- [ ] **T021** [US2] Brancher sous-router dans `backend/app/modules/admin/router.py` (router parent F02) : `router.include_router(sources_router, prefix="/sources", tags=["admin-sources"])`.

### Frontend Composants Partagés US2

- [ ] **T022** [P] [US2] Créer composant `frontend/app/components/admin/badges/PendingBadge.vue` (jaune), `VerifiedBadge.vue` (bleu), `OutdatedBadge.vue` (rouge), `DraftBadge.vue` (gris), `PublishedBadge.vue` (vert). Dark mode complet.
- [ ] **T023** [US2] Créer composant `frontend/app/components/admin/SourcePicker.vue` :
  - Modal avec liste sources verified, filtre par publisher/title, prévisualisation URL (target="_blank").
  - Props : `multiple: boolean`, `selected: Source[]`, `onSelect`.
  - Dark mode obligatoire.
- [ ] **T024** [US2] Créer composant `frontend/app/components/admin/PublishButton.vue` :
  - Props : `entityType: string`, `entityId: UUID`, `disabled: boolean`, `disabledReason?: string` (tooltip).
  - Au clic, appelle `POST /api/admin/<entityType>/{id}/publish` via composable `useAdminPublication`.
  - Gère erreur 400 avec parsing `blocking_sources` → toast erreur listant sources bloquantes.
- [ ] **T025** [US2] Créer composant `frontend/app/components/admin/ImpactAnalysisModal.vue` :
  - Props : `entityType: string`, `entityId: UUID`, `dependents: DependentsReport`.
  - Liste les dépendants groupés par type avec liens vers leur page admin.
  - 2 boutons : "Annuler" (ferme modal), "Forcer la suppression" (cascade, demande confirmation explicite).
- [ ] **T026** [US2] Créer composant `frontend/app/components/admin/forms/SourceForm.vue` :
  - Champs : URL, title, publisher, version, date_publication, page, section.
  - Validation : URL format, title non-vide, publisher requis.
  - Réutilisé par new.vue et [id].vue.

### Frontend Pages US2

- [ ] **T027** [P] [US2] Créer composable `frontend/app/composables/useAdminSources.ts` :
  - Méthodes : `listSources(filters)`, `getSource(id)`, `getDependents(id)`, `createSource(payload)`, `updateSource(id, payload)`, `deleteSource(id, force)`, `verifySource(id)`, `markOutdated(id, reason)`.
  - Wrappe les endpoints `/api/admin/sources/*`.
  - Gère erreurs 400 (4-eyes, dependents).
- [ ] **T028** [US2] Créer page `frontend/app/pages/admin/sources/index.vue` :
  - Tabs "Toutes / Pending / Verified / Outdated" avec compteurs.
  - Table paginée avec colonnes (title, publisher, status badge, captured_by, verified_by, actions).
  - Bouton "Nouvelle source" en haut.
  - Dark mode complet.
- [ ] **T029** [US2] Créer page `frontend/app/pages/admin/sources/new.vue` :
  - Utilise `<SourceForm>` (T026).
  - Sur submit, POST `/api/admin/sources` → redirect vers détail.
- [ ] **T030** [US2] Créer page `frontend/app/pages/admin/sources/[id].vue` :
  - Détail source avec champs en lecture seule.
  - Bouton "Ouvrir le document officiel" (target="_blank").
  - Bouton "Marquer comme vérifiée" visible **uniquement** si `current_user.id !== source.captured_by_user_id`.
  - Bouton "Marquer comme obsolète" avec champ raison.
  - Section "Entités dépendantes" avec `<ImpactAnalysisModal>`.
  - Bouton DELETE avec impact analysis modal.

### E2E US2

- [ ] **T031** [US2] Créer test E2E `backend/tests/e2e/test_admin_4_eyes_source_flow.py` (Pytest + httpx async client) :
  - Setup : 2 admins A et B en BDD.
  - Scénario : login A → POST source → status pending → tente PATCH verify → 400 → login B → PATCH verify → 200 → vérifie audit log.
  - Marker `pytest.mark.e2e`.
- [ ] **T032** [P] [US2] Créer test E2E Playwright `frontend/tests/e2e/admin/source-4-eyes.spec.ts` :
  - Login admin A → naviguer /admin/sources/new → soumettre → vérifier status pending sur liste.
  - Naviguer détail → bouton "Marquer vérifiée" caché.
  - Logout A → login B → naviguer détail → bouton visible → cliquer → vérifier badge Verified.

**Checkpoint Sprint 1** : Workflow 4-yeux source complet (backend + frontend + E2E). Triggers PG validés. Sprint 2 peut maintenant tester le publish gating.

---

## Phase 4: Sprint 2 — CRUD Funds + Intermediaries + Offers + Publish Gating (P1) MVP

**Goal**: 3 sous-routers CRUD critiques + composant générique `<EntityCRUDTable>` + tests publish gating triggers PostgreSQL.

**Independent Test**: Test E2E `test_admin_publish_gating_flow.py` — Admin crée Fund + source pending → publish 400 → fix source → publish 200.

### Tests for User Story 1 (Funds CRUD + Publish Gating) (TDD)

- [ ] **T033** [P] [US1] Créer `backend/tests/integration/triggers/test_trigger_publish_gating.py` :
  - Fixture : 1 source verified, 1 source pending, 1 admin.
  - Test (10x, paramétré sur 10 tables) : créer entité catalogue avec source pending liée → UPDATE publication_status='published' → IntegrityError P0001.
  - Test (10x) : créer entité avec source verified → UPDATE publication_status='published' → success.
  - Test : déjà published → re-UPDATE → no-op (trigger ne re-fire que sur draft→published).
  - Test : draft → draft → no-op.
  - Marker `pytest.mark.requires_postgres`.
- [ ] **T034** [P] [US1] Créer `backend/tests/integration/admin/test_admin_funds_router.py` :
  - Tests : CRUD complet (POST → GET list → GET detail → PATCH → POST publish → DELETE).
  - Test : POST publish avec source pending → 400 + blocking_sources liste.
  - Test : POST publish avec sources verified → 200.
  - Test : PATCH d'un fund published → nouvelle version créée (VersioningMixin F04).
  - Test : DELETE avec candidatures liées → 400 sans force, 200 avec force.
  - Test : user PME → 403.
  - Test : pagination, filtres `fund_type`, `status`, `publication_status`, `theme`, `q`.
- [ ] **T035** [P] [US1] Idem `test_admin_intermediaries_router.py` (CRUD + publish + champs spécifiques).
- [ ] **T036** [P] [US1] Idem `test_admin_offers_router.py` (CRUD + publish + endpoint `/compute-effective`).

### Implementation Backend US1

- [ ] **T037** [US1] Créer service partagé `backend/app/modules/admin/catalog_publish_helper.py` :
  - `async def publish_entity(entity_type: str, entity_id: UUID, admin_id: UUID, db)` : tente UPDATE publication_status, catch IntegrityError P0001, parse message → retourne réponse 400 structurée avec blocking_sources.
  - Audit log entry sur succès `<entity_type>_published`.
- [ ] **T038** [US1] Créer router `backend/app/modules/admin/funds_router.py` :
  - 6 endpoints REST (cf. FR-004).
  - Utilise `catalog_publish_helper` pour POST `/publish`.
  - Versioning F04 sur PATCH d'un fund published.
  - Audit log sur create/update/delete/publish.
- [ ] **T039** [US1] Créer router `backend/app/modules/admin/intermediaries_router.py` (similaire à funds avec champs spécifiques `required_documents`, `fees_structured`, `processing_time_days`, `success_rate`).
- [ ] **T040** [US1] Créer router `backend/app/modules/admin/offers_router.py` :
  - 6 endpoints + endpoint additionnel `POST /api/admin/offers/{id}/compute-effective` qui appelle service F07 `compute_effective_offer()`.
  - Validation : Fund et Intermediary doivent être tous deux `published` avant publish de l'Offer.
- [ ] **T041** [US1] Brancher 3 sous-routers dans `app/modules/admin/router.py` (parent F02).

### Frontend Composants US1

- [ ] **T042** [US1] Créer composant `frontend/app/components/admin/EntityCRUDTable.vue` (générique réutilisable) :
  - Props : `columns: TableColumn[]`, `dataLoader: (filters, page, limit) => Promise<{items, total}>`, `actions: TableAction[]` (edit/delete/duplicate/custom), `searchable: boolean`, `filters: FilterDef[]`.
  - Slots : `header`, `row`, `actions`, `empty-state`.
  - Pagination, tri par colonne, recherche full-text avec debounce.
  - Dark mode complet.
  - Tests unitaires Vitest.
- [ ] **T043** [P] [US1] Créer `frontend/app/components/admin/forms/FundForm.vue`, `IntermediaryForm.vue`, `OfferForm.vue` (3 forms en parallèle).
- [ ] **T044** [US1] Créer composable `frontend/app/composables/useAdminCatalog.ts` (générique typed) :
  - Factory `createAdminCatalogStore<T>(entityType: string)` qui produit méthodes CRUD typed.
  - Réutilisé pour funds, intermediaries, offers (et plus tard 7 autres).
- [ ] **T045** [US1] Créer composable `frontend/app/composables/useAdminPublication.ts` :
  - Méthode `publishEntity(entityType, entityId)` qui appelle endpoint `/publish`.
  - Gère erreur 400 avec parsing `blocking_sources` → toast.

### Frontend Pages US1

- [ ] **T046** [P] [US1] Créer pages `frontend/app/pages/admin/funds/{index,new,[id]}.vue` (3 pages, utilisent `<EntityCRUDTable>`, `<FundForm>`, `<PublishButton>`, `<SourcePicker>`).
- [ ] **T047** [P] [US1] Créer pages `frontend/app/pages/admin/intermediaries/{index,new,[id]}.vue`.
- [ ] **T048** [P] [US1] Créer pages `frontend/app/pages/admin/offers/{index,new,[id]}.vue` (avec bouton "Calcul auto" appelant `/compute-effective`).

### E2E US1

- [ ] **T049** [US1] Créer test E2E `backend/tests/e2e/test_admin_publish_gating_flow.py` :
  - Setup : 2 admins, 1 source pending, 1 source verified.
  - Scénario : Admin POST fund avec sources mixtes → tente publish → 400 listant la source pending → admin B verify la source → re-publish → 200.
  - Marker `pytest.mark.e2e`.
- [ ] **T050** [P] [US1] Créer test E2E Playwright `frontend/tests/e2e/admin/publish-gating.spec.ts` :
  - Login admin → /admin/funds/new → submit → /admin/funds/[id] → cliquer Publier → vérifier toast erreur listant source pending → naviguer source → marquer verified (avec second admin) → revenir au fund → publier → vérifier badge Published.
- [ ] **T051** [P] [US1] Créer test E2E Playwright `frontend/tests/e2e/admin/catalog-funds.spec.ts` :
  - CRUD complet : create, list (pagination, filtres), edit, delete avec impact modal.

**Checkpoint Sprint 2** : 3 sections catalogue critiques (funds, intermediaries, offers) fonctionnelles avec publish gating validé E2E. `<EntityCRUDTable>` réutilisable prouvé. Sprint 3 peut élargir aux 6 autres entités catalogue + support PME.

---

## Phase 5: Sprint 3 — CRUD Étendu Catalogue + Support PME (P1-P2) MVP

**Goal**: 6 sous-routers catalogue restants + 4 sous-routers support (users, companies, attestations, auth public) + endpoint reset-password complet.

### Tests for User Stories 6, 8, 3, 9 (TDD)

- [ ] **T052** [P] [US6] Créer `backend/tests/integration/admin/test_admin_referentials_router.py` (CRUD + publish + cascade indicators).
- [ ] **T053** [P] [US6] Créer `backend/tests/integration/admin/test_admin_indicators_router.py` (CRUD + impact analysis sur criteria).
- [ ] **T054** [P] [US6] Créer `backend/tests/integration/admin/test_admin_criteria_router.py`.
- [ ] **T055** [P] [US8] Créer `backend/tests/integration/admin/test_admin_templates_router.py` (avec upload DOCX mocked).
- [ ] **T056** [P] [US8] Créer `backend/tests/integration/admin/test_admin_emission_factors_router.py` (avec source ADEME).
- [ ] **T057** [P] [US8] Créer `backend/tests/integration/admin/test_admin_simulation_factors_router.py`.
- [ ] **T058** [P] [US3] Créer `backend/tests/unit/modules/admin/test_users_service.py` :
  - Test : `initiate_password_reset(user_id, admin_id)` → token créé en BDD avec expires_at = now + 1h, hash sha256, email sent.
  - Test : `complete_password_reset(token, new_pw)` → vérifie token, hashe pw bcrypt, marque used_at.
  - Test : token expiré → ResetTokenExpiredError.
  - Test : token déjà utilisé → ResetTokenAlreadyUsedError.
  - Test : token invalide (hash mismatch) → ResetTokenInvalidError.
  - Test : `toggle_user_active(user_id, admin_id, reason)` → toggle is_active, audit log avec metadata.
- [ ] **T059** [P] [US3] Créer `backend/tests/integration/admin/test_admin_users_router.py` :
  - Test : POST `/users/{id}/reset-password` → token créé, email envoyé (console log dev), audit log entry.
  - Test : POST `/users/{id}/toggle-active` avec reason → toggle is_active, audit log.
  - Test : POST `/users/{id}/toggle-active` sans reason → 422.
- [ ] **T060** [P] [US3] Créer `backend/tests/integration/auth/test_reset_password_endpoint.py` :
  - Test : POST `/api/auth/reset-password` avec token valide + new_pw → 200, password mis à jour, token used_at marqué.
  - Test : token expiré → 400.
  - Test : token déjà utilisé → 400.
  - Test : password < 8 chars → 422.
- [ ] **T061** [P] [US3] Créer `backend/tests/unit/modules/admin/test_companies_service.py` :
  - Test : `get_company_overview(account_id, admin_id)` retourne profil + projets + scores + attestations + audit_log.
  - Test : appel crée audit log entry view_admin (dedup 1/jour).
- [ ] **T062** [P] [US3] Créer `backend/tests/integration/admin/test_admin_companies_router.py` :
  - Test : GET `/admin/companies/{id}` → 200 + audit log entry.
  - Test : GET deuxième fois même jour → audit log non duplicated.
  - Test : Vérifier visible côté PME via GET `/api/account/audit`.
- [ ] **T063** [P] [US3] Créer `backend/tests/integration/admin/test_admin_attestations_router.py` :
  - Test : POST `/attestations/{id}/revoke` avec reason ≥ 10 chars → 200, revoked_at, revoked_by, revocation_reason set, audit log.
  - Test : reason < 10 chars → 422.
  - Test : Vérifier endpoint public verify retourne `{valid: false, revoked: true, reason}`.
- [ ] **T064** [P] [US9] Créer `backend/tests/integration/conformity/test_no_admin_emails_whitelist.py` :
  - Test : grep récursif `admin_emails` dans `backend/app/` → 0 match.

### Implementation Backend US6, US8, US3, US9

- [ ] **T065** [P] [US6] Créer routers `backend/app/modules/admin/{referentials,indicators,criteria}_router.py` (3 routers en parallèle, similaires).
- [ ] **T066** [P] [US8] Créer routers `backend/app/modules/admin/{templates,emission_factors,simulation_factors}_router.py` (3 routers en parallèle).
- [ ] **T067** [US3] Créer service `backend/app/modules/admin/users_service.py` :
  - `initiate_password_reset()`, `complete_password_reset()`, `toggle_user_active()` (cf. FR-015).
- [ ] **T068** [US3] Créer service `backend/app/modules/admin/companies_service.py` :
  - `get_company_overview(account_id, admin_id, db)` qui agrège profil + projets + candidatures + scores + attestations + audit_log.
  - Appelle `log_view_admin_dedup()` (T014) à chaque appel.
- [ ] **T069** [US3] Créer router `backend/app/modules/admin/users_router.py` (cf. FR-010).
- [ ] **T070** [US3] Créer router `backend/app/modules/admin/companies_router.py` (cf. FR-011).
- [ ] **T071** [US3] Créer router `backend/app/modules/admin/attestations_router.py` (cf. FR-012).
- [ ] **T072** [US3] Modifier `backend/app/modules/auth/router.py` : ajouter endpoint public `POST /api/auth/reset-password` (cf. FR-016).
- [ ] **T073** [US9] Brancher 7 sous-routers (referentials, indicators, criteria, templates, emission_factors, simulation_factors, users, companies, attestations) dans `app/modules/admin/router.py`.

### Frontend Composants Étendus US6, US8, US3

- [ ] **T074** [P] [US6] Créer forms `frontend/app/components/admin/forms/{ReferentialForm,IndicatorForm,CriterionForm}.vue` (3 forms parallèles).
- [ ] **T075** [P] [US8] Créer forms `{TemplateForm,EmissionFactorForm,SimulationFactorForm}.vue` (3 forms parallèles).
- [ ] **T076** [US3] Créer composants `frontend/app/components/admin/companies/CompanyOverview.vue` (read-only profile + projets + scores) et `CompanyActions.vue` (boutons reset password, toggle active, révoquer).
- [ ] **T077** [P] [US3] Créer composables `frontend/app/composables/useAdminUsers.ts`, `useAdminCompanies.ts`, `useAdminAttestations.ts`.

### Frontend Pages Étendues

- [ ] **T078** [P] [US6] Créer pages `pages/admin/referentials/{index,new,[id]}.vue`, `pages/admin/indicators/...`, `pages/admin/criteria/...` (9 pages parallèles, utilisent `<EntityCRUDTable>`).
- [ ] **T079** [P] [US8] Créer pages `pages/admin/templates/...`, `pages/admin/emission-factors/...`, `pages/admin/simulation-factors/...` (9 pages parallèles).
- [ ] **T080** [US3] Créer pages `frontend/app/pages/admin/companies/{index,[account_id]}.vue` (2 pages).
- [ ] **T081** [US3] Créer page `frontend/app/pages/admin/attestations/index.vue` (liste + révocation modal).
- [ ] **T082** [US3] Créer page publique `frontend/app/pages/auth/reset.vue` :
  - Lit token depuis query param.
  - Form : new_password (≥ 8 chars), confirm_password.
  - Submit → POST `/api/auth/reset-password` → redirect vers /login avec success message.

### E2E Sprint 3

- [ ] **T083** [US9] Créer test E2E `backend/tests/e2e/test_admin_isolation_pme.py` :
  - User PME tente GET `/api/admin/funds`, `/api/admin/sources`, etc. → 403.
  - User PME tente POST `/api/admin/users/{id}/reset-password` → 403.
  - Marker `pytest.mark.e2e`.
- [ ] **T084** [P] [US9] Créer test E2E Playwright `frontend/tests/e2e/admin/isolation-pme.spec.ts` :
  - Login user PME → naviguer `/admin/funds` → vérifier redirect vers /dashboard avec query reason=admin_required.
- [ ] **T085** [US3] Créer test E2E `backend/tests/e2e/test_admin_reset_password_flow.py` :
  - Setup : 1 admin, 1 user PME.
  - Scénario : admin POST reset-password → token en BDD → email console log capturé → user POST `/api/auth/reset-password` avec token + new_pw → 200 → user login avec new_pw → success.
  - Marker `pytest.mark.e2e`.
- [ ] **T086** [P] [US3] Créer test E2E Playwright `frontend/tests/e2e/admin/reset-password.spec.ts` :
  - Login admin → /admin/companies/[id] → cliquer "Reset password" → confirmer → vérifier email envoyé (capturé via mock).
  - Logout → naviguer /auth/reset?token=<captured> → soumettre new_pw → vérifier login successful.

**Checkpoint Sprint 3** : Catalogue complet (10 entités), support PME complet (companies, users, attestations), endpoint public reset-password, isolation PME validée. Sprint 4 peut finaliser le polish (métriques, layout, dashboard, doc).

---

## Phase 6: Sprint 4 — Métriques + Layout + Dashboard + Documentation (P2-P3)

**Goal**: Finaliser le back-office avec dashboard métriques, layout polish, documentation runbook.

### Tests for User Story 5 (Metrics) (TDD)

- [ ] **T087** [P] [US5] Créer `backend/tests/unit/modules/admin/test_metrics_service.py` :
  - Test : `compute_overview()` avec fixtures (10 sources mixtes, 50 users, 5 attestations) → MetricsOverview correct.
  - Test : sections placeholder (applications, llm_costs) retournent structure cohérente.
  - Test : performance < 500ms sur 1000 entités (mesure via pytest-benchmark).
- [ ] **T088** [P] [US5] Créer `backend/tests/integration/admin/test_admin_metrics_router.py` :
  - Test : GET `/api/admin/metrics/overview` → 200 + structure complète.
  - Test : user PME → 403.

### Implementation Backend US5

- [ ] **T089** [US5] Créer service `backend/app/modules/admin/metrics_service.py` :
  - `async def compute_overview(db) -> MetricsOverview` avec 1 seule transaction CTE pour performance.
  - Sections : sources (counts + trend 30j), accounts, applications (placeholder), attestations, llm_costs (placeholder).
- [ ] **T090** [US5] Créer router `backend/app/modules/admin/metrics_router.py` :
  - GET `/api/admin/metrics/overview` (cf. FR-013).
- [ ] **T091** [US5] Brancher metrics_router dans `app/modules/admin/router.py`.

### Frontend Sprint 4

- [ ] **T092** [P] [US5] Créer composant `frontend/app/components/admin/MetricsCard.vue` :
  - Props : `title: string`, `mainValue: string|number`, `subMetrics: list[{label, value}]`, `trend30d?: number[]` (sparkline).
  - Rendu sparkline via vue-chartjs ou SVG inline.
  - Dark mode obligatoire.
- [ ] **T093** [US5] Créer composable `frontend/app/composables/useAdminMetrics.ts` (méthode `fetchOverview()`).
- [ ] **T094** [US5] Créer page `frontend/app/pages/admin/metrics/index.vue` :
  - Plusieurs `<MetricsCard>` agencés en grille (sources, accounts, applications placeholder, attestations, llm_costs placeholder).
  - Refresh manuel + auto-refresh 60s (post-MVP).
- [ ] **T095** [US1, US5] Créer page `frontend/app/pages/admin/index.vue` (dashboard accueil admin) :
  - Réutilise `<MetricsCard>` pour les 5 KPIs principaux.
  - Liens rapides vers chaque section.
- [ ] **T096** Modifier layout `frontend/app/layouts/admin.vue` (étendu de F02) :
  - Sidebar gauche : sections Catalogue (10 sous-items expandable) / Sources / Comptes (Companies, Users, Attestations) / Métriques / Audit / Skills.
  - Header : badge "Mode Admin" rouge, toggle theme partagé.
  - Footer minimal.
  - Palette accentuée admin (`dark:border-admin-accent` rouge foncé sur les bordures principales).
  - Dark mode 100 % complet.
  - Responsive (sidebar collapse en hamburger sur mobile).
- [ ] **T097** Polish dark mode toutes pages admin (audit visuel + tests Playwright dark mode toggle).
- [ ] **T098** Validation des liens sidebar pour pages F03 (audit) et F23 (skills) :
  - Vérifier `/admin/audit` charge correctement avec layout admin.
  - Vérifier `/admin/skills/*` charge correctement.

### Documentation Sprint 4

- [ ] **T099** Créer `docs/admin-runbook.md` (français, avec accents) :
  - Procédure : créer une nouvelle source officielle (saisie + 4-yeux).
  - Procédure : créer un nouveau fonds avec sources liées (draft → publish).
  - Procédure : valider une source (workflow 4-yeux, attention "ne pas valider sa propre source").
  - Procédure : gérer un incident PME (consultation + reset password + révocation attestation).
  - Procédure : interpréter les métriques admin.
  - Procédure : gérer une suppression destructive (impact analysis).
  - Procédure : appliquer la migration 035 sur DB existante (avec script `seed_publish_existing_catalog.py`).

### Conformity & Polish Final

- [ ] **T100** Run `pytest --cov=app/modules/admin` → vérifier couverture ≥ 80 %.
- [ ] **T101** Run pytest complet → 0 régression sur les ~935+ tests existants.
- [ ] **T102** Run Playwright suite complète admin → tous les E2E passent.
- [ ] **T103** Vérifier conformity grep `admin_emails` (T064) → 0 match dans `backend/app/`.
- [ ] **T104** Vérifier toutes les pages admin ont dark mode complet (audit visuel + Playwright theme toggle test).
- [ ] **T105** Vérifier middleware `admin.ts` est bien appliqué à toutes les pages admin (Playwright test isolation).

**Checkpoint Sprint 4** : Back-office admin complet, métriques fonctionnelles, layout polish, documentation runbook livrée. F09 prêt pour merge.

---

## Phase 7: Polish & Cross-Cutting Concerns (Optional Post-MVP)

**Purpose**: Améliorations post-MVP non bloquantes pour le merge initial.

- [ ] **T106** [P] Bulk import CSV/Excel pour catalogue (post-MVP).
- [ ] **T107** [P] Workflow `pending_review` intermédiaire entre draft et verified pour sources (post-MVP).
- [ ] **T108** [P] Permissions granulaires intra-admin (`dpo`, `catalog_editor`, `support`) avec policies par sous-router (post-MVP).
- [ ] **T109** [P] Coûts LLM par PME : ajouter `tokens_in/tokens_out/cost_usd` sur `tool_call_logs` + agrégation dans MetricsOverview (post-MVP).
- [ ] **T110** [P] Cache 5 min sur `GET /api/admin/metrics/overview` via `@cache_async` (post-MVP).
- [ ] **T111** [P] Notification PME : email automatique quand admin reset password ou révoque attestation (post-MVP).
- [ ] **T112** [P] Détection patterns anormaux audit_log (admin consulte 100 PME/h → alerte) (post-MVP).
- [ ] **T113** [P] Banner d'avertissement frontend si admin se logue depuis une PME résiduelle (post-MVP).

---

## Récapitulatif Tâches

- **Phase 1 (Setup)** : 6 tâches (T001-T006).
- **Phase 2 (Foundational)** : 9 tâches (T007-T015).
- **Phase 3 (Sprint 1 - Sources + 4-yeux)** : 17 tâches (T016-T032).
- **Phase 4 (Sprint 2 - CRUD critiques)** : 19 tâches (T033-T051).
- **Phase 5 (Sprint 3 - Catalogue étendu + Support PME)** : 35 tâches (T052-T086).
- **Phase 6 (Sprint 4 - Métriques + Polish)** : 19 tâches (T087-T105).
- **Phase 7 (Post-MVP optionnel)** : 8 tâches (T106-T113).

**Total MVP : ~105 tâches sur 4 sprints**. Estimation alignée avec la fiche F09 (3-4 sprints).

## Tâches E2E Obligatoires (4)

1. **T031** : `test_admin_4_eyes_source_flow.py` (US2) — Admin A crée source → Admin A tente verify → 400 → Admin B verify → 200.
2. **T049** : `test_admin_publish_gating_flow.py` (US1) — Admin crée fund avec source pending → publish 400 → fix source via 4-yeux → publish 200.
3. **T083** : `test_admin_isolation_pme.py` (US9) — User PME tente `/api/admin/*` → 403 backend, redirect frontend.
4. **T085** : `test_admin_reset_password_flow.py` (US3) — Admin POST reset-password → token → email → user POST `/api/auth/reset-password` → 200 → login avec new_pw OK.

## Dépendances Inter-Tâches

- T007 (migration) → T009-T031 (tous les tests intégration triggers + sources).
- T008-T013 (infrastructure sécurité) → T067 (users_service).
- T014 (audit helpers) → T020, T038, T067, T068, T071 (tous les routers admin).
- T018 (schemas partagés) → T020, T038, T039, T040, T065, T066, T069, T070, T071, T089.
- T024 (PublishButton) → T046, T047, T048, T078, T079 (toutes les pages CRUD avec publish).
- T042 (EntityCRUDTable) → T046, T047, T048, T078, T079, T080, T081 (toutes les pages liste catalogue + companies + attestations).
- T044 (useAdminCatalog factory) → T046, T047, T048, T078, T079.
- T096 (layout admin finalisé) → T097, T098, T104 (polish + audit dark mode).

## Stratégie de Test

- **Unit tests** : tous les services (T009, T011, T013, T015, T058, T061, T087).
- **Integration tests routers** : tous les sous-routers admin (T017, T034-T036, T052-T057, T059, T060, T062, T063, T088).
- **Integration tests triggers** : T016 (4-yeux) + T033 (publish gating × 10 tables).
- **Conformity tests** : T064 (no admin_emails whitelist).
- **E2E tests obligatoires** : T031, T049, T083, T085 (backend Pytest) + T032, T050, T051, T084, T086 (frontend Playwright).
- **Couverture** : ≥ 80 % sur `app/modules/admin/*` (vérifié T100).
- **Régression** : 0 sur les 935+ tests existants (vérifié T101).
