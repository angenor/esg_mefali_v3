# Data Model — F02 Multi-tenant + Roles + RLS

**Feature** : 019-multitenant-roles-rls
**Date** : 2026-05-06

Ce document décrit le modèle de données introduit ou modifié par F02. Trois nouvelles tables, une modification du modèle `User`, et 14 tables métier qui reçoivent une colonne `account_id` + RLS policies.

---

## 1. Nouvelle entité — `Account`

Table : `accounts`

| Champ | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` ou `uuid_generate_v4()` | Identifiant unique de l'`Account` |
| `name` | VARCHAR(255) | NOT NULL | Nom de l'entreprise |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Statut actif/inactif (désactivation logicielle) |
| `plan` | VARCHAR(32) | NOT NULL, DEFAULT `'free'` | Plan tarifaire (`free`, `pro`) — préparé pour post-MVP |
| `created_at` | TIMESTAMPTZ | NOT NULL, server_default `now()` | Date de création |
| `updated_at` | TIMESTAMPTZ | NOT NULL, server_default `now()`, ON UPDATE `now()` | Date de mise à jour |

**Indexes** :
- `idx_accounts_is_active` sur `is_active` (filtrage rapide des comptes actifs)

**Relations** :
- 1 — N `users` (via `users.account_id`)
- 1 — 1 `company_profiles` (via `company_profiles.account_id` UNIQUE)
- 1 — N toutes les autres tables métier (via `<table>.account_id`)

---

## 2. Modification — `User`

Table : `users` (existante)

| Champ existant | Action | Détails |
|---|---|---|
| `id`, `email`, `hashed_password`, `full_name`, `company_name`, `is_active`, `created_at`, `updated_at` | Conservés | Pas de modification |

| Champ nouveau | Type | Contraintes | Description |
|---|---|---|---|
| `role` | ENUM(`'PME'`, `'ADMIN'`) | NOT NULL, DEFAULT `'PME'` | Rôle de l'utilisateur (Postgres ENUM type `user_role`) |
| `account_id` | UUID | NULL, FK → `accounts.id` ON DELETE RESTRICT | `Account` parent ; NULL pour les Admin |

**Contrainte CHECK** :
```sql
ALTER TABLE users ADD CONSTRAINT users_role_account_consistency CHECK (
  (role = 'PME' AND account_id IS NOT NULL) OR
  (role = 'ADMIN' AND account_id IS NULL)
);
```

**Indexes** :
- `idx_users_account_id` sur `account_id`
- `idx_users_role` sur `role`

**Lifecycle / state transitions** :
- À l'inscription standard : `role = 'PME'`, `account_id = <newly_created_account>`
- À l'inscription via invitation : `role = 'PME'`, `account_id = <invitation.account_id>`
- Création d'un Admin : uniquement via seed SQL ou script `app.scripts.seed_admin` ; aucun endpoint public
- Suppression : ON DELETE RESTRICT pour `account_id` (un Admin gère manuellement la migration ou la désactivation)

---

## 3. Nouvelle entité — `RefreshToken`

Table : `refresh_tokens`

| Champ | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | Identifiant interne |
| `jti` | VARCHAR(64) | UNIQUE, NOT NULL | JWT Identifier (claim `jti` du JWT refresh) |
| `user_id` | UUID | NOT NULL, FK → `users.id` ON DELETE CASCADE | Utilisateur émetteur |
| `issued_at` | TIMESTAMPTZ | NOT NULL, server_default `now()` | Date d'émission |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Date d'expiration (issued_at + 30 j) |
| `revoked_at` | TIMESTAMPTZ | NULL | Date de révocation (NULL si actif) |
| `replaced_by_jti` | VARCHAR(64) | NULL | JTI du successeur en cas de rotation (ou NULL si logout direct) |
| `created_at` | TIMESTAMPTZ | NOT NULL, server_default `now()` | Audit |

**Indexes** :
- `idx_refresh_tokens_jti` UNIQUE sur `jti`
- `idx_refresh_tokens_user_id` sur `user_id` (lookup rapide pour logout)
- `idx_refresh_tokens_active` sur `(user_id, revoked_at) WHERE revoked_at IS NULL` (index partiel)

**Lifecycle** :
- `issued` (revoked_at = NULL, replaced_by_jti = NULL) → état initial à l'émission
- `rotated` (revoked_at = T, replaced_by_jti = jti2) → après rotation par `/auth/refresh`
- `logged_out` (revoked_at = T, replaced_by_jti = NULL) → après `/auth/logout`
- `expired` : implicite si `expires_at < now()`

**Garbage collection** : un job hors-scope F02 (post-MVP) supprimera les `refresh_tokens` dont `expires_at < now() - 30 days`.

---

## 4. Nouvelle entité — `AccountInvitation`

Table : `account_invitations`

| Champ | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | Identifiant interne |
| `account_id` | UUID | NOT NULL, FK → `accounts.id` ON DELETE CASCADE | `Account` cible |
| `email` | VARCHAR(255) | NOT NULL | Email destinataire |
| `token_hash` | VARCHAR(255) | NOT NULL | Hash bcrypt du token clair (token clair envoyé par email, jamais stocké) |
| `token_lookup` | VARCHAR(64) | NOT NULL, INDEXED | SHA256 hex du token clair (lookup rapide, déterministe) — utilisé pour retrouver l'invitation correspondante avant la vérification bcrypt |
| `invited_by_user_id` | UUID | NOT NULL, FK → `users.id` ON DELETE SET NULL | Utilisateur émetteur de l'invitation |
| `status` | ENUM(`'pending'`, `'accepted'`, `'expired'`, `'revoked'`) | NOT NULL, DEFAULT `'pending'` | État de l'invitation (Postgres ENUM type `invitation_status`) |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Date d'expiration (issued_at + INVITE_TOKEN_TTL_DAYS jours, défaut 7) |
| `accepted_at` | TIMESTAMPTZ | NULL | Date d'acceptation |
| `accepted_by_user_id` | UUID | NULL, FK → `users.id` ON DELETE SET NULL | Utilisateur créé par l'acceptation |
| `created_at` | TIMESTAMPTZ | NOT NULL, server_default `now()` | Audit |
| `updated_at` | TIMESTAMPTZ | NOT NULL, server_default `now()`, ON UPDATE `now()` | Audit |

**Indexes** :
- `idx_invitations_account_id` sur `account_id`
- `idx_invitations_email_status` sur `(email, status)` (lookup pour éviter doublons pending)
- `idx_invitations_status_expires_at` sur `(status, expires_at)` (purge des expirés)
- `idx_invitations_token_lookup` UNIQUE sur `token_lookup` (lookup rapide à l'acceptation d'une invitation)

**Lifecycle / state machine** :
```
pending --(accept via /register?invite=<token>)--> accepted
pending --(expires_at < now())--> expired
pending --(DELETE /api/account/users/<inv_id>)--> revoked
```

Une fois `accepted`, `revoked`, ou `expired`, le token n'est plus utilisable.

---

## 5. Modifications — Tables métier (14 tables)

Pour chacune des 14 tables ci-dessous, ajout de la colonne :

| Champ | Type | Contraintes |
|---|---|---|
| `account_id` | UUID | NOT NULL après backfill, FK → `accounts.id` ON DELETE RESTRICT |

**Tables affectées** :

| # | Table | Particularité |
|---|---|---|
| 1 | `company_profiles` | UNIQUE sur `account_id` (1:1 avec `Account` — FR-007a) ; profils dupliqués au backfill marqués `archived = true` ou supprimés selon stratégie validée à l'implémentation |
| 2 | `documents` | Standard (FK + index) |
| 3 | `esg_assessments` | Standard |
| 4 | `carbon_assessments` | Standard |
| 5 | `credit_scores` | Standard |
| 6 | `fund_matches` | Standard |
| 7 | `fund_applications` | Standard |
| 8 | `action_plans` | Standard |
| 9 | `action_items` | Standard (peut hériter via `action_plans.account_id` mais on duplique pour RLS direct) |
| 10 | `reminders` | Standard |
| 11 | `conversations` | Standard |
| 12 | `messages` | Standard (peut hériter via `conversations.account_id`, dupliqué pour RLS direct) |
| 13 | `interactive_questions` | Standard |
| 14 | `tool_call_logs` | Standard |
| 15 | `reports` | Standard |

(Note : 14 tables annoncées dans la fiche, mais 15 tables physiques recensées car `action_items` et `reminders` sont distinguées de `action_plans`. Le décompte exact sera tranché en phase B selon l'inspection des modèles existants ; le critère reste : toute table métier user-owned reçoit `account_id`.)

**Indexes** : `idx_<table>_account_id` sur `account_id` pour chaque table (utile pour les requêtes Admin qui filtrent par account, et pour aider le planificateur PostgreSQL avec les RLS policies).

**RLS policies appliquées** sur chaque table :

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account ON <table>
  FOR ALL
  USING (account_id = current_setting('app.current_account_id', true)::uuid)
  WITH CHECK (account_id = current_setting('app.current_account_id', true)::uuid);

CREATE POLICY admin_full_access ON <table>
  FOR ALL
  USING (current_setting('app.current_role', true) = 'ADMIN')
  WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');
```

