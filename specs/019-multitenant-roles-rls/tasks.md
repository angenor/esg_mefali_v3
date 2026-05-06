---
description: "Task list for F02 Multi-tenant + Roles + Row-Level Security"
---

# Tasks: F02 — Multi-tenant + Rôle Admin + Row-Level Security

**Input** : Design documents from `/Users/mac/Documents/projets/2025/esg_mefali_v3/specs/019-multitenant-roles-rls/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests** : OBLIGATOIRES — TDD strict (tests AVANT implémentation), couverture ≥ 80 %.

**Organization** : Tasks groupées par user story pour activation/test indépendants. Conventions :

- **[P]** : tâche parallélisable (fichier différent, pas de dépendance bloquante).
- **[USx]** : rattachement à une user story (US1 isolation, US2 admin, US3 invitations, US4 refresh rotation).
- Chaque path est ABSOLU. Backend root : `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/`. Frontend root : `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/`.

## Path Conventions

- Backend : `backend/app/...`, `backend/tests/...`, `backend/alembic/versions/...`
- Frontend : `frontend/app/...`, `frontend/tests/unit/...`, `frontend/tests/e2e/...`
- Docs : `docs/...`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparation des constantes, types, schémas Pydantic communs avant toute implémentation. Aucune logique métier ici.

- [ ] T001 [P] Créer `backend/app/core/constants.py` avec les enums Python `UserRole` (`PME`, `ADMIN`) et `InvitationStatus` (`pending`, `accepted`, `expired`, `revoked`), et les constantes `INVITE_TOKEN_TTL_DAYS_DEFAULT = 7`, `REFRESH_TOKEN_GRACE_WINDOW_SECONDS = 5`, `REFRESH_TOKEN_EXPIRE_DAYS = 30`.
- [ ] T002 [P] Étendre `backend/app/core/config.py` (zone interdite — sérialiser avec orchestrateur) : changer `access_token_expire_minutes: int = 480` en `1440`, ajouter `invite_token_ttl_days: int = 7` et `refresh_token_grace_window_seconds: int = 5`.
- [ ] T003 [P] Créer `backend/app/schemas/account.py` avec les Pydantic v2 : `AccountSummary` (id, name, is_active, plan), `InvitationCreate` (email: EmailStr), `InvitationResponse` (id, email, status, expires_at, invited_by, created_at), `AccountUsersResponse` (members: list, pending_invitations: list), `AccountMemberSummary` (id, email, full_name, role, is_active, joined_at).
- [ ] T004 [P] Étendre `backend/app/schemas/auth.py` avec : `LogoutRequest` (no body), `RegisterRequest.invite_token: str | None = None`, `UserResponse.role: UserRole`, `UserResponse.account: AccountSummary | None`.
- [ ] T005 [P] Créer `backend/app/schemas/admin.py` (squelette) : `AdminHealthResponse` (status: str, role: str, service: str).
- [ ] T006 [P] Créer types TypeScript `frontend/app/types/auth.ts` (ou étendre l'existant) avec `type Role = 'PME' | 'ADMIN'`, `interface AccountSummary { id: string; name: string; is_active: boolean; plan: 'free' | 'pro' }`, `interface AccountMember { id: string; email: string; full_name: string; role: Role; is_active: boolean; joined_at: string }`, `interface AccountInvitation { id: string; email: string; status: 'pending' | 'accepted' | 'expired' | 'revoked'; expires_at: string; invited_by: { id: string; full_name: string }; created_at: string }`.

**Checkpoint Phase 1** : constantes, configs et schémas définis. Aucune logique métier touchée.

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Modèles SQLAlchemy + migration Alembic 019 + helpers RLS/Email. **Aucune user story ne peut démarrer avant la fin de cette phase.**

**TDD strict** : pour chaque modèle/helper, écrire les tests AVANT le code.

### Tests fondations (TDD red)

- [ ] T007 [P] Créer `backend/tests/unit/test_models_account.py` avec tests : (a) création d'un `Account`, (b) défaut `is_active = True`, (c) défaut `plan = 'free'`, (d) `created_at` auto-rempli, (e) `name` requis.
- [ ] T008 [P] Créer `backend/tests/unit/test_models_refresh_token.py` avec tests : (a) création, (b) `jti` UNIQUE, (c) `revoked_at` NULL par défaut, (d) `replaced_by_jti` NULL par défaut, (e) FK `user_id` ON DELETE CASCADE.
- [ ] T009 [P] Créer `backend/tests/unit/test_models_account_invitation.py` avec tests : (a) création, (b) statut défaut `pending`, (c) `expires_at` requis, (d) FK `account_id` et `invited_by_user_id`, (e) `token_hash` requis.
- [ ] T010 [P] Créer `backend/tests/unit/test_models_user_role_constraint.py` avec tests : (a) PME avec account_id NOT NULL OK, (b) ADMIN avec account_id NULL OK, (c) PME sans account_id → IntegrityError, (d) ADMIN avec account_id → IntegrityError.
- [ ] T011 [P] Créer `backend/tests/unit/test_email_delivery.py` avec tests pour `LoggingEmailDelivery` : (a) `send()` log INFO avec to/subject/body, (b) interface respectée (`Protocol EmailDeliveryService`), (c) helpers `format_invitation_email(invitation, base_url)`.
- [ ] T012 [P] Créer `backend/tests/unit/test_rls_session_helper.py` avec tests pour `set_rls_context(session, account_id, role)` : (a) SET LOCAL des deux variables, (b) acceptance d'un `account_id` None (Admin), (c) appel SQL `current_setting('app.current_account_id', true)` retourne la bonne valeur après set.
- [ ] T013 [P] Créer `backend/tests/integration/test_alembic_019_upgrade_downgrade.py` avec tests : (a) `alembic upgrade head` applique 019, (b) tables `accounts`, `refresh_tokens`, `account_invitations` créées, (c) `users` a colonnes `role` et `account_id`, (d) RLS active sur 14 tables (`SELECT relrowsecurity FROM pg_class WHERE relname = ...` retourne `t`), (e) `alembic downgrade -1` supprime tout proprement, (f) `alembic upgrade head` re-applique sans erreur.

### Implémentation fondations

- [ ] T014 [P] Créer `backend/app/models/account.py` (modèle `Account` avec `name`, `is_active`, `plan`, timestamps). Doit faire passer T007.
- [ ] T015 [P] Créer `backend/app/models/refresh_token.py` (modèle `RefreshToken` avec `jti`, `user_id`, `issued_at`, `expires_at`, `revoked_at`, `replaced_by_jti`). Doit faire passer T008.
- [ ] T016 [P] Créer `backend/app/models/account_invitation.py` (modèle `AccountInvitation` avec `account_id`, `email`, `token_hash`, `token_lookup`, `invited_by_user_id`, `status`, `expires_at`, `accepted_at`, `accepted_by_user_id`). Doit faire passer T009.
- [ ] T017 Modifier `backend/app/models/user.py` : ajouter `role: Mapped[UserRole]` (défaut PME), `account_id: Mapped[uuid.UUID | None]` (FK accounts), CheckConstraint `users_role_account_consistency`. Doit faire passer T010.
- [ ] T018 [P] Modifier `backend/app/models/company.py` : ajouter `account_id: Mapped[uuid.UUID]` FK + UNIQUE INDEX partiel `WHERE archived = FALSE`, ajouter `archived: Mapped[bool] = False`.
- [ ] T019 [P] Modifier `backend/app/models/document.py` : ajouter `account_id` FK + index.
- [ ] T020 [P] Modifier `backend/app/models/esg.py` : ajouter `account_id` FK + index sur `esg_assessments`.
- [ ] T021 [P] Modifier `backend/app/models/carbon.py` : ajouter `account_id` FK + index sur `carbon_assessments`.
- [ ] T022 [P] Modifier `backend/app/models/credit.py` : ajouter `account_id` FK + index sur `credit_scores`.
- [ ] T023 [P] Modifier `backend/app/models/financing.py` : ajouter `account_id` FK + index sur `fund_matches`.
- [ ] T024 [P] Modifier `backend/app/models/application.py` : ajouter `account_id` FK + index sur `fund_applications`.
- [ ] T025 [P] Modifier `backend/app/models/action_plan.py` : ajouter `account_id` FK + index sur `action_plans`, `action_items`, `reminders`.
- [ ] T026 [P] Modifier `backend/app/models/conversation.py` : ajouter `account_id` FK + index.
- [ ] T027 [P] Modifier `backend/app/models/message.py` : ajouter `account_id` FK + index.
- [ ] T028 [P] Modifier `backend/app/models/interactive_question.py` : ajouter `account_id` FK + index.
- [ ] T029 [P] Modifier `backend/app/models/tool_call_log.py` : ajouter `account_id` FK + index.
- [ ] T030 [P] Modifier `backend/app/models/report.py` : ajouter `account_id` FK + index.
- [ ] T031 Créer migration `backend/alembic/versions/019_multitenant_and_roles.py` : (a) CREATE TYPE user_role + invitation_status, (b) CREATE TABLE accounts, refresh_tokens, account_invitations, (c) ALTER TABLE users ADD COLUMN role, account_id (nullable temp), (d) backfill (1 Account/company_name distinct + Account 'default' pour anomalies), (e) ALTER COLUMN account_id NOT NULL + CHECK constraint, (f) pour 14 tables métier : ADD COLUMN account_id NULL → backfill via users → ALTER NOT NULL → CREATE INDEX → CREATE FK, (g) pour company_profiles : ADD COLUMN archived + déduplication → UNIQUE INDEX partiel, (h) ENABLE + FORCE ROW LEVEL SECURITY + 2 policies (pme_access_own_account, admin_full_access) sur 14 tables + users (avec clause `app.current_user_id` pour Admin self-access). Downgrade complet en ordre inverse. Doit faire passer T013.
- [ ] T032 Créer `backend/app/core/rls_session.py` : helper `async def set_rls_context(session, account_id, role, user_id)` qui exécute `SET LOCAL app.current_account_id`, `SET LOCAL app.current_role`, `SET LOCAL app.current_user_id`. Doit faire passer T012.
- [ ] T033 Créer `backend/app/core/email_delivery.py` : Protocol `EmailDeliveryService` + classe `LoggingEmailDelivery` + helpers `format_invitation_subject(account_name)` et `format_invitation_body(invitation, invitation_url)`. Doit faire passer T011.

**Checkpoint Phase 2** : modèles, migration et helpers prêts. Tous les tests fondations passent. Les user stories peuvent démarrer.

---

## Phase 3 : User Story 1 — Isolation stricte multi-tenant (Priority: P1) 🎯 MVP

**Goal** : Garantir qu'un utilisateur d'une PME A ne peut JAMAIS voir les données d'une PME B, même en cas de bug applicatif. Implémenté via RLS PostgreSQL + helper `set_rls_context` câblé dans `get_current_user`.

**Independent Test** : créer 2 PME, créer pour chacune des conversations/documents/applications, puis vérifier via API et via SQL direct que A ne voit pas B et inversement. Test fail-closed quand `app.current_account_id` n'est pas SET.

### Tests US1 (TDD red)

- [ ] T034 [P] [US1] Créer `backend/tests/integration/test_rls_isolation.py` avec scénarios : (a) 2 accounts/2 users PME, conversations distinctes, user A list_conversations() ne voit pas celles de B, (b) UPDATE direct sans WHERE → ne touche que A, (c) SELECT direct sans WHERE → ne retourne que A, (d) sans set_rls_context préalable → 0 ligne (fail-closed), (e) Admin set_rls_context(role='ADMIN', account_id=None) → voit toutes les conversations.
- [ ] T035 [P] [US1] Créer `backend/tests/integration/test_rls_metier_tables.py` qui boucle sur les 14 tables métier et vérifie pour chaque table : RLS activée, FORCE RLS activée, 2 policies (pme/admin) présentes, `account_id NOT NULL` avec FK vers `accounts`. Utilise `pg_class` et `pg_policies`.

### Implémentation US1

- [ ] T036 [US1] Modifier `backend/app/api/deps.py` : étendre `get_current_user` pour appeler `await set_rls_context(db, current_user.account_id, current_user.role, current_user.id)` AVANT le return. Lever 403 explicite si `accounts.is_active = false` pour le compte du user. Doit faire passer T034 (a-d).
- [ ] T037 [US1] Créer `backend/app/api/deps.py::get_current_admin` : dépendance qui wrap `get_current_user` et lève 403 si `current_user.role != UserRole.ADMIN`. Inclure dans les imports publics.
- [ ] T038 [US1] Vérifier que tous les routers existants utilisent `Depends(get_current_user)` et bénéficient automatiquement du RLS. Aucune modification fonctionnelle des services métier (FR-011 — l'isolation est garantie par la DB seule). Test : T034 (e) admin full access.

**Checkpoint US1** : isolation stricte fonctionnelle, tests RLS verts. MVP de F02 livrable indépendamment.

---

## Phase 4 : User Story 2 — Accès Admin protégé (Priority: P1)

**Goal** : Routeur `/api/admin/*` réservé aux Admin (403 sinon). Suppression de la whitelist email anti-pattern. Frontend : middleware admin + layout dédié.

**Independent Test** : créer un Admin via seed, accéder à `/api/admin/health` → 200 ; créer un PME, accéder → 403. Côté frontend, middleware redirige PME vers `/dashboard`.

### Tests US2 (TDD red)

- [ ] T039 [P] [US2] Créer `backend/tests/integration/test_admin_route_protection.py` : (a) Admin → GET /api/admin/health 200, (b) PME → 403, (c) sans token → 401, (d) Admin désactivé → 403.
- [ ] T040 [P] [US2] Créer `backend/tests/integration/test_financing_admin_protection.py` : (a) PME → POST /api/financing/funds 403, (b) Admin → 201 (whitelist supprimée), (c) `grep "admin@esg-mefali.com" backend/app/modules/financing/router.py` retourne 0 ligne.
- [ ] T041 [P] [US2] Créer `backend/tests/unit/test_get_current_admin.py` : (a) user PME → 403, (b) user ADMIN → return user, (c) user inactive → 401.
- [ ] T042 [P] [US2] Créer `frontend/tests/unit/middleware-admin.spec.ts` : (a) user PME → navigateTo('/dashboard'), (b) user ADMIN → next(), (c) user null → navigateTo('/login').
- [ ] T043 [P] [US2] Créer `frontend/tests/unit/RoleBadge.spec.ts` : (a) role='ADMIN' → badge rouge, (b) role='PME' → badge bleu/vert, (c) dark mode classes appliquées.

### Implémentation US2

- [ ] T044 [P] [US2] Créer `backend/app/modules/admin/__init__.py` (vide) et `backend/app/modules/admin/router.py` avec `router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_admin)])` et `GET /admin/health` qui retourne `AdminHealthResponse`. Doit faire passer T039.
- [ ] T045 [US2] Modifier `backend/app/modules/financing/router.py` : supprimer la whitelist `admin_emails` (lignes ~118-120), remplacer par `current_admin: User = Depends(get_current_admin)` dans `create_fund_endpoint`. Doit faire passer T040.
- [ ] T046 ⚠️ ZONE INTERDITE [US2] Modifier `backend/app/main.py` (sérialiser via orchestrateur) : importer `app.modules.admin.router as admin_router` et `app.include_router(admin_router.router, prefix="/api")`. Si conflit avec une autre feature → signaler `zone_conflict`.
- [ ] T047 [P] [US2] Créer `frontend/app/middleware/admin.ts` (non global) : utilise `useAuth().isAdmin` et redirige vers `/dashboard` si non admin. Doit faire passer T042.
- [ ] T048 [P] [US2] Créer `frontend/app/components/ui/RoleBadge.vue` : prop `role: Role`, classes Tailwind différenciées (`bg-red-700 text-white dark:bg-red-900` pour ADMIN, `bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200` pour PME). Doit faire passer T043.
- [ ] T049 [P] [US2] Créer `frontend/app/layouts/admin.vue` : sidebar admin avec entrées (Catalogue, Sources, Comptes PME, Métriques) — entrées factices F02, peuplées par F09 — header avec `<RoleBadge role="ADMIN" />` persistant et accent rouge (`bg-red-50 dark:bg-red-950`, `border-red-200 dark:border-red-800`). Mode sombre complet. Slot principal pour le contenu de la page.
- [ ] T050 [P] [US2] Créer `frontend/app/pages/admin/health.vue` avec `definePageMeta({ middleware: 'admin', layout: 'admin' })`. Affiche un état health-check récupéré via `$fetch('/api/admin/health')`. Mode sombre.
- [ ] T051 [US2] Modifier `frontend/app/composables/useAuth.ts` : ajouter `isAdmin: ComputedRef<boolean>` calculé sur le `role` du user du store auth.
- [ ] T052 [US2] Modifier `frontend/app/stores/auth.ts` : ajouter au state `account: AccountSummary | null` et `role: Role | null`. Mettre à jour le hydrate après `/auth/me`.

**Checkpoint US2** : back-office Admin protégé fonctionnel, whitelist supprimée, frontend admin différencié visuellement. Test E2E US2 (Phase 8) peut être préparé.

---

## Phase 5 : User Story 3 — Multi-utilisateurs PME (invitations) (Priority: P2)

**Goal** : Permettre à un utilisateur PME d'inviter un collaborateur, livrer le lien d'invitation via `LoggingEmailDelivery`, finaliser l'inscription et partager toutes les données de l'`Account`.

**Independent Test** : Alice (PME A) invite Carole, Carole reçoit le lien (loggé), s'inscrit via `/register?invite=<token>`, voit les conversations d'Alice. Alice retire Carole, Carole perd l'accès.

### Tests US3 (TDD red)

- [ ] T053 [P] [US3] Créer `backend/tests/unit/test_account_tokens.py` : (a) `generate_invite_token()` retourne 32+ chars URL-safe, (b) `hash_invite_token(token)` produit un bcrypt distinct à chaque appel, (c) `verify_invite_token(token, hash)` valide correctement, (d) `compute_token_lookup(token)` est déterministe (SHA256 hex).
- [ ] T054 [P] [US3] Créer `backend/tests/integration/test_account_invitation_flow.py` : (a) POST /api/account/invite → 201 + invitation pending + LoggingEmailDelivery appelé, (b) GET /api/account/users → liste membres + invitations pending, (c) flow complet invite → register avec invite_token → user créé avec account_id correct, (d) DELETE /api/account/users/{user_id} → soft delete + révocation refresh tokens, (e) DELETE invitation pending → status revoked, (f) edge case last user → 409.
- [ ] T055 [P] [US3] Créer `backend/tests/integration/test_invitation_edge_cases.py` : (a) invitation expirée (> 7 j) → 400 sur register, (b) invitation déjà acceptée → 400, (c) invitation revoked → 400, (d) double invitation pending même email/account → 409 sur POST invite.
- [ ] T056 [P] [US3] Créer `frontend/tests/unit/useAccountTeam.spec.ts` : (a) `inviteMember(email)` POST /api/account/invite, (b) `listTeam()` GET /api/account/users, (c) `removeMember(id)` DELETE /api/account/users/{id}, (d) états loading/error gérés.

### Implémentation US3

- [ ] T057 [P] [US3] Créer `backend/app/modules/account/__init__.py` (vide) et `backend/app/modules/account/tokens.py` avec `generate_invite_token() -> str`, `hash_invite_token(token) -> str` (bcrypt via passlib), `verify_invite_token(token, hash) -> bool`, `compute_token_lookup(token) -> str` (sha256 hex pour lookup rapide). Doit faire passer T053.
- [ ] T058 [P] [US3] Créer `backend/app/modules/account/service.py` avec : `create_invitation(db, account_id, email, invited_by_user)`, `accept_invitation(db, token, new_user)`, `list_account_users(db, account_id)`, `remove_account_user(db, account_id, target_id)` (gère soft delete + révocation refresh tokens + détection dernier membre actif), `revoke_invitation(db, account_id, invitation_id)`. Doit faire passer T054 et T055.
- [ ] T059 [P] [US3] Créer `backend/app/modules/account/router.py` avec endpoints : `POST /account/invite`, `GET /account/users`, `DELETE /account/users/{user_id}`. Tous avec `Depends(get_current_user)`. Vérifier `current_user.role == UserRole.PME` pour tous (Admin → 403). Injection `Depends(get_email_service)` (provider qui retourne `LoggingEmailDelivery` en F02).
- [ ] T060 [P] [US3] Créer `backend/app/api/deps.py::get_email_service` : dépendance FastAPI qui retourne une instance `LoggingEmailDelivery` (singleton de module).
- [ ] T061 [US3] Modifier `backend/app/api/auth.py::register` : si `data.invite_token` est présent, lookup `account_invitations` via `token_lookup = sha256(token).hex()` ; valider `status='pending'` + `expires_at > now()` + verify_invite_token ; créer le user avec `account_id = invitation.account_id`, `role = PME` ; marquer invitation `accepted` ; sinon (cas standard) créer un nouvel `Account` et y rattacher le user. Doit faire passer T054 (c).
- [ ] T062 ⚠️ ZONE INTERDITE [US3] Modifier `backend/app/main.py` (sérialiser via orchestrateur) : monter `account_router` sur `/api`. Si conflit → signaler.
- [ ] T063 [P] [US3] Créer `frontend/app/composables/useAccountTeam.ts` : exposer `inviteMember(email)`, `listTeam()`, `removeMember(id)`, états réactifs `members`, `pendingInvitations`, `loading`, `error`. Doit faire passer T056.
- [ ] T064 [P] [US3] Créer `frontend/app/pages/account/team.vue` : page (layout par défaut PME) avec formulaire d'invitation (input email + bouton « Inviter »), liste des membres avec `<RoleBadge>`, liste des invitations en cours, bouton « Retirer » pour chaque. Toasts de succès/erreur. Mode sombre obligatoire (variantes `dark:`). Confirmation modale avant retrait.
- [ ] T065 [P] [US3] Modifier `frontend/app/pages/register.vue` : lire le query param `invite` (si présent), pré-remplir l'email correspondant à l'invitation (récupéré via une route publique `GET /account/invitations/preview?token=<token>` ou reçu en paramètre), envoyer `invite_token` lors du submit. Si invitation invalide/expirée, afficher un message d'erreur clair en français.
- [ ] T066 [P] [US3] Modifier `frontend/app/pages/login.vue` : si query param `invite` présent ET utilisateur non connecté, rediriger vers `/register?invite=<token>` au lieu d'afficher login.

**Checkpoint US3** : flux invite/accept/list/remove complet, accès partagé fonctionnel.

---

## Phase 6 : User Story 4 — Refresh token rotatif + logout (Priority: P2)

**Goal** : Rotation refresh token à chaque appel `/auth/refresh`, fenêtre de grâce 5 s, endpoint `/auth/logout` qui révoque tous les refresh tokens, JWT 24 h.

**Independent Test** : login → RT1 ; refresh → RT2 ≠ RT1 ; replay RT1 immédiatement → grace OK ; replay RT1 après 6 s → 401 ; logout → RT2 invalidé.

### Tests US4 (TDD red)

- [ ] T067 [P] [US4] Créer `backend/tests/integration/test_jwt_expiry_24h.py` : login → décoder access_token → vérifier `exp - iat == 86400`.
- [ ] T068 [P] [US4] Créer `backend/tests/integration/test_refresh_token_rotation.py` : (a) refresh révoque l'ancien et émet nouveau, (b) replay RT1 dans la fenêtre 5 s → retourne le successeur (RT2 même valeur), (c) replay RT1 après 5 s → 401, (d) chaque rotation insère une ligne dans `refresh_tokens` avec `replaced_by_jti` pointant vers le successeur.
- [ ] T069 [P] [US4] Créer `backend/tests/integration/test_logout_revokes_all.py` : (a) user avec 3 refresh tokens actifs, (b) POST /auth/logout → 204, (c) tous les `revoked_at` sont SET, (d) refresh avec n'importe quel ancien RT → 401.
- [ ] T070 [P] [US4] Créer `backend/tests/integration/test_account_deactivation.py` : (a) accounts.is_active = false → tous les refresh tokens révoqués, (b) login → 403, (c) refresh → 401.

### Implémentation US4

- [ ] T071 [US4] Modifier `backend/app/core/security.py` : `create_refresh_token(user_id) -> tuple[str, str, datetime]` retourne (token, jti, expires_at) ; ajouter helpers `decode_refresh_token(token) -> RefreshTokenPayload` (avec jti). T002 a déjà mis à jour la durée access_token.
- [ ] T072 [US4] Créer `backend/app/services/refresh_token_service.py` (ou ajouter à `security.py` si < 200 LOC) : (a) `persist_refresh_token(db, user_id, jti, issued_at, expires_at)`, (b) `rotate_refresh_token(db, old_jti, new_jti, new_expires_at)` (gère fenêtre de grâce 5 s + logging événements `grace_window_reuse` / `refresh_token_replay`), (c) `revoke_all_refresh_tokens(db, user_id)`.
- [ ] T073 [US4] Modifier `backend/app/api/auth.py::login` : émettre refresh token + persister dans `refresh_tokens`. Vérifier `accounts.is_active` avant login. Doit faire passer T067 et T070.
- [ ] T074 [US4] Modifier `backend/app/api/auth.py::refresh` : appliquer `rotate_refresh_token`. Logger événements. Doit faire passer T068.
- [ ] T075 [US4] Ajouter `backend/app/api/auth.py::logout` : `POST /auth/logout` (Depends(get_current_user), aucun body, retourne 204) qui appelle `revoke_all_refresh_tokens(db, current_user.id)`. Doit faire passer T069.
- [ ] T076 [P] [US4] Modifier `frontend/app/composables/useAuth.ts` : ajouter méthode `logout()` qui POST /auth/logout puis vide le store.
- [ ] T077 [P] [US4] Modifier `frontend/app/stores/auth.ts` : `clearSession()` appelé après logout, retire access_token et refresh_token du localStorage.

**Checkpoint US4** : sessions sécurisées avec rotation, logout côté serveur fonctionnel.

---

## Phase 7 : Tests E2E Playwright (transversaux, après US1-US4)

**Purpose** : valider end-to-end les 4 user stories via Playwright. Le fichier de tests est obligatoire selon le projet (`frontend/tests/e2e/F02-multitenant-roles-rls.spec.ts`).

- [ ] T078 [P] Créer `frontend/tests/e2e/fixtures/F02-helpers.ts` : helpers `createPmeAccount(api, name)`, `createAdminAccount(api, name)` (via SQL direct ou seed endpoint dev-only), `loginAs(page, credentials)`, `extractInviteTokenFromLogs()`.
- [ ] T079 Créer `frontend/tests/e2e/F02-multitenant-roles-rls.spec.ts` avec 4 scénarios indépendants :
  - **Scénario 1 (US1) "Isolation 2 PME"** : créer Alice@PME-A et Bob@PME-B en parallèle, login en tant qu'Alice, créer une conversation, login en tant que Bob (autre browser context), créer une conversation, vérifier que ni Alice ni Bob ne voient l'autre conversation dans leurs interfaces respectives.
  - **Scénario 2 (US2) "Accès admin"** : login Admin (seed) sur `/admin/health` → page admin chargée avec layout admin (vérifier classes CSS rouges), badge ADMIN visible. Login PME → naviguer vers `/admin/health` → redirection vers `/dashboard`.
  - **Scénario 3 (US3) "Flow invitation"** : Alice invite Carole via `/account/team`, lire l'URL d'invitation depuis les logs (helper), ouvrir un autre browser context, naviguer vers `/register?invite=<token>`, finaliser l'inscription, vérifier que Carole voit la conversation d'Alice.
  - **Scénario 4 (US4) "Logout révocation"** : Alice login → ouvrir 2 onglets → logout dans onglet 1 → vérifier que les requêtes authentifiées retournent 401 dans onglet 2 (après expiration access_token simulée ou rappel manuel `/auth/refresh` qui doit échouer).
- [ ] T080 [P] Documenter dans `frontend/tests/e2e/README.md` (créer ou étendre) : commandes de lancement (`npx playwright test tests/e2e/F02-multitenant-roles-rls.spec.ts --reporter=html`), prérequis env (postgres up, backend up, frontend up, seed admin appliqué).

**Checkpoint Phase 7** : tests E2E exécutables et passants. La phase B' (e2e-runner) les utilisera.

---

## Phase 8 : Documentation & Garde-fou CI

- [ ] T081 [P] Créer `docs/auth-and-multitenant.md` avec sections : (1) Modèle de menaces (acteurs, vecteurs, mitigations), (2) Architecture RLS (ENABLE+FORCE, SET LOCAL, fail-closed), (3) Rotation refresh token (algorithme, fenêtre grâce, logout), (4) Procédure pas-à-pas pour ajouter une nouvelle table métier (modèle SQLAlchemy + migration : ADD account_id FK, INDEX, ENABLE+FORCE RLS, CREATE 2 policies + test d'isolation), (5) Conventions de seed Admin (script `app.scripts.seed_admin`), (6) Troubleshooting (fail-closed, migration rollback, replay token).
- [ ] T082 [P] Créer `backend/tests/ci/test_no_metier_table_without_account_id.py` : (a) liste des tables métier connues (allow-list), (b) scan de tous les modèles SQLAlchemy via `Base.metadata.tables`, (c) pour chaque table métier listée, vérifier présence colonne `account_id` UUID NOT NULL FK + 2 RLS policies actives en BDD via `pg_policies`. Test échoue avec un message clair si une nouvelle table métier est ajoutée sans `account_id` ou sans RLS. Doit faire passer FR-034.
- [ ] T083 [P] Créer `backend/app/scripts/seed_admin.py` : script CLI avec `argparse` (`--email`, `--password`, `--full-name`) qui crée un user `role=ADMIN`, `account_id=NULL`, hashed_password via `hash_password`. Affiche le user créé. À exécuter manuellement post-migration. Aucun endpoint public.

---

## Phase 9 : Polish & Cross-Cutting

- [ ] T084 [P] Étendre `backend/tests/unit/` pour couvrir les cas non-bonheur restants (validation Pydantic, edge cases service `accept_invitation` avec utilisateur déjà existant, etc.) afin d'atteindre couverture ≥ 80 % sur le périmètre F02.
- [ ] T085 [P] Étendre `frontend/tests/unit/` (composables, composants, store auth) pour atteindre couverture ≥ 80 % sur le périmètre F02.
- [ ] T086 [P] Vérifier dark mode complet sur tous les composants/pages F02 : `frontend/app/components/ui/RoleBadge.vue`, `frontend/app/layouts/admin.vue`, `frontend/app/pages/admin/health.vue`, `frontend/app/pages/account/team.vue`, modifications de `pages/login.vue` et `pages/register.vue`. Aucune classe Tailwind sans variante `dark:`.
- [ ] T087 [P] Linter backend : `cd backend && source venv/bin/activate && python -m py_compile $(find app -name '*.py')` → 0 erreur. Si configuré, `ruff check` et `black --check` à 0 erreur.
- [ ] T088 [P] Type-check frontend : `cd frontend && npx nuxt typecheck` (ou `npm run build`) → 0 erreur.
- [ ] T089 Validation manuelle via `quickstart.md` : exécuter chaque section et confirmer le comportement attendu.
- [ ] T090 Mise à jour de `CLAUDE.md` (zone interdite — sérialiser via orchestrateur) via le script `bash .specify/scripts/bash/update-agent-context.sh claude` qui ajoute une entrée Recent Changes pour F02 (multi-tenant + RLS + roles).
- [ ] T091 [P] Créer `backend/tests/integration/test_rls_performance_benchmark.py` qui mesure la latence p95 sur 5 endpoints chauds (chat list, dashboard, fund_applications list, conversations list, documents list) AVANT/APRÈS activation RLS. Tolérance : dégradation < 20 % (SC-009). Utilise `pytest-benchmark` ou un timer manuel ; échoue si dégradation > 20 %.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** : aucune dépendance. T001-T006 en parallèle.
- **Phase 2 (Foundational)** : dépend de Phase 1. **BLOQUE TOUTES les user stories.** Tests T007-T013 d'abord (tous [P]), puis modèles T014-T030 ([P] dans la limite des fichiers distincts), puis migration T031 (dépend de tous les modèles), puis helpers T032-T033 ([P]).
- **Phase 3 (US1 isolation)** : dépend de Phase 2. T034-T035 d'abord, puis T036 (modifie deps.py partagée), T037 (idem), T038 (vérification).
- **Phase 4 (US2 admin)** : dépend de Phase 2 + T036/T037. Tests d'abord, puis backend (T044, T045, T046 sérialisé), puis frontend (T047-T052 [P] majoritairement).
- **Phase 5 (US3 invitations)** : dépend de Phase 2 + T036/T037. Tests d'abord, puis backend modules account (T057-T062), puis frontend (T063-T066).
- **Phase 6 (US4 refresh rotation)** : dépend de Phase 2 + T036. Tests d'abord, puis backend (T071-T075), puis frontend logout (T076-T077).
- **Phase 7 (E2E Playwright)** : dépend de toutes les US (Phases 3-6). T078 fixtures puis T079 tests.
- **Phase 8 (doc + CI)** : peut démarrer après Phase 2 ; T081 [P] de la doc en parallèle des US ; T082 ne peut être finalisé qu'après les modèles (Phase 2).
- **Phase 9 (polish)** : finale, dépend de toutes les phases précédentes.

### User Story Dependencies

- **US1 (P1 isolation)** : aucune dépendance entre stories. C'est la fondation de toutes les autres.
- **US2 (P1 admin)** : dépend uniquement de US1 (utilise `set_rls_context` indirectement via `get_current_admin`).
- **US3 (P2 invitations)** : dépend de US1 (RLS sur invitations) ; ne dépend pas de US2.
- **US4 (P2 refresh rotation)** : indépendante des autres US au niveau code (touche `auth.py` uniquement). Peut être implémentée en parallèle de US3.

### Parallel Opportunities

- Phase 1 : T001-T006 tous en parallèle.
- Phase 2 tests T007-T013 : tous [P] (fichiers distincts).
- Phase 2 modèles T014-T016 [P], T018-T030 [P] (fichiers distincts, T017 user.py séquentiel).
- Phase 4-6 frontend : majorité [P] entre composants.

---

## Parallel Example : Phase 2 (Foundational Tests)

Lancer en parallèle :

```bash
# Tests modèles (tous indépendants)
pytest backend/tests/unit/test_models_account.py
pytest backend/tests/unit/test_models_refresh_token.py
pytest backend/tests/unit/test_models_account_invitation.py
pytest backend/tests/unit/test_models_user_role_constraint.py
pytest backend/tests/unit/test_email_delivery.py
pytest backend/tests/unit/test_rls_session_helper.py
```

Puis création des modèles en parallèle dans des branches de pensée séparées :

```text
Task : "Créer Account model dans backend/app/models/account.py"
Task : "Créer RefreshToken model dans backend/app/models/refresh_token.py"
Task : "Créer AccountInvitation model dans backend/app/models/account_invitation.py"
Task : "Modifier company.py pour ajouter account_id"
Task : "Modifier document.py pour ajouter account_id"
... (12 modifications de modèles existants en parallèle car fichiers distincts)
```

Puis convergence sur la migration T031 (dépendance forte sur tous les modèles).

---

## Implementation Strategy

### MVP First (US1 isolation seule)

1. Phase 1 (Setup)
2. Phase 2 (Foundational : tests + modèles + migration + helpers)
3. Phase 3 (US1) — RLS appliqué partout
4. **STOP & VALIDATE** : 2 PME ne se voient jamais. MVP livrable.

### Incremental Delivery

1. MVP (US1)
2. + US2 (Admin protégé) → back-office squelette opérationnel pour F09
3. + US3 (Invitations) → multi-utilisateurs PME
4. + US4 (Refresh rotation) → posture sécurité renforcée
5. Phase 7 (E2E) une fois toutes les US livrées
6. Phase 8 (doc + CI) → garde-fous post-merge
7. Phase 9 (polish) → couverture finale

### Parallel Team Strategy

Avec plusieurs développeurs (post-Phase 2) :
- Dev A : US1 + suppression whitelist (US2 partial)
- Dev B : US3 (invitations)
- Dev C : US4 (refresh rotation)
- Dev D : frontend (US2 visuel + US3 frontend)

Convergence sur Phase 7 (E2E) qui valide tous les flux.

---

## Notes

- Tests E2E Playwright OBLIGATOIRES (T079) : 4 scénarios couvrant US1/US2/US3/US4.
- Couverture ≥ 80 % imposée (Phase 9 polish).
- Migration Alembic UNIQUE (T031) — UNE seule migration en flight gérée par l'orchestrateur (zone interdite).
- `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/deps.py` sont zones partagées — sérialiser via orchestrateur.
- Mode sombre obligatoire sur tous les nouveaux composants frontend.
- Aucun secret hardcodé : tous les paramètres via `core/config.py` (env vars).
- TDD strict : tous les tests sont en RED avant implémentation. Phase B (orchestrateur) doit lancer les tests AVANT de coder.
- Commits intermédiaires recommandés : un par checkpoint de phase.
