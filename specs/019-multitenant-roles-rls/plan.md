# Implementation Plan: F02 — Multi-tenant + Rôle Admin + Row-Level Security

**Branch**: `019-multitenant-roles-rls` (orchestrator branch : `feat/F02-multitenant-roles-rls`) | **Date**: 2026-05-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-multitenant-roles-rls/spec.md`

## Summary

Introduire le multi-tenant strict via une entité `Account`, le rôle Admin, et la Row-Level Security PostgreSQL. La couche d'authentification JWT existante est étendue (rotation refresh token, logout, JWT 24 h) et complétée par une dépendance `get_current_admin`. Les 14 tables métier reçoivent une colonne `account_id NOT NULL` et des policies RLS `ENABLE` + `FORCE ROW LEVEL SECURITY` qui garantissent l'isolation indépendamment du code applicatif. Un module `app/modules/account/` gère les invitations d'équipe (TTL 7 jours, livraison stub via `LoggingEmailDelivery`), un module `app/modules/admin/` expose le squelette `/api/admin/health`. Côté frontend, un middleware `admin.ts` non global, un layout `admin.vue` (accent rouge/orange + badge « Mode Admin »), un composable étendu `useAuth.isAdmin` et une page `account/team.vue` complètent la livraison. L'anti-pattern whitelist email est supprimé.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**:
- Backend : FastAPI, SQLAlchemy async (`asyncpg`), Alembic, Pydantic v2, `python-jose` (JWT, déjà présent), `passlib` (bcrypt, déjà présent)
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4
- Tests : pytest + pytest-asyncio + pytest-cov (backend), Vitest + @vue/test-utils + happy-dom (frontend), Playwright (E2E)

**Storage**: PostgreSQL 16 + pgvector (existant). Nouvelles tables : `accounts`, `refresh_tokens`, `account_invitations`. RLS PostgreSQL natif activé via `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` sur 14 tables métier. Variables de session `app.current_account_id` et `app.current_role` positionnées par `SET LOCAL` au sein de chaque transaction authentifiée.

**Testing**: pytest (`backend/tests/`), Vitest (`frontend/tests/unit/`), Playwright (`frontend/tests/e2e/F02-multitenant-roles-rls.spec.ts`). Cible couverture ≥ 80 %.

**Target Platform**: Linux server (Docker Compose en local), navigateurs modernes côté frontend (Chromium/Firefox/Safari récents).

**Project Type**: Web application multi-tenant — backend FastAPI séparé du frontend Nuxt.

**Performance Goals**: Pas de dégradation > 20 % sur les 5 endpoints les plus chauds (chat, dashboard, applications/list, conversations/list, documents/list) après activation du RLS, mesuré par benchmark CI ; révocation de refresh token < 1 s ; invalidation de session sur désactivation d'`Account` < 1 s.

**Constraints**:
- Pas de Redis introduit : refresh tokens stockés dans PostgreSQL (table `refresh_tokens`).
- Pas de service SMTP réel : `LoggingEmailDelivery` en MVP (log INFO + persistance BDD).
- RLS en mode « fail-closed » : sans `app.current_account_id` SET, requêtes retournent 0 ligne.
- Rotation refresh token avec fenêtre de grâce 5 secondes (multi-onglets) via `replaced_by_jti`.
- Aucun secret hardcodé ; toutes les configs via `core/config.py` (env vars).
- Mode sombre obligatoire sur tout nouveau composant frontend (variantes `dark:` Tailwind).

**Scale/Scope**: 14 tables métier modifiées, 3 tables nouvelles, 1 migration Alembic (`019_multitenant_and_roles.py`), ~15 modifications de modèles SQLAlchemy, ~10 endpoints API nouveaux/modifiés (`/auth/refresh`, `/auth/logout`, `/api/account/invite`, `/api/account/users`, `/api/account/users/{id}`, `/api/admin/health`, etc.), 4-5 composants Vue nouveaux, 1 layout admin, 1 middleware admin, 1 page `account/team.vue`, 1 doc `docs/auth-and-multitenant.md`.

## Constitution Check

*GATE: doit passer avant Phase 0 research. Re-check après Phase 1 design.*

Évaluation par principe (constitution v1.0.0) :

| Principe | Évaluation | Justification |
|---|---|---|
| I. Francophone-First | ✅ PASS | Toutes les UI strings, messages d'erreur, doc `docs/auth-and-multitenant.md` en français avec accents. Code en anglais, commentaires/docstrings en français. |
| II. Architecture Modulaire | ✅ PASS | Modules `app/modules/admin/` et `app/modules/account/` créés en isolation. Pas de couplage avec les modules métier existants (le RLS est transversal mais reste un mécanisme infrastructure, pas une dépendance fonctionnelle directe). |
| III. Conversation-Driven UX | ✅ PASS (non-applicable) | F02 est une feature d'infrastructure ; aucun impact négatif sur la conversation. La page `account/team.vue` est un formulaire mais reste secondaire (gestion d'équipe). |
| IV. Test-First (NON-NÉGOCIABLE) | ✅ PASS | tasks.md spécifiera tests AVANT implémentation. Couverture cible ≥ 80 %. Tests : unitaires (modèles, deps), intégration (RLS isolation, rotation refresh), E2E (Playwright). |
| V. Sécurité & Données | ✅ PASS (renforcé) | F02 EST une feature de sécurité : RLS, rotation refresh, suppression whitelist anti-pattern. Aucun secret hardcodé. SQLAlchemy parameterized queries. JWT déjà en place. |
| VI. Inclusivité & Accessibilité | ✅ PASS | Messages d'erreur clairs en français (« Ce compte est désactivé », « Cette invitation a expiré »). Layout admin accessible (sémantique sidebar/header), dark mode obligatoire. Aucun parcours nouveau ne ralentit l'expérience PME standard. |
| VII. Simplicité & YAGNI | ✅ PASS | Pas de Redis (refresh tokens en BDD). Pas de SMTP (Logging stub). Pas de RBAC granulaire (Owner/Member/Viewer remis post-MVP). Réutilisation du JWT existant. |

**Verdict** : PASS sur tous les principes. Aucune dérogation à justifier.

## Project Structure

### Documentation (this feature)

```text
specs/019-multitenant-roles-rls/
├── plan.md                       # Ce fichier (/speckit.plan output)
├── spec.md                       # Spec clarifiée (/speckit.specify + /speckit.clarify output)
├── research.md                   # Phase 0 output (/speckit.plan)
├── data-model.md                 # Phase 1 output (/speckit.plan)
├── quickstart.md                 # Phase 1 output (/speckit.plan)
├── contracts/                    # Phase 1 output (/speckit.plan)
│   ├── auth.api.md               # /auth/refresh, /auth/logout (rotation)
│   ├── account.api.md            # /api/account/invite, /api/account/users
│   └── admin.api.md              # /api/admin/health
├── checklists/
│   └── requirements.md           # Spec quality checklist
└── tasks.md                      # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 019_multitenant_and_roles.py        # NOUVEAU — migration unique F02
├── app/
│   ├── core/
│   │   ├── config.py                            # MODIFIÉ : access_token_expire_minutes 480→1440
│   │   ├── database.py                          # MODIFIÉ : helper SET LOCAL session vars (intégration RLS)
│   │   ├── rls_session.py                       # NOUVEAU : middleware/helper SET LOCAL app.current_account_id, app.current_role
│   │   ├── security.py                          # MODIFIÉ : génération JTI, helpers refresh token store
│   │   └── email_delivery.py                    # NOUVEAU : interface EmailDeliveryService + LoggingEmailDelivery
│   ├── api/
│   │   ├── auth.py                              # MODIFIÉ : /auth/login (émet refresh token persisté), /auth/refresh (rotation), /auth/logout (NOUVEAU)
│   │   └── deps.py                              # MODIFIÉ : get_current_user (SET LOCAL RLS vars), get_current_admin (NOUVEAU)
│   ├── models/
│   │   ├── account.py                           # NOUVEAU : Account
│   │   ├── account_invitation.py                # NOUVEAU : AccountInvitation
│   │   ├── refresh_token.py                     # NOUVEAU : RefreshToken
│   │   ├── user.py                              # MODIFIÉ : role enum, account_id FK, contrainte CHECK
│   │   ├── company.py                           # MODIFIÉ : account_id FK + UNIQUE (1:1 Account)
│   │   ├── document.py                          # MODIFIÉ : account_id FK
│   │   ├── esg.py                               # MODIFIÉ : account_id FK sur esg_assessments
│   │   ├── carbon.py                            # MODIFIÉ : account_id FK sur carbon_assessments
│   │   ├── credit.py                            # MODIFIÉ : account_id FK sur credit_scores
│   │   ├── financing.py                         # MODIFIÉ : account_id FK sur fund_matches
│   │   ├── application.py                       # MODIFIÉ : account_id FK sur fund_applications
│   │   ├── action_plan.py                       # MODIFIÉ : account_id FK sur action_plans, action_items, reminders
│   │   ├── conversation.py                      # MODIFIÉ : account_id FK
│   │   ├── message.py                           # MODIFIÉ : account_id FK
│   │   ├── interactive_question.py              # MODIFIÉ : account_id FK
│   │   ├── tool_call_log.py                     # MODIFIÉ : account_id FK
│   │   └── report.py                            # MODIFIÉ : account_id FK
│   ├── schemas/
│   │   ├── account.py                           # NOUVEAU : AccountResponse, InvitationCreate, InvitationResponse
│   │   ├── auth.py                              # MODIFIÉ : LogoutRequest, RefreshRequest tolérant grâce
│   │   └── admin.py                             # NOUVEAU (squelette, à enrichir par F09)
│   ├── modules/
│   │   ├── account/
│   │   │   ├── __init__.py                      # NOUVEAU
│   │   │   ├── router.py                        # NOUVEAU : /api/account/invite, /api/account/users
│   │   │   ├── service.py                       # NOUVEAU : create_invitation, accept_invitation, list_account_users, remove_account_user
│   │   │   └── tokens.py                        # NOUVEAU : generate_invite_token, hash_invite_token, validate_invite_token
│   │   ├── admin/
│   │   │   ├── __init__.py                      # NOUVEAU (squelette pour F09)
│   │   │   └── router.py                        # NOUVEAU : GET /api/admin/health (Depends(get_current_admin))
│   │   └── financing/
│   │       └── router.py                        # MODIFIÉ : suppression whitelist email à la ligne 118, remplacée par Depends(get_current_admin)
│   └── main.py                                  # ⚠️ ZONE INTERDITE — modifier UNIQUEMENT pour monter les nouveaux routeurs admin/account (sérialisé par orchestrateur)
└── tests/
    ├── unit/
    │   ├── test_models_account.py               # NOUVEAU
    │   ├── test_models_refresh_token.py         # NOUVEAU
    │   ├── test_models_account_invitation.py    # NOUVEAU
    │   ├── test_models_user_role_constraint.py  # NOUVEAU (contrainte CHECK)
    │   ├── test_email_delivery.py               # NOUVEAU
    │   └── test_rls_session_helper.py           # NOUVEAU
    ├── integration/
    │   ├── test_rls_isolation.py                # NOUVEAU : 2 accounts, vérifier que A ne voit jamais B
    │   ├── test_admin_route_protection.py       # NOUVEAU : 403 PME / 200 ADMIN
    │   ├── test_refresh_token_rotation.py       # NOUVEAU : RT1 révoqué, RT2 émis, replay rejeté, fenêtre grâce 5s acceptée
    │   ├── test_logout_revokes_all.py           # NOUVEAU : POST /auth/logout révoque tous les RT
    │   ├── test_account_invitation_flow.py      # NOUVEAU : invite → register → access partagé
    │   ├── test_account_deactivation.py         # NOUVEAU : is_active=false invalide sessions
    │   ├── test_financing_admin_protection.py   # NOUVEAU : POST /api/financing/funds requiert ADMIN
    │   └── test_jwt_expiry_24h.py               # NOUVEAU : access_token_expire_minutes == 1440
    └── ci/
        └── test_no_metier_table_without_account_id.py  # NOUVEAU : scan models/, garde-fou FR-034