**Note CHECK constraint** : aucune table n'a de contrainte `account_id = users.account_id WHERE users.id = user_id` (au niveau SQL pur, ce serait via trigger). On s'appuie sur la cohérence applicative + RLS pour éviter cette dérive : les services backend utilisent toujours `account_id` du contexte authentifié pour les writes.

---

## 6. Diagramme texte des relations

```
                   accounts
                   ├── id (PK)
                   ├── name
                   ├── is_active
                   └── ...
                       │
                       │ 1
                       │
       ┌───────────────┼─────────────────┬────────────────┐
       │ N             │ 1               │ 1              │ N
       │               │                 │                │
       ▼               ▼                 ▼                ▼
    users        company_profiles    account_invitations  <14 tables métier>
    ├── id (PK)  ├── id (PK)         ├── id (PK)          ├── id (PK)
    ├── email    ├── account_id (FK  ├── account_id (FK)  ├── account_id (FK)
    ├── role        UNIQUE)          ├── token_hash       ├── user_id (existing)
    ├── account_id (FK NULL)         ├── status            └── ...
    └── ...      └── ...             └── ...
       │
       │ 1
       │
       ▼ N
    refresh_tokens
    ├── id (PK)
    ├── jti (UNIQUE)
    ├── user_id (FK)
    ├── revoked_at
    ├── replaced_by_jti
    └── ...
```

