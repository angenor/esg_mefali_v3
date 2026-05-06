# F02 — Multi-tenant + Rôle Admin + Row-Level Security

**Module(s) source(s)** : Module 0.2 (Auth et Rôles)
**Priorité** : P0 — BLOQUANTE pour le back-office Admin (F09) et la conformité multi-tenant
**Dépendances** : aucune (feature de fondation)
**Estimation** : 2 sprints

## Contexte & motivation

Le brainstorming Module 0.2 spécifie 2 rôles (`PME`, `Admin`), du multi-tenant via `account_id` sur tables métier, et de la Row-Level Security PostgreSQL pour isolation stricte.

**État actuel** :
- Le modèle `User` (`backend/app/models/user.py:9-20`) a uniquement `email`, `hashed_password`, `full_name`, `company_name`, `is_active`. **Aucun champ `role`**.
- Aucune notion de `account_id` ni d'`accounts` table. L'isolation se fait par `user_id` direct sur chaque table métier (1 user = 1 compte).
- Aucune `CREATE POLICY` Row-Level Security PostgreSQL — `grep "CREATE POLICY"` → 0 résultats.
- Aucun routeur `/api/admin/*`. Le seul "guard admin" est un anti-pattern : whitelist d'emails en dur dans `backend/app/modules/financing/router.py:118` (`admin_emails = {"admin@esg-mefali.com", "admin@mefali.org"}`).
- JWT access token : 480 minutes (8h) au lieu de 24h spécifiées (`backend/app/core/config.py:20`).
- Refresh token endpoint existe (`/refresh`) mais sans rotation : l'ancien refresh reste valide jusqu'expiration 30 jours.
- Aucune page admin frontend, aucun middleware Nuxt admin.

**Conséquences** :
- Pas de back-office possible (Module 9 bloqué)
- Pas de support PME multi-utilisateurs (Module 7.3 impossible)
- Sécurité affaiblie : si un service applicatif oublie un `WHERE user_id = X`, fuite de données entre comptes
- Pas de protection administrative légitime des fonctionnalités sensibles

## User stories

