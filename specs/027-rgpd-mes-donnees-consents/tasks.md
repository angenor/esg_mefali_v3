---

description: "Task list — F05 RGPD : Page Mes Données + Consentements + Export/Suppression"
---

# Tasks: F05 — RGPD : Page « Mes Données » + Consentements + Export/Suppression

**Input** : Design documents from `/specs/027-rgpd-mes-donnees-consents/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Branch** : `feat/F05-rgpd-mes-donnees-consents` (alias SpecKit `027-rgpd-mes-donnees-consents`)

**Tests** : Tests TDD obligatoires (cycle Red-Green-Refactor enforce, couverture ≥ 80 %).

**Organization** : Tasks groupées par user story (US1, US2, US3, US4, US5, US6) pour livraison incrémentale.

## Format : `[ID] [P?] [Story] Description`

- **[P]** : Peut s'exécuter en parallèle (fichiers différents, pas de dépendance bloquante)
- **[Story]** : Rattachement user story (US1, US2, US3, US4, US5, US6) ; absent pour Setup/Foundational/Polish
- Chemins absolus depuis racine repo

## Path Conventions

- **Backend** : `backend/app/`, `backend/tests/`, `backend/alembic/versions/`, `backend/scripts/`
- **Frontend** : `frontend/app/`, `frontend/tests/`
- **Specs** : `specs/027-rgpd-mes-donnees-consents/`
- **Docs** : `docs/`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparer l'environnement de développement et vérifier les prérequis F02 (multi-tenant) + F03 (audit log).

- [ ] T001 Vérifier l'activation du venv backend (`source backend/venv/bin/activate`) et des dépendances installées (`pip install -r backend/requirements.txt`) ; vérifier `which python` pointe vers `backend/venv/bin/python`.
- [ ] T002 Vérifier que les migrations F02 (`019_multitenant_and_roles`) et F03 (`021_create_audit_log`) sont appliquées localement (`cd backend && alembic current` doit montrer la dernière migration). Si F02/F03 mergent dans main entre-temps, recaler `down_revision` de la migration F05 en T011.
- [ ] T003 Ajouter `itsdangerous>=2.1.0` à `backend/requirements.txt` si absent (vérifier avec `pip show itsdangerous`). Ajouter `aiosmtplib>=3.0.0` à `backend/requirements.txt` si absent (pour SMTP async).
- [ ] T004 Ajouter variables d'environnement dans `backend/app/core/config.py` : `EXPORT_URL_SIGNING_KEY: str` (Field requis), `SMTP_HOST: str | None` (default None), `SMTP_PORT: int = 587`, `SMTP_USER: str | None`, `SMTP_PASSWORD: str | None`, `EMAIL_FROM: str = "no-reply@esg-mefali.com"`, `PRIVACY_POLICY_VERSION: str = "v1.0"`, `ACCOUNT_DELETION_GRACE_PERIOD_DAYS: int = 30`. Documenter dans `.env.example`.
- [ ] T005 [P] Vérifier que les dépendances frontend sont à jour (`cd frontend && npm install`) et que Playwright est installé (`npx playwright install`).
- [ ] T006 [P] Vérifier l'existence du layout `frontend/app/layouts/public.vue` (créé éventuellement par feature antérieure). Si absent, sera créé en T070.

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Mise en place de la migration Alembic, des modèles, du helper `require_consent`, du URL signer et du mailer stub — prérequis bloquants pour toutes les user stories.

**⚠️ CRITICAL** : Aucune user story ne peut commencer avant la fin de cette phase.

### Tests Foundational (TDD — écrire AVANT implémentation, vérifier qu'ils ÉCHOUENT)

- [ ] T007 [P] Écrire test unitaire `backend/tests/unit/test_consent_model.py` : invariants table `consents` (un seul actif par couple, FK cascade vers accounts, FK SET NULL vers users, contrainte revoked_after_granted, enum type rejette valeurs invalides).
- [ ] T008 [P] Écrire test unitaire `backend/tests/unit/test_consent_helper.py` : `require_consent` (raise 403 quand absent, raise 403 quand revoked, no-op quand actif, message en français, metadata `consent_type` + `settings_url`). Couverture des 7 types.
- [ ] T009 [P] Écrire test unitaire `backend/tests/unit/test_url_signer.py` : `sign_export_url`/`verify_export_url` (sign + verify roundtrip, expiration, signature corrompue → InvalidSignature, expired → SignatureExpired).
- [ ] T010 [P] Écrire test unitaire `backend/tests/unit/test_mailer_stub.py` : `send_email` en mode stub (sans SMTP_HOST) → logge dans audit_log avec entity_type='email', action='sent_stub', metadata complète. En mode réel (mock aiosmtplib) → appel SMTP correctement formé.
- [ ] T011 [P] Écrire test migration `backend/tests/migrations/test_alembic_f05.py` : up/down/up sans erreur ; vérifie que la table `consents` est créée avec les bons champs/contraintes/index ; vérifie que les colonnes `accounts.deletion_scheduled_at`, `deleted_at`, `purge_in_progress` sont ajoutées ; vérifie que les enums `consent_type_enum` et `legal_basis_enum` sont créés.

### Implementation Foundational

- [ ] T012 Créer `backend/app/models/consent.py` selon `data-model.md` : `Consent` SQLAlchemy avec colonnes `id`, `account_id`, `user_id`, `consent_type`, `granted`, `granted_at`, `revoked_at`, `legal_basis`, `version`, `metadata_`, `created_at`, `updated_at` ; enums Python `CONSENT_TYPE_VALUES` et `LEGAL_BASIS_VALUES` ; check constraint + indexes partiels via `__table_args__`.
- [ ] T013 Étendre `backend/app/models/account.py` avec colonnes `deletion_scheduled_at: Mapped[datetime | None]`, `deleted_at: Mapped[datetime | None]`, `purge_in_progress: Mapped[bool]` (default False) ; ajouter relation `consents: Mapped[list[Consent]]` cascade='delete'.
- [ ] T014 Créer la migration Alembic `backend/alembic/versions/0XX_consents_and_account_deletion.py` (revision et down_revision à fixer en revue selon ordre merge) implémentant : (1) `op.execute("CREATE TYPE consent_type_enum AS ENUM (...)")` avec 7 valeurs ; (2) `op.execute("CREATE TYPE legal_basis_enum AS ENUM (...)")` avec 4 valeurs ; (3) `op.create_table('consents', ...)` ; (4) check constraint `chk_consents_revoked_after_granted` ; (5) `op.create_index('idx_consents_active', ..., postgresql_where=...)` ; (6) `op.create_index('uq_consents_one_active', unique=True, postgresql_where=...)` ; (7) trigger updated_at (réutilise fonction projet) ; (8) `op.add_column('accounts', ...)` × 3 ; (9) indexes partiels sur accounts ; downgrade symétrique inverse.
- [ ] T015 Créer `backend/app/core/url_signer.py` : `sign_export_url(account_id, expires_in_seconds) -> str`, `verify_export_url(token) -> dict` levant `SignatureExpired` ou `BadSignature`. Utilise `itsdangerous.URLSafeTimedSerializer(settings.EXPORT_URL_SIGNING_KEY)`.
- [ ] T016 Créer `backend/app/core/mailer.py` : `async send_email(to, subject, body_html, body_text=None)` ; si `settings.SMTP_HOST` non configuré → audit_log stub `entity_type='email', action='sent_stub'` + return success ; sinon envoi SMTP via `aiosmtplib.send` async + audit_log `action='sent'`.
- [ ] T017 Créer `backend/app/core/consent.py` : (1) `CONSENT_TYPE_LABELS: dict[str, str]` avec libellés français ; (2) async `require_consent(db, account_id, consent_type) -> None` levant `HTTPException(403, ...)` ; (3) factory `consent_dependency(consent_type) -> Callable` pour FastAPI Depends.
- [ ] T018 Faire passer les tests T007-T011 au vert ; mesurer couverture (`pytest tests/unit/test_consent_model.py tests/unit/test_consent_helper.py tests/unit/test_url_signer.py tests/unit/test_mailer_stub.py tests/migrations/test_alembic_f05.py --cov=app.models.consent --cov=app.core.consent --cov=app.core.url_signer --cov=app.core.mailer --cov-report=term-missing`) ≥ 80 %.
- [ ] T019 Vérifier la migration up/down/up : `cd backend && source venv/bin/activate && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` ; aucune perte de données ; aucune erreur Alembic ; les enums survivent au down ou sont propres.

**Checkpoint** : Foundation prête — les user stories peuvent maintenant être implémentées en parallèle.

---

## Phase 3 : User Story 1 — Inventaire et export complet de mes données (Priority: P1) 🎯 MVP

**Goal** : La PME peut accéder à `/mes-donnees`, voir l'inventaire complet de ses données stockées, et exporter le tout en JSON via un fichier ZIP exhaustif.

**Independent Test** : Créer un compte avec données complètes, ouvrir `/mes-donnees`, vérifier compteurs corrects, cliquer « Exporter », télécharger ZIP, valider structure (data.json + README + manifest documents).

### Tests pour User Story 1 (TDD)

- [ ] T020 [P] [US1] Écrire test unitaire `backend/tests/unit/test_inventory_service.py` : `get_inventory(db, account_id)` retourne `InventoryResponse` avec compteurs corrects pour 11 catégories ; isole strictement par account_id (créer 2 accounts, vérifier isolement).
- [ ] T021 [P] [US1] Écrire test unitaire `backend/tests/unit/test_exporter.py` : `build_export_zip(account_id, db)` → bytes ZIP contenant data.json (toutes tables account_id), README.md (texte fr structure), documents/manifest.json (liste fichiers signés). Schéma data.json validé.
- [ ] T022 [P] [US1] Écrire test d'intégration `backend/tests/integration/test_me_router.py::test_inventory_endpoint` : crée compte avec 1 projet + 2 documents + 1 conversation, `GET /api/me/data/inventory` avec JWT → 200 avec compteurs corrects.
- [ ] T023 [P] [US1] Écrire test d'intégration `test_me_router.py::test_export_sync_returns_zip` : compte small, `GET /api/me/data/export?format=json` → 200 application/zip avec structure correcte.
- [ ] T024 [P] [US1] Écrire test d'intégration `test_me_router.py::test_export_audit_log_logged` : après export sync, vérifie événement audit_log `data_exported`.
- [ ] T025 [P] [US1] Écrire test d'intégration `test_me_router.py::test_export_async_returns_202_for_large_account` : mock estimation > 100 MB, vérifie 202 + job_id.
- [ ] T026 [P] [US1] Écrire test d'intégration `test_me_router.py::test_export_isolation_by_account_id` : 2 accounts (A, B), connecté A → export ne contient QUE les données de A.
- [ ] T027 [P] [US1] Écrire test d'intégration `test_me_router.py::test_export_download_token_signed` : génère token via `sign_export_url`, `GET /api/me/data/export/download?token=xxx` → 200.
- [ ] T028 [P] [US1] Écrire test d'intégration `test_me_router.py::test_export_download_token_expired` : token > 7j (mock time), → 410.
- [ ] T029 [P] [US1] Écrire test unitaire frontend `frontend/tests/unit/useDataPrivacy.spec.ts` : `useInventory()` charge les compteurs ; `useExport()` gère sync vs async.
- [ ] T030 [P] [US1] Écrire test unitaire frontend `frontend/tests/unit/DataInventoryTable.spec.ts` : rend 11 lignes avec format correct, dark mode, accessible.

### Implementation pour User Story 1

- [ ] T031 [US1] Créer `backend/app/modules/me/__init__.py` (module vide) et `backend/app/modules/me/schemas.py` avec Pydantic schemas selon `data-model.md` (`InventoryCounts`, `InventoryLastModified`, `InventoryResponse`, `ExportSyncResponse`, `ExportAsyncResponse`, `RegisterRequest` étendu, `ScheduleDeletionRequest`, `ConsentItem`, etc.).
- [ ] T032 [US1] Créer `backend/app/modules/me/service.py::get_inventory(db, account_id) -> InventoryResponse` : 11 SELECT COUNT(*) parallélisés via `asyncio.gather` + 11 SELECT MAX(updated_at) parallélisés. Décoré du mixin `Auditable` (lecture, donc pas d'event mais respect du pattern).
- [ ] T033 [US1] Créer `backend/app/modules/me/exporter.py::build_export_zip(account_id, db) -> bytes` : fetch toutes les tables account_id, construit `data.json` avec schéma documenté, génère URLs signées 24h pour chaque document via `url_signer`, zip en mémoire avec `zipfile.ZipFile(BytesIO())`. Inclut README.md texte français.
- [ ] T034 [US1] Créer `backend/app/modules/me/exporter.py::estimate_export_size(account_id, db) -> int` : compte rapide pour décider sync vs async (< 100 MB → sync).
- [ ] T035 [US1] Créer `backend/app/modules/me/exporter.py::build_export_async(account_id, background_tasks)` : stocke ZIP sur disque `/uploads/exports/{account_id}/{timestamp}.zip`, génère lien signé 7j, envoie email via `mailer.send_email`, log audit_log `data_export_ready`.
- [ ] T036 [US1] Créer `backend/app/modules/me/router.py` avec endpoints `GET /inventory` et `GET /export?format=json` et `GET /export/download?token=...` selon contracts/me-data.md ; utilise `Depends(get_current_user)` + auth ; gère sync/async selon `estimate_export_size`.
- [ ] T037 [US1] Modifier `backend/app/main.py` (zone partagée — minimiser le diff) pour inclure `from app.modules.me.router import router as me_router; app.include_router(me_router, prefix="/api/me")`. Coordonner avec orchestrateur si autre feature touche `main.py`.
- [ ] T038 [US1] Créer `frontend/app/composables/useDataPrivacy.ts` exposant `useInventory()`, `useExport()`. Typed via `$fetch<InventoryResponse>('/api/me/data/inventory')`. Gestion sync (Blob download) vs async (toast notification).
- [ ] T039 [US1] Créer `frontend/app/components/DataInventoryTable.vue` (props `counts: InventoryCounts`, `lastModified: InventoryLastModified`) ; tableau responsive avec 11 lignes, dark mode complet, ARIA `role=table`.
- [ ] T040 [US1] Créer `frontend/app/components/DataExportButton.vue` (props `estimatedSizeMb?: number`, emit `export-started`, `export-ready`) ; spinner pendant requête, gère sync vs async, accessible.
- [ ] T041 [US1] Créer `frontend/app/pages/mes-donnees/inventaire.vue` consommant `useDataPrivacy().useInventory()` + composants T039/T040. Layout default, auth requise via middleware.
- [ ] T042 [US1] Faire passer les tests T020-T030 au vert ; mesurer couverture (`pytest tests/unit/test_inventory_service.py tests/unit/test_exporter.py tests/integration/test_me_router.py --cov=app.modules.me --cov-report=term-missing`) ≥ 80 % sur module me.

**Checkpoint** : User Story 1 fonctionnelle — l'inventaire et l'export sont opérationnels.

---

## Phase 4 : User Story 2 — Consentements granulaires révocables (Priority: P1)

**Goal** : La PME voit les 7 consentements sur `/mes-donnees → Consentements`, peut les activer/désactiver à tout moment ; les services dépendants invoquent `require_consent` et rejettent en 403 si manquant.

**Independent Test** : Activer/désactiver Mobile Money, vérifier état BDD + audit_log + effet sur endpoint stub `require_consent`.

### Tests pour User Story 2 (TDD)

- [ ] T043 [P] [US2] Écrire test d'intégration `backend/tests/integration/test_me_router.py::test_list_consents_returns_7_default` : nouveau compte → `GET /api/me/consents` retourne 7 entrées avec valeurs default documentées.
- [ ] T044 [P] [US2] Écrire test d'intégration `test_me_router.py::test_grant_consent_creates_active_row` : `POST /api/me/consents/mobile_money_analysis/grant` → row inséré avec `granted=true, revoked_at=NULL`.
- [ ] T045 [P] [US2] Écrire test d'intégration `test_me_router.py::test_grant_idempotent_when_already_granted` : 2 calls, vérifier 1 seule row active.
- [ ] T046 [P] [US2] Écrire test d'intégration `test_me_router.py::test_revoke_marks_revoked_at` : grant puis revoke → row `revoked_at` positionné.
- [ ] T047 [P] [US2] Écrire test d'intégration `test_me_router.py::test_consent_audit_log_logged` : grant et revoke → audit_log events `consent_granted`/`consent_revoked` insérés avec metadata correcte (ip, user_agent, version).
- [ ] T048 [P] [US2] Écrire test d'intégration `test_me_router.py::test_consent_invalid_type_returns_422`.
- [ ] T049 [P] [US2] Écrire test d'intégration `test_me_router.py::test_consents_isolated_by_account_id`.
- [ ] T050 [P] [US2] Écrire test unitaire frontend `frontend/tests/unit/ConsentToggle.spec.ts` : props rendues correctement, emit `@toggle` au clic, accessible (ARIA `role=switch`, `aria-checked`), dark mode.

### Implementation pour User Story 2

- [ ] T051 [US2] Étendre `backend/app/modules/me/service.py` avec `list_consents(db, account_id) -> list[ConsentItem]`, `grant_consent(db, account_id, user_id, consent_type, request_metadata) -> Consent`, `revoke_consent(db, account_id, consent_type) -> Consent`. Décorées `Auditable` (events `consent_granted`/`consent_revoked`).
- [ ] T052 [US2] Étendre `backend/app/modules/me/router.py` avec endpoints `GET /consents`, `POST /consents/{type}/grant`, `POST /consents/{type}/revoke` selon contracts/me-consents.md.
- [ ] T053 [US2] Créer `frontend/app/stores/consents.ts` Pinia avec state `consents: ConsentItem[]`, actions `fetchAll()`, `grant(type)`, `revoke(type)` ; gestion optimistic UI + rollback en erreur.
- [ ] T054 [US2] Créer `frontend/app/components/ConsentToggle.vue` (props `consent: ConsentItem`, emit `@toggle`) ; ARIA switch + dark mode + animation transition.
- [ ] T055 [US2] Créer `frontend/app/pages/mes-donnees/consentements.vue` consommant `useConsentsStore()`, rendu liste 7 ConsentToggle, layout default.
- [ ] T056 [US2] Faire passer les tests T043-T050 au vert ; couverture ≥ 80 % sur le subset consent.

**Checkpoint** : User Story 2 fonctionnelle — les consentements granulaires sont opérationnels.

---

## Phase 5 : User Story 3 — Suppression de compte avec délai de grâce 30 jours (Priority: P1)

**Goal** : La PME peut programmer la suppression (triple confirmation), annuler avant J+30, ou laisser le cron purger effectivement après J+30 (cascade + anonymisation audit_log).

**Independent Test** : Programmer suppression, vérifier email + `deletion_scheduled_at` en BDD, annuler, re-programmer, simuler J+30, exécuter cron, vérifier purge effective + audit_log anonymisé.

### Tests pour User Story 3 (TDD)

- [ ] T057 [P] [US3] Écrire test d'intégration `backend/tests/integration/test_me_router.py::test_verify_password_success` et `test_verify_password_failure` (401).
- [ ] T058 [P] [US3] Écrire test d'intégration `test_me_router.py::test_schedule_deletion_owner_only` : owner → 200, collaborator → 403.
- [ ] T059 [P] [US3] Écrire test d'intégration `test_me_router.py::test_schedule_deletion_invalid_password_returns_401` ; audit_log `account_deletion_attempt_failed` inséré.
- [ ] T060 [P] [US3] Écrire test d'intégration `test_me_router.py::test_schedule_deletion_invalid_confirmation_returns_422`.
- [ ] T061 [P] [US3] Écrire test d'intégration `test_me_router.py::test_schedule_deletion_already_scheduled_returns_409`.
- [ ] T062 [P] [US3] Écrire test d'intégration `test_me_router.py::test_cancel_deletion_via_jwt` (auth) et `test_cancel_deletion_via_token_signed` (no-auth).
- [ ] T063 [P] [US3] Écrire test unitaire `backend/tests/unit/test_purge_service.py::test_purge_cascades_all_account_data` : compte avec données → purge → toutes les tables account_id vides.
- [ ] T064 [P] [US3] Écrire test unitaire `test_purge_service.py::test_purge_anonymizes_audit_log` : audit_log post-purge → `user_id IS NULL AND account_id IS NULL`, `payload` filtré (PII whitelistées retirées, autres conservés).
- [ ] T065 [P] [US3] Écrire test unitaire `test_purge_service.py::test_purge_removes_uploads_directory` : crée fichiers fictifs sous `/uploads/{account_id}/`, purge → vérifier suppression.
- [ ] T066 [P] [US3] Écrire test unitaire `test_purge_service.py::test_purge_revokes_attestations_first` : attestation active pré-existante → purge → `status='revoked', reason='account_deleted'` AVANT cascade.
- [ ] T067 [P] [US3] Écrire test unitaire `test_purge_service.py::test_purge_revokes_refresh_tokens`.
- [ ] T068 [P] [US3] Écrire test d'intégration `backend/tests/integration/test_purge_cron.py::test_full_cron_flow` : programmer suppression → avancer date → exécuter `purge_scheduled_deletions.py` → vérifier purge effective + audit_log anonymisé + `accounts.deleted_at` positionné.
- [ ] T069 [P] [US3] Écrire test d'intégration `test_purge_cron.py::test_purge_idempotent_after_interruption` : démarrer purge, simuler exception, relancer, vérifier complétion finale.
- [ ] T070 [P] [US3] Écrire test unitaire frontend `frontend/tests/unit/DeletionConfirmModal.spec.ts` : 3 étapes incrémentales, focus trap, ARIA, validation par étape, emit `@confirm` qu'à validation finale.

### Implementation pour User Story 3

- [ ] T071 [US3] Étendre `backend/app/modules/me/service.py` avec `verify_password(db, user_id, password) -> bool`, `schedule_deletion(db, account_id, user_id, password, confirmation_text, request_metadata) -> ScheduleDeletionResponse`, `cancel_deletion(db, account_id, token=None) -> dict`. Décorées `Auditable` (events `account_deletion_scheduled`/`account_deletion_cancelled`/`password_verification_failed`).
- [ ] T072 [US3] Étendre `backend/app/modules/me/router.py` avec endpoints `POST /account/verify-password`, `POST /account/schedule-deletion`, `POST /account/cancel-deletion` selon contracts/me-account.md.
- [ ] T073 [US3] Créer `backend/app/modules/me/purge.py::purge_account_data(account_id, db) -> PurgeResult` avec étapes documentées dans contracts/me-account.md (lock idempotent, révocation attestation, fetch document_paths, anonymisation audit_log via UPDATE en place avec fonction Python `anonymize_payload`, suppression fichiers, suppression refresh tokens, mise à `deleted_at`, envoi email final, audit_log `account_purged` anonymisé).
- [ ] T074 [US3] Créer `backend/app/modules/me/purge.py::anonymize_payload(payload, pii_fields) -> dict` : retire récursivement les clés correspondant à la whitelist (`email`, `phone`, `ip`, `user_agent`, `name`, `address`, etc.), conserve les autres.
- [ ] T075 [US3] Créer `backend/scripts/purge_scheduled_deletions.py` : main entrypoint async, fetch comptes éligibles, appelle `purge_account_data` pour chacun, gestion exceptions (continuer sur les autres), logging structuré JSON.
- [ ] T076 [US3] Créer `frontend/app/components/DeletionConfirmModal.vue` : 3 étapes (consequences checkbox, password verify async, confirmation text "SUPPRIMER"), focus trap natif, ARIA `role=dialog`, dark mode, retour focus à élément déclencheur.
- [ ] T077 [US3] Créer `frontend/app/components/DeletionScheduledBanner.vue` : warning persistant avec date programmée + bouton « Annuler ».
- [ ] T078 [US3] Créer `frontend/app/pages/mes-donnees/supprimer.vue` : bouton « Supprimer mon compte » qui ouvre modal, gestion état déjà programmée → afficher banner + bouton Annuler.
- [ ] T079 [US3] Étendre `frontend/app/composables/useDataPrivacy.ts` avec `useDeletion()` exposant `verifyPassword`, `scheduleDeletion`, `cancelDeletion`.
- [ ] T080 [US3] Faire passer les tests T057-T070 au vert ; couverture ≥ 80 % sur purge + service + router.

**Checkpoint** : User Story 3 fonctionnelle — suppression programmée + annulation + cron purge.

---

## Phase 6 : User Story 4 — Politique de confidentialité publique et consentement à l'inscription (Priority: P2)

**Goal** : `/legal/privacy` accessible sans auth ; checkbox obligatoire à `/register` ; footer global avec lien.

**Independent Test** : Naviguer en privé sur `/legal/privacy`, vérifier 10 sections + chargement < 1s. Tenter inscription sans cocher → bloqué.

### Tests pour User Story 4 (TDD)

- [ ] T081 [P] [US4] Écrire test d'intégration `backend/tests/integration/test_register_privacy_flag.py::test_register_without_privacy_returns_422` : `POST /api/auth/register` sans `privacy_policy_accepted=true` → 422.
- [ ] T082 [P] [US4] Écrire test d'intégration `test_register_privacy_flag.py::test_register_audit_log_inserted` : avec privacy=true, → audit_log `privacy_policy_accepted` inséré avec metadata version+ip+user_agent.
- [ ] T083 [P] [US4] Écrire test d'intégration `test_register_privacy_flag.py::test_register_creates_essential_consents` : 3 essential consents auto-créés avec `granted=true` (profile_analysis, document_analysis_ai, credit_certificate_generation).
- [ ] T084 [P] [US4] Écrire test E2E (intégré dans `frontend/tests/e2e/F05-rgpd-mes-donnees-consents.spec.ts`) : checkbox bloque la soumission frontend (scénario 5 du fichier E2E, implémenté en Phase 10 / T104).

### Implementation pour User Story 4

- [ ] T085 [US4] Modifier `backend/app/routers/auth.py` (zone partagée — minimiser le diff) : étendre `RegisterRequest` Pydantic avec `privacy_policy_accepted: bool` (Field requis) + `privacy_policy_version: str = "v1.0"` ; valider que `privacy_policy_accepted=true` ; après création compte, insérer audit_log `privacy_policy_accepted` ; créer 3 essential consents auto.
- [ ] T086 [US4] Vérifier l'existence de `frontend/app/layouts/public.vue` ; si absent (T006), créer le layout : header simple ESG Mefali + slot main + footer global avec lien `/legal/privacy`. Dark mode.
- [ ] T087 [US4] Créer `frontend/app/pages/legal/privacy.vue` avec `definePageMeta({layout: 'public', auth: false})`. Contenu : 10 sections sémantiques (responsable / finalités / catégories / durée / sous-traitants / transferts / droits / exercice / coordonnées privacy@esg-mefali.com / date+versions). Dark mode.
- [ ] T088 [US4] Modifier `frontend/app/pages/register.vue` (zone partagée — minimiser le diff) : ajouter checkbox `<input type="checkbox" v-model="privacy_policy_accepted" required>` avec label cliquable vers `/legal/privacy` ; bouton submit `:disabled="!privacy_policy_accepted"`.
- [ ] T089 [US4] Modifier `frontend/app/layouts/default.vue` (zone partagée — minimiser le diff) : ajouter dans le footer global le lien `/legal/privacy`. Si footer composant déjà extrait (`<AppFooter />`), modifier ce composant.
- [ ] T090 [US4] Faire passer les tests T081-T084 au vert.

**Checkpoint** : User Story 4 fonctionnelle — politique publiée + checkbox obligatoire.

---

## Phase 7 : User Story 5 — Garde-fou applicatif `require_consent` intégré aux services sensibles (Priority: P2)

**Goal** : Le helper `require_consent` est disponible et un test CI scanner garantit sa présence dans les services sensibles présents et futurs.

**Independent Test** : Endpoint stub `/api/credit/mobile-money/preview` avec `Depends(consent_dependency('mobile_money_analysis'))` → 403 sans grant, 200 avec grant.

### Tests pour User Story 5 (TDD)

- [ ] T091 [P] [US5] Écrire test d'intégration `backend/tests/integration/test_consent_gating.py::test_endpoint_with_consent_dependency_blocks_without_grant` : endpoint stub décoré `Depends(consent_dependency('mobile_money_analysis'))` → 403 sans grant ; après grant → 200.
- [ ] T092 [P] [US5] Écrire test d'intégration `test_consent_gating.py::test_endpoint_blocks_after_revoke` : grant puis revoke → 403.
- [ ] T093 [P] [US5] Écrire test CI security `backend/tests/security/test_require_consent_coverage.py` : (1) walk les fichiers `backend/app/services/`, `backend/app/modules/*/service.py`, `backend/app/graph/tools/*_tools.py` ; (2) regex match fonctions `analyze_*|fetch_*_external|generate_certificate_*|process_*_sensitive` ; (3) pour chaque match, vérifier que le corps de fonction contient la string `require_consent(` OU est dans `EXCLUSIONS = {...}` documentée. Échec liste les fonctions non conformes.

### Implementation pour User Story 5

- [ ] T094 [US5] Créer un router stub `backend/app/routers/credit_stub.py` avec endpoint `POST /api/credit/mobile-money/preview` décoré `Depends(consent_dependency('mobile_money_analysis'))` retournant 501 `{"detail": "F18 not implemented yet, but consent gating works"}`. Cette stub permet aux tests T091/T092 de passer même sans F18 mergé.
- [ ] T095 [US5] Inclure le router stub dans `backend/app/main.py` (zone partagée — coordonné avec T037).
- [ ] T096 [US5] Documenter la `EXCLUSIONS` liste explicite dans `test_require_consent_coverage.py` (au moins une exclusion documentée pour servir d'exemple, ex. `"analyze_self_assessed_score"` si applicable).
- [ ] T097 [US5] Faire passer les tests T091-T093 au vert.

**Checkpoint** : User Story 5 fonctionnelle — helper `require_consent` opérationnel + scanner CI vert.

---

## Phase 8 : User Story 6 — Documentation hébergement et conformité (Priority: P3)

**Goal** : Documents internes `docs/rgpd-conformite.md` + `docs/hosting-and-data-residency.md` rédigés et complets.

**Independent Test** : Lire les 2 documents et vérifier qu'ils couvrent toutes les sections requises.

### Implementation pour User Story 6

- [ ] T098 [P] [US6] Créer `docs/rgpd-conformite.md` avec sections : (1) Cadre légal (RGPD + loi ivoirienne 2013-450 + UEMOA n°20/2010/CM/UEMOA), (2) Checklist de conformité (≥ 15 items couvrant : politique publiée, registre traitements, DPO, consentements granulaires, exercice des droits, durées de conservation, sous-traitants, sécurité, anonymisation purge, etc.), (3) Processus d'exercice des droits (Art. 15/17/20), (4) Contacts (privacy@esg-mefali.com, DPO post-MVP), (5) Gabarits de réponse aux demandes RGPD, (6) Historique versions à la fin.
- [ ] T099 [P] [US6] Créer `docs/hosting-and-data-residency.md` avec sections : (1) Provider (à compléter selon décision infra : OVH / Scaleway / Africa Data Centres), (2) Région (Europe ou Afrique Ouest, **pas USA**), (3) Chiffrement at-rest (AES-256 par défaut du provider), (4) Backup encrypté + rétention, (5) Sous-traitants (OpenRouter, exchangerate-api, hébergeur) avec DPA si applicable, (6) Variables d'environnement requises (SMTP_*, EXPORT_URL_SIGNING_KEY, etc.), (7) Historique versions à la fin.

**Checkpoint** : User Story 6 fonctionnelle — documentation rédigée.

---

## Phase 9 : Page principale `/mes-donnees/index.vue` + intégration globale

**Purpose** : Assembler la page tableau de bord et garantir l'intégration cohérente.

- [ ] T100 Créer `frontend/app/pages/mes-donnees/index.vue` : layout default, 4 cartes (Inventaire / Export / Consentements / Suppression) chacune linkée vers la sous-page correspondante, bandeau `<DeletionScheduledBanner>` en haut si applicable. Dark mode.
- [ ] T101 Vérifier la cohérence du middleware auth global sur `/mes-donnees/*` (auth requise) et l'absence de middleware auth sur `/legal/*` (no-auth).
- [ ] T102 Mettre à jour `frontend/app/composables/useDataPrivacy.ts` pour exposer un seul composable cohérent (vérification API surface).
- [ ] T103 Vérifier le rendu dark mode complet sur les 5 nouveaux composants Vue + les 5 pages (inventaire, consentements, supprimer, index mes-donnees, legal/privacy) + le layout public via screenshot diff.

---

## Phase 10 : Tests E2E Playwright

**Purpose** : Valider les 4 scénarios critiques bout en bout (cf. spec critères d'acceptation).

- [ ] T104 Créer `frontend/tests/e2e/F05-rgpd-mes-donnees-consents.spec.ts` avec 4+1 scénarios :

```typescript
import { test, expect } from '@playwright/test';

test.describe('F05 — RGPD Mes Données + Consentements + Export/Suppression', () => {

  test('Scénario 1 : créer compte → exporter → JSON valide non vide', async ({ page, request }) => {
    // 1. Inscription avec privacy_policy_accepted=true
    await page.goto('/register');
    await page.fill('input[name="email"]', `e2e-${Date.now()}@example.com`);
    await page.fill('input[name="password"]', 'TestPwd123!');
    await page.fill('input[name="company_name"]', 'PME E2E');
    await page.check('input[name="privacy_policy_accepted"]');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    // 2. Aller sur /mes-donnees → inventaire
    await page.goto('/mes-donnees/inventaire');
    await expect(page.getByText('Inventaire de mes données')).toBeVisible();

    // 3. Cliquer Exporter → download du ZIP
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('button:has-text("Exporter mes données en JSON")'),
    ]);
    const path = await download.path();
    expect(path).toBeTruthy();

    // 4. Validation : décompresser et vérifier data.json non vide
    // (utiliser node:zlib ou yauzl ; assertion : data.account.id non vide)
  });

  test('Scénario 2 : programmer suppression → annuler → compte intact', async ({ page }) => {
    // 1. Inscription + login
    // ...

    // 2. Aller sur /mes-donnees/supprimer
    await page.goto('/mes-donnees/supprimer');

    // 3. Clic bouton Supprimer → modale 3 étapes
    await page.click('button:has-text("Supprimer mon compte")');
    await page.check('input[name="acknowledge_consequences"]');
    await page.fill('input[name="password"]', 'TestPwd123!');
    await page.fill('input[name="confirmation_text"]', 'SUPPRIMER');
    await page.click('button:has-text("Confirmer la suppression")');
    await expect(page.getByText('Suppression programmée')).toBeVisible();

    // 4. Cliquer Annuler la suppression
    await page.click('button:has-text("Annuler la suppression")');
    await expect(page.getByText('Suppression annulée')).toBeVisible();

    // 5. Vérifier que le compte reste fonctionnel : retour sur /mes-donnees → pas de bandeau
    await page.goto('/mes-donnees');
    await expect(page.getByText('Suppression programmée')).not.toBeVisible();
  });

  test('Scénario 3 : programmer suppression → simuler J+30 → purge effective + audit_log anonymisé', async ({ page, request }) => {
    // 1. Inscription + login + programmer suppression (idem scénario 2)
    // ...

    // 2. Avancer la date via API admin/test (route protégée test_only)
    const accountId = await getAccountIdFromJwt(page);
    await request.post(`/api/test/accounts/${accountId}/force-deletion-due`, { /* ... */ });

    // 3. Déclencher cron via API admin (ou run script in-process)
    await request.post('/api/test/cron/purge-scheduled-deletions');

    // 4. Vérifier purge : tentative de fetch /api/me/data/inventory → 401 (token révoqué)
    const inventoryRes = await request.get('/api/me/data/inventory');
    expect(inventoryRes.status()).toBe(401);

    // 5. Vérifier audit_log anonymisé via API admin
    const auditRes = await request.get(`/api/admin/audit-log?account_id=${accountId}`);
    const auditEvents = await auditRes.json();
    expect(auditEvents).toHaveLength(0);  // pas de row avec account_id
    const anonymizedRes = await request.get(`/api/admin/audit-log?entity_id=${accountId}&user_id_is_null=true`);
    expect((await anonymizedRes.json()).length).toBeGreaterThan(0);  // rows anonymisés conservés
  });

  test('Scénario 4 : tenter analyse Mobile Money sans consent → 403', async ({ page, request }) => {
    // 1. Inscription + login
    // ...

    // 2. Vérifier consent default = false pour mobile_money_analysis
    const consentsRes = await request.get('/api/me/consents');
    const mm = (await consentsRes.json()).find((c: any) => c.type === 'mobile_money_analysis');
    expect(mm.granted).toBe(false);

    // 3. Tenter endpoint stub
    const previewRes = await request.post('/api/credit/mobile-money/preview');
    expect(previewRes.status()).toBe(403);
    const detail = await previewRes.json();
    expect(detail.detail.consent_type).toBe('mobile_money_analysis');

    // 4. Grant consent
    await request.post('/api/me/consents/mobile_money_analysis/grant');

    // 5. Retenter → 200 ou 501 (stub) — pas 403
    const previewRes2 = await request.post('/api/credit/mobile-money/preview');
    expect(previewRes2.status()).not.toBe(403);

    // 6. Revoke
    await request.post('/api/me/consents/mobile_money_analysis/revoke');

    // 7. Retenter → 403
    const previewRes3 = await request.post('/api/credit/mobile-money/preview');
    expect(previewRes3.status()).toBe(403);
  });

  test('Scénario 5 (US4) : page /legal/privacy accessible sans auth + checkbox obligatoire à /register', async ({ page }) => {
    // 1. Naviguer en mode déconnecté sur /legal/privacy
    await page.goto('/legal/privacy');
    await expect(page).toHaveURL(/.*\/legal\/privacy/);  // pas de redirect login
    await expect(page.getByText('Politique de confidentialité')).toBeVisible();
    await expect(page.getByText('privacy@esg-mefali.com')).toBeVisible();

    // 2. Footer contient le lien
    await expect(page.locator('footer >> text=Politique de confidentialité')).toBeVisible();

    // 3. Sur /register, sans cocher la case → soumission bloquée
    await page.goto('/register');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'TestPwd123!');
    await page.fill('input[name="company_name"]', 'Test PME');
    // NE PAS cocher la case
    const submitButton = page.locator('button[type="submit"]');
    await expect(submitButton).toBeDisabled();
  });
});
```

- [ ] T105 Implémenter les routes de test `/api/test/*` dans `backend/app/routers/test_only.py` (uniquement actives en `ENV=test` ou `DEBUG=true`) pour permettre aux E2E de manipuler les dates et déclencher le cron : `POST /api/test/accounts/{id}/force-deletion-due`, `POST /api/test/cron/purge-scheduled-deletions`. Documenter clairement ces routes comme « test only, jamais en prod ».
- [ ] T106 Vérifier que les E2E passent localement avec backend + frontend démarrés : `npx playwright test tests/e2e/F05-rgpd-mes-donnees-consents.spec.ts --reporter=html`.

**Checkpoint** : Tests E2E verts sur les 5 scénarios.

---

## Phase 11 : Polish & validation finale

**Purpose** : Garantir l'absence de régression et la qualité finale avant PR.

- [ ] T107 Lancer la suite de tests complète : `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app --cov-report=term-missing`. Vérifier couverture globale ≥ 80 %.
- [ ] T108 Lancer la suite frontend : `cd frontend && npm run test -- --coverage`. Vérifier couverture composants F05 ≥ 80 %.
- [ ] T109 Vérifier qu'aucun secret n'est hardcodé : `grep -rE '(api_key|secret|password|token|signing_key)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/ specs/` ne retourne que des fixtures de test ou clés env-référencées.
- [ ] T110 Lancer `python -m py_compile $(find backend/app -name '*.py')` pour vérifier zéro erreur de syntaxe.
- [ ] T111 Lancer `cd frontend && npx nuxt typecheck` (ou `npm run build`) pour valider le typage TypeScript.
- [ ] T112 Mettre à jour `CLAUDE.md` via `.specify/scripts/bash/update-agent-context.sh claude` pour ajouter F05 à `Active Technologies` et `Recent Changes`.
- [ ] T113 Visual diff dark mode : capturer screenshots des 5 nouveaux composants + 5 pages en light et dark mode, vérifier que tous les fonds/textes/bordures sont correctement adaptés.
- [ ] T114 Audit accessibilité automatique sur `/mes-donnees`, `/mes-donnees/consentements`, `/mes-donnees/supprimer`, `/legal/privacy` via Playwright `axe-core` snapshot ou équivalent. Aucune violation niveau A/AA.
- [ ] T115 Vérifier le commit message respecte Conventional Commits : `feat(F05): RGPD Mes Données + Consentements + Export/Suppression`.

---

## Stratégie de parallélisation

Les tâches marquées `[P]` peuvent s'exécuter en parallèle car elles touchent des fichiers différents sans dépendance bloquante. Les tâches avec [Story] sont rattachées à une user story et peuvent être lancées en parallèle entre stories après la fin de Phase 2 (Foundational).

**Vagues recommandées** :

- **Vague 1 (Setup)** : T001-T006 séquentiel ou rapide.
- **Vague 2 (Foundational tests)** : T007-T011 en parallèle.
- **Vague 3 (Foundational impl)** : T012-T017 séquentiel (mêmes fichiers / même migration).
- **Vague 4 (Foundational checks)** : T018-T019 séquentiel.
- **Vague 5 (US1+US2+US3 tests en parallèle)** : T020-T030, T043-T050, T057-T070 en parallèle entre stories.
- **Vague 6 (US1+US2+US3 impl)** : T031-T042, T051-T056, T071-T080 séquentiels par story mais parallèles entre stories.
- **Vague 7 (US4+US5)** : T081-T097 mostly parallel.
- **Vague 8 (Doc + page index + E2E + Polish)** : T098-T115 mix séquentiel/parallèle.

## Critères d'acceptation finaux (rappel spec)

- ✅ Page `/mes-donnees` fonctionnelle (inventaire + export + consentements + suppression)
- ✅ Endpoint `GET /api/me/data/export?format=json` génère ZIP complet incluant toutes tables `account_id` + URLs signées
- ✅ Modèle `Consent` créé avec 7 types initiaux
- ✅ Helper `require_consent` intégré dans services dépendants (au minimum stub pour F18)
- ✅ Politique privacy publiée à `/legal/privacy`, accessible sans auth
- ✅ Email `privacy@esg-mefali.com` documenté
- ✅ Inscription : checkbox obligatoire (refus = pas d'inscription)
- ✅ Suppression compte : J+30 grâce, email confirmation, cron purge effectif
- ✅ Test E2E : créer compte → exporter → JSON valide non vide
- ✅ Test E2E : programmer suppression → annuler → compte intact
- ✅ Test E2E : programmer suppression → simuler J+30 → purge effective + audit log anonymisé
- ✅ Test consent gating : tenter Mobile Money sans consent → 403
- ✅ Couverture tests ≥ 80 %
- ✅ Documentation `docs/rgpd-conformite.md` + `docs/hosting-and-data-residency.md`