---

## 7. Validation rules (côté Pydantic v2)

| Schéma | Règle |
|---|---|
| `RegisterRequest` | Si query string contient `invite_token`, alors le serveur lookup l'invitation, valide expiration et statut `pending`, et lie `account_id` du user créé à `invitation.account_id`. Sinon, crée un nouvel `Account`. |
| `InvitationCreate` | `email` validé par `EmailStr` Pydantic ; vérifier qu'aucune invitation `pending` n'existe déjà pour cet email + account_id. |
| `LogoutRequest` | Aucun body requis ; révocation de tous les `refresh_tokens` du `current_user`. |
| `RefreshRequest` | `refresh_token` (str) requis ; serveur valide signature, vérifie `revoked_at`, applique fenêtre grâce 5 s. |

---

## 8. Backfill : ordre topologique

```
1. CREATE TABLE accounts
2. CREATE TABLE refresh_tokens
3. CREATE TABLE account_invitations
4. CREATE TYPE user_role AS ENUM ('PME', 'ADMIN')
5. CREATE TYPE invitation_status AS ENUM ('pending', 'accepted', 'expired', 'revoked')
6. ALTER TABLE users ADD COLUMN role user_role NOT NULL DEFAULT 'PME'
7. ALTER TABLE users ADD COLUMN account_id UUID NULL  -- nullable temporairement
8. -- Backfill users.account_id :
   INSERT INTO accounts (id, name, is_active, created_at)
     SELECT gen_random_uuid(), company_name, TRUE, NOW()
     FROM users
     WHERE company_name IS NOT NULL AND company_name <> ''
     GROUP BY company_name;
9. UPDATE users SET account_id = (SELECT id FROM accounts WHERE accounts.name = users.company_name) WHERE company_name IS NOT NULL AND company_name <> '';
10. -- Cas anomalie : users sans company_name
    INSERT INTO accounts (name) VALUES ('default') ON CONFLICT DO NOTHING;
    UPDATE users SET account_id = (SELECT id FROM accounts WHERE name = 'default') WHERE account_id IS NULL;
    -- Logger les anomalies via NOTICE
11. ALTER TABLE users ADD CONSTRAINT users_role_account_consistency CHECK (...)
12. -- Pour chaque table métier (14 tables) :
    ALTER TABLE <table> ADD COLUMN account_id UUID NULL;
    UPDATE <table> SET account_id = (SELECT account_id FROM users WHERE users.id = <table>.user_id);
    ALTER TABLE <table> ALTER COLUMN account_id SET NOT NULL;
    ALTER TABLE <table> ADD CONSTRAINT fk_<table>_account FOREIGN KEY (account_id) REFERENCES accounts(id);
    CREATE INDEX idx_<table>_account_id ON <table>(account_id);
13. -- Cas particulier : company_profiles → 1:1 avec Account
    -- Détecter doublons :
    -- Pour chaque account_id avec > 1 company_profile, marquer les plus anciens archived = true
    ALTER TABLE company_profiles ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE;
    -- Conserver le plus récent par account, archiver les autres :
    UPDATE company_profiles SET archived = TRUE WHERE id IN (
      SELECT id FROM company_profiles cp1
      WHERE EXISTS (
        SELECT 1 FROM company_profiles cp2
        WHERE cp2.account_id = cp1.account_id AND cp2.created_at > cp1.created_at
      )
    );
    -- Contrainte d'unicité partielle (uniquement sur les non-archivés) :
    CREATE UNIQUE INDEX uq_company_profiles_account_active ON company_profiles(account_id) WHERE archived = FALSE;
14. -- Activation RLS :
    -- Pour chaque table métier :
    ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
    CREATE POLICY pme_access_own_account ON <table> ...;
    CREATE POLICY admin_full_access ON <table> ...;
```

---

## 9. Downgrade (dans la migration Alembic)

Ordre inverse :
1. DROP POLICY sur chaque table.
2. ALTER TABLE ... DISABLE ROW LEVEL SECURITY.
3. DROP INDEX sur `account_id` colonnes.
4. ALTER TABLE ... DROP COLUMN `account_id`.
5. DROP CONSTRAINT users_role_account_consistency.
6. ALTER TABLE users DROP COLUMN account_id, role.
7. DROP TABLE refresh_tokens, account_invitations, accounts.
8. DROP TYPE user_role, invitation_status.

⚠️ **Attention** : la downgrade perd les `Account`, les `RefreshToken`, et les invitations. Documenté dans le fichier de migration.