frontend/
├── app/
│   ├── composables/
│   │   ├── useAuth.ts                           # MODIFIÉ : ajout role, account, isAdmin, logout (révoque côté serveur)
│   │   └── useAccountTeam.ts                    # NOUVEAU : list/invite/remove team
│   ├── components/
│   │   └── ui/
│   │       └── RoleBadge.vue                    # NOUVEAU
│   ├── layouts/
│   │   └── admin.vue                            # NOUVEAU : sidebar admin, badge Mode Admin, accent rouge/orange
│   ├── middleware/
│   │   └── admin.ts                             # NOUVEAU (non global) : redirige non-Admin vers /dashboard
│   ├── pages/
│   │   ├── admin/
│   │   │   └── health.vue                       # NOUVEAU : page minimale 200 si admin (squelette F09)
│   │   ├── account/
│   │   │   └── team.vue                         # NOUVEAU : invite/list/remove collaborateurs
│   │   ├── login.vue                            # MODIFIÉ : gérer ?invite=<token>
│   │   └── register.vue                         # MODIFIÉ : gérer ?invite=<token>
│   ├── stores/
│   │   └── auth.ts                              # MODIFIÉ : ajout account, role, isAdmin
│   └── types/
│       └── auth.ts                              # MODIFIÉ : enum Role, interface AccountSummary, etc.
└── tests/
    ├── unit/
    │   ├── useAuth.spec.ts                      # MODIFIÉ : tests isAdmin
    │   ├── useAccountTeam.spec.ts               # NOUVEAU
    │   ├── RoleBadge.spec.ts                    # NOUVEAU
    │   └── middleware-admin.spec.ts             # NOUVEAU
    └── e2e/
        └── F02-multitenant-roles-rls.spec.ts    # NOUVEAU : tests E2E Playwright complets