- **PME** : « En tant que PME, je veux pouvoir inviter un collaborateur (autre user) avec accès partagé à toutes les données de mon entreprise (profil, candidatures, scores, plan d'action). »
- **Admin Mefali** : « En tant qu'admin de la plateforme, je dois pouvoir accéder au back-office (`/admin`) tandis qu'un user PME est redirigé en 403 ou vers `/dashboard`. »
- **Admin Mefali** : « Je dois pouvoir voir les comptes PME en lecture seule, mais chaque consultation est tracée dans l'audit log (Module 0.4 / F03). »
- **Architecte plateforme** : « Une erreur applicative ne doit JAMAIS permettre à un user d'une PME A de lire les données d'une PME B, même si le service oublie un filtre `WHERE`. »

## Périmètre fonctionnel

### Modèle `Role`

Enum strict côté backend et frontend :
- `PME` : utilisateur d'un compte PME
- `ADMIN` : équipe ESG Mefali (back-office)

Pas de granularité MVP (Owner/Member/Viewer = post-MVP).

### Entité `Account`

Représente un **compte PME** (collectivité de users sous une même entreprise) :
- `id: UUID` (PK)
- `name: str` (nom de l'entreprise)
- `created_at: datetime`
- `is_active: bool`
- `plan: enum('free', 'pro')` (post-MVP)

Un `Account` peut avoir N users.

### Modèle `User` étendu

Ajouter à `users` :
- `role: enum('PME', 'ADMIN') NOT NULL DEFAULT 'PME'`
- `account_id: UUID FK accounts.id NULL` (NULL pour les Admin Mefali, NOT NULL pour les PME)
- Garder les champs existants

Contrainte : `(role = 'PME' AND account_id IS NOT NULL) OR (role = 'ADMIN' AND account_id IS NULL)`.

### Migration data existante

- Pour chaque `User` existant avec `company_name`, créer un `Account(name=company_name)` et lier.
- Tous les users existants → `role = 'PME'` par défaut.
- Créer manuellement (seed) 1-2 comptes Admin avec emails de l'équipe Mefali.

### Multi-tenant : `account_id` sur tables métier

Ajouter colonne `account_id: UUID FK accounts.id NOT NULL` (avec backfill depuis `user_id → user.account_id`) sur :
- `company_profiles`
- `documents`
- `esg_assessments`
- `carbon_assessments`
- `credit_scores`
- `fund_matches`
- `fund_applications`
- `action_plans`, `action_items`, `reminders`
- `conversations`, `messages`
- `interactive_questions`
- `tool_call_logs`
- `reports`
- (toutes les futures tables métier ajoutées par F06, F07, F13, etc.)

Garder `user_id` (qui a fait quoi) ET `account_id` (à qui ça appartient) — distinct.

### Row-Level Security PostgreSQL

Pour chaque table métier, créer policies :

```sql
ALTER TABLE company_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account
  ON company_profiles
  FOR ALL
  TO application_user
  USING (account_id = current_setting('app.current_account_id')::uuid);

CREATE POLICY admin_full_access
  ON company_profiles
  FOR ALL
  TO application_user
  USING (current_setting('app.current_role') = 'ADMIN');
```

(Adapter pour les 13+ tables listées ci-dessus.)

### Middleware FastAPI : SET session variables

Dans `backend/app/api/deps.py`, étendre `get_current_user` :
- Après validation JWT, ouvrir la connexion DB
- `SET LOCAL app.current_account_id = '{user.account_id}'` (ou NULL si admin)
- `SET LOCAL app.current_role = '{user.role}'`
- Toutes les requêtes ORM dans la même transaction respectent les policies RLS

Créer `get_current_admin` :
- Identique à `get_current_user` mais lève `HTTPException(403)` si `user.role != 'ADMIN'`

### JWT et refresh token rotatif

- `access_token_expire_minutes` : 480 → **1440** (24h conforme spec)
- Refresh token rotation : à chaque appel `POST /auth/refresh`, invalider l'ancien refresh (table `refresh_tokens` avec `revoked_at` ou JWT JTI blacklist Redis), émettre un nouveau.
- Table `refresh_tokens(id, user_id, jti, issued_at, expires_at, revoked_at, replaced_by_jti)` (audit chain).
- Endpoint `POST /auth/logout` qui révoque tous les refresh tokens du user.

### Routeur Admin protégé

`backend/app/modules/admin/router.py` monté sur `/api/admin` avec `Depends(get_current_admin)` global :
- Sera peuplé par F09 (Back-Office Admin) avec les CRUD catalogue.
- En F02 : juste le squelette + endpoint `GET /admin/health` qui retourne 200 si admin, 403 sinon.

Supprimer la whitelist email anti-pattern dans `backend/app/modules/financing/router.py:118`.

### Frontend : middleware admin

Créer `frontend/app/middleware/admin.ts` (pas global) :
- Lit `useAuth().user.value.role`
- Si `role !== 'ADMIN'` : redirige vers `/dashboard` ou affiche 403
- Appliqué via `definePageMeta({ middleware: 'admin' })` sur les pages `/admin/*`

Créer `frontend/app/layouts/admin.vue` :
- Sidebar admin distincte (catalogue, sources, comptes PME, métriques, audit log)
- Header avec badge "Mode Admin"
- Style visuel différencié (couleur accent rouge/orange) pour éviter confusion avec PME

Étendre `useAuth` (ou store `auth.ts`) :
- Exposer `isAdmin: computed(() => user.value?.role === 'ADMIN')`
- Utilisable dans les composants pour cacher/afficher éléments

### Multi-utilisateurs PME (simplifié MVP)

- `Account` 1—N `User` (`account_id` FK)
- Tous les users d'un même `Account` ont accès aux mêmes données (via RLS sur `account_id`)
- Tous ont `role = 'PME'`, droits équivalents (pas de hiérarchie MVP)
- Endpoint `POST /api/account/invite` (envoie email d'invitation avec lien `/register?invite={token}`)
- Endpoint `GET /api/account/users` (liste les collaborateurs)
- Endpoint `DELETE /api/account/users/{id}` (retire un collaborateur)
- Page `frontend/app/pages/account/team.vue` : gestion équipe

## Hors-scope (post-MVP)

- OTP SMS, magic link, 2FA
- RBAC granulaire (Owner / Member / Viewer)
- Workflow d'approbation interne PME (relectures avant soumission)
- SSO entreprise (SAML/OIDC)

## Exigences techniques

### Backend

- Migration Alembic `019_multitenant_and_roles.py` :
  - Créer `accounts`
  - Créer `refresh_tokens`
  - Ajouter `role`, `account_id` à `users`
  - Backfill : un account par `company_name` distinct, lier les users
  - Ajouter `account_id` sur les 13+ tables métier (avec backfill et NOT NULL après)
  - Créer les RLS policies sur chaque table
- Modèles SQLAlchemy : `Account`, `RefreshToken`, mise à jour `User`
- Middleware `app/core/rls_session.py` qui hooke avant chaque requête pour SET les variables session
- Dépendance `get_current_admin` dans `api/deps.py`
- Module `app/modules/admin/` (squelette)
- Module `app/modules/account/` (invitations team)
- Mise à jour `core/config.py` : `access_token_expire_minutes = 1440`
- Mise à jour `api/auth.py` : rotation refresh token, endpoint logout
- Tests : 
  - Test isolation : créer 2 accounts, 2 users, vérifier que user A ne voit jamais data de account B (même via SQL direct sans WHERE)
  - Test rôle : user PME → 403 sur `/api/admin/*`
  - Test invitation : flow complet invite → register → access partagé

### Frontend

- Store `auth.ts` : ajouter `account`, `role`, `isAdmin`
- Middleware `middleware/admin.ts`
- Layout `layouts/admin.vue`
- Page `pages/account/team.vue` (gestion collaborateurs)
- Composant `<RoleBadge :role="user.role" />` pour afficher le rôle
- Mise à jour `pages/login.vue` et `pages/register.vue` pour gérer le flow invitation
- Mise à jour `composables/useAuth.ts` : nouvelle propriété `isAdmin`

### Base de données

- Tables nouvelles : `accounts`, `refresh_tokens`
- Colonnes nouvelles : `users.role`, `users.account_id`, `<13+ tables>.account_id`
- Index : `users(account_id)`, `*.account_id` sur toutes les tables métier
- Contraintes : check `(role = 'PME' AND account_id IS NOT NULL) OR (role = 'ADMIN' AND account_id IS NULL)`
- RLS policies sur 13+ tables
- Service variable PostgreSQL `app.current_account_id`, `app.current_role` configurables

## Critères d'acceptation

- [ ] Migration Alembic 019 créée et exécutable, backfill correct
- [ ] Modèle `User` étendu avec `role` + `account_id`
- [ ] Modèle `Account` créé
- [ ] 13+ tables métier ont `account_id NOT NULL`
- [ ] RLS policies actives et testées : un SQL direct sans filtre retourne uniquement les rows du `current_account_id` courant
- [ ] Whitelist email supprimée de `financing/router.py:118`, remplacée par `Depends(get_current_admin)`
- [ ] JWT access token expire à 24h (1440 min)
- [ ] Refresh token rotatif fonctionnel : ancien révoqué après usage
- [ ] Endpoint `/auth/logout` révoque tous les refresh tokens
- [ ] Routeur `/api/admin/*` refuse l'accès aux users PME (403)
- [ ] Frontend : `isAdmin` exposé, middleware admin fonctionne, layout admin existe
- [ ] Page `/account/team` permet d'inviter, lister, retirer un collaborateur
- [ ] Test E2E : 2 PME créées en parallèle ne voient jamais les données l'une de l'autre
- [ ] Test E2E : un admin créé manuellement accède à `/admin/*`, un user PME est redirigé
- [ ] Couverture tests ≥ 80 % sur `accounts`, `refresh_tokens`, RLS isolation
- [ ] Documentation : `docs/auth-and-multitenant.md` décrit le modèle de menaces, RLS, rotation

## Risques & garde-fous

- **Risque** : RLS mal configurée → soit blocage total des requêtes (pas de session var SET), soit fuite (policy laxiste). **Garde-fou** : test d'isolation systématique en CI ; SET LOCAL dans une dépendance FastAPI obligatoire ; échec immédiat si la session var n'est pas définie.
- **Risque** : la migration data échoue car certains users n'ont pas de `company_name`. **Garde-fou** : créer `account_id` initialement nullable, backfill avec un account "default" si manquant, puis NOT NULL. Logger les anomalies.
- **Risque** : la rotation du refresh token casse les sessions multi-onglets. **Garde-fou** : ajouter `replaced_by_jti` pour permettre une fenêtre de grâce de 5 secondes (si l'ancien JTI est utilisé alors qu'il est `replaced_by_jti`, accepter mais alerter).
- **Risque** : la performance des requêtes RLS dégrade trop. **Garde-fou** : benchmarker AVANT/APRÈS sur les 5 endpoints les plus chauds (chat, dashboard, applications/list) ; si dégradation > 20 %, optimiser via index sur `account_id` et planificateur.
- **Risque** : un developer crée une nouvelle table métier sans `account_id` et sans RLS. **Garde-fou** : test CI qui scanne `models/*.py` et vérifie que toute nouvelle table métier a `account_id` + RLS policy.