docs/
└── auth-and-multitenant.md                      # NOUVEAU : modèle de menaces, RLS, rotation, ajout d'une nouvelle table métier
```

**Structure Decision** : Web application séparée backend/frontend (pattern existant). Les nouveaux modules backend `app/modules/admin/` et `app/modules/account/` suivent la convention existante (router.py + service.py par module). Frontend respecte la structure Nuxt 4 (`app/components/ui/`, `app/layouts/`, `app/middleware/`, `app/pages/`, `app/composables/`). Les tests Playwright sont consolidés dans `frontend/tests/e2e/F02-multitenant-roles-rls.spec.ts`.

⚠️ **Zone interdite à coordonner avec l'orchestrateur** : `backend/app/main.py` (montage des routeurs `admin` + `account`) est zone d'écriture sérialisée. La phase B doit signaler `zone_conflict` si une autre feature modifie ce fichier en parallèle.

## Phase 0 : Outline & Research — Décisions techniques

Voir `research.md` (généré séparément) pour le détail. Résumé ici :

| Sujet | Décision | Rationale courte |
|---|---|---|
| Stockage refresh tokens | PostgreSQL table `refresh_tokens` | Pas de Redis MVP (invariant simplicité). Indexable, atomique, jointure user. |
| RLS PostgreSQL approach | `ENABLE` + `FORCE ROW LEVEL SECURITY` sur 14 tables, policies `pme_access_own_account` (USING+CHECK sur `account_id = current_setting('app.current_account_id')::uuid`) et `admin_full_access` (USING+CHECK sur `current_setting('app.current_role') = 'ADMIN'`) | FORCE garantit que même le propriétaire de la table (rôle PostgreSQL utilisé par l'app) est soumis aux policies. Fail-closed. |
| Variables de session | `app.current_account_id`, `app.current_role` via `SET LOCAL` dans une transaction par requête authentifiée | Standard PostgreSQL. Compatible asyncpg + SQLAlchemy async. |
| Hook session SQLAlchemy | Helper `set_rls_context(session, account_id, role)` appelé dans `get_current_user` (et dans une dépendance `get_db_with_rls`) AVANT toute query métier | Plus lisible qu'un middleware FastAPI bas-niveau ; testable unitairement. |
| Génération JTI | `uuid.uuid4()` claim `jti` dans le JWT refresh, indexé dans `refresh_tokens.jti` | Standard JWT, recherche O(log n). |
| TTL invitation | 7 jours (configurable via `INVITE_TOKEN_TTL_DAYS`) | Industry standard, équilibre sécurité/UX. |
| Hash token invitation | bcrypt (déjà disponible via `passlib`) | Pas de nouvelle dépendance ; protection contre timing attacks. |
| Email delivery | `EmailDeliveryService` Protocol + `LoggingEmailDelivery` | Swap futur sans modification d'appelants (SOLID). |
| Backfill `account_id` sur 14 tables | Ordonné par ordre topologique (`users` d'abord, puis tables qui référencent `users`) ; pour chaque ligne, lookup `users.account_id`. NULL initialement, puis `ALTER COLUMN ... SET NOT NULL` après backfill complet. | Standard, réversible. |
| Doublons `company_profiles` au backfill | Conserver le profil le plus récent par `Account`, marquer les autres `archived = true` (ou table `_legacy_company_profiles_archive` selon la complexité) | Unicité 1:1 Account/CompanyProfile (FR-007a). |
| Numérotation Alembic | `019_multitenant_and_roles.py` (head courant après `018_create_interactive_questions`) | Continuité numérotation locale. |
| Frontend admin layout couleurs | TailwindCSS classes `bg-red-700`, `text-red-50`, badges via `RoleBadge.vue` ; mode sombre via `dark:bg-red-900` | Différenciation visuelle nette du thème PME (vert/bleu) sans ajout de dépendance. |
| Frontend `useAuth` extension | Pinia store `stores/auth.ts` ajoute `account` et `role` ; `useAuth.ts` expose `isAdmin: computed(() => store.user?.role === 'ADMIN')` | Réutilisation du store existant, pas de Vuex/autre state lib. |

**Output** : `research.md` couvrant chaque décision avec format Decision/Rationale/Alternatives.

## Phase 1 : Design & Contracts

**Prérequis** : `research.md` complet.

### 1. Data model — `data-model.md`

Décrit en détail les 4 nouvelles entités (`Account`, `RefreshToken`, `AccountInvitation`, `User étendu`) + récap des 14 tables métier qui reçoivent `account_id`. Inclut :
- Champs et types
- Contraintes (unicité, CHECK, FK avec ON DELETE)
- Index recommandés
- Diagramme texte ASCII des relations
- Lifecycle des entités (transitions de statut pour invitations, refresh tokens)

### 2. Contracts API — `contracts/`

Trois fichiers Markdown détaillent les endpoints :

**`contracts/auth.api.md`** :
- `POST /auth/login` — émet access + refresh token (refresh persisté en BDD)
- `POST /auth/refresh` — rotation : révoque l'ancien, émet nouveau, gère fenêtre grâce 5 s
- `POST /auth/logout` — révoque tous les refresh tokens du user

**`contracts/account.api.md`** :
- `POST /api/account/invite` — body `{email, role?}`, génère invitation (TTL 7 j), journalise l'envoi via `LoggingEmailDelivery`
- `GET /api/account/users` — liste les membres actifs + invitations en cours du compte
- `DELETE /api/account/users/{user_id}` — retire un membre (ou révoque une invitation)

**`contracts/admin.api.md`** :
- `GET /api/admin/health` — 200 si Admin, 403 sinon (squelette F09)

Chaque contrat documente : path, method, params, request body, response (success/error), codes HTTP, exemples curl, comportement RLS attendu.

### 3. Quickstart — `quickstart.md`

Guide pas-à-pas pour valider F02 manuellement :
1. Lancer `alembic upgrade head` → migration 019
2. Seed Admin via script `python -m app.scripts.seed_admin` (ou via SQL d'amorçage documenté)
3. Créer 2 PME via `/auth/register`
4. Vérifier isolation : connexion PME A, appel `GET /api/conversations`, aucune trace de PME B
5. Tester rôle Admin : connexion Admin, `GET /api/admin/health` → 200 ; idem en PME → 403
6. Tester invitation : `POST /api/account/invite`, ouvrir lien, register, vérifier accès partagé
7. Tester rotation refresh : capturer RT1, refresh → RT2, replay RT1 → 401 (sauf grâce 5 s)

### 4. Agent context update

Exécuter `bash .specify/scripts/bash/update-agent-context.sh claude` (à la fin de la phase B, hors phase A) pour mettre à jour les marqueurs CLAUDE.md sans toucher aux sections manuelles. **Phase A ne modifie PAS CLAUDE.md** (zone interdite orchestrateur).

**Output** : `data-model.md`, `contracts/auth.api.md`, `contracts/account.api.md`, `contracts/admin.api.md`, `quickstart.md`.

## Phase 2 : Tasks (généré séparément par /speckit.tasks)

Voir `tasks.md`. La phase 2 est gérée par la commande `/speckit.tasks` indépendamment.

## Re-évaluation Constitution Check (post-Phase 1 design)

Aucun élément du design ne contrevient aux 7 principes. Notamment :
- Test-First (IV) : tasks.md ordonnera les tests AVANT l'implémentation pour chaque entité (pattern TDD strict).
- Sécurité (V) : RLS + rotation refresh + suppression whitelist = renforcement net de la sécurité.
- Simplicité (VII) : aucune nouvelle dépendance externe (Redis, SMTP, Celery non introduits).

**Verdict** : PASS. Pas de section Complexity Tracking nécessaire.

## Complexity Tracking

> Aucune dérogation à justifier. Section vide.
