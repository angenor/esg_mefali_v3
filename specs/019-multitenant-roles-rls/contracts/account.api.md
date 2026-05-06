# Contracts — Account (F02 nouveau module)

Module `app/modules/account/` exposant les endpoints d'invitation et de gestion d'équipe PME. Tous les endpoints requièrent `Depends(get_current_user)`.

---

## POST /api/account/invite

**Description** : Invite un nouveau collaborateur à rejoindre l'`Account` de l'utilisateur courant.

**Method** : POST
**Path** : `/api/account/invite`
**Auth** : Bearer access_token (rôle `PME` uniquement, Admin n'invite pas — son `account_id` est NULL)

### Request body

```json
{
  "email": "nouveau.collegue@example.com"
}
```

### Response 201

```json
{
  "id": "uuid",
  "email": "nouveau.collegue@example.com",
  "status": "pending",
  "expires_at": "2026-05-13T10:00:00Z",
  "invited_by": {
    "id": "uuid",
    "full_name": "Jean Dupont"
  },
  "created_at": "2026-05-06T10:00:00Z"
}
```

**Comportement** :
1. Valider que `current_user.role == 'PME'` et `current_user.account_id IS NOT NULL`.
2. Vérifier qu'aucune invitation `pending` non expirée n'existe déjà pour ce couple `(account_id, email)` ; sinon 409.
3. Vérifier qu'aucun utilisateur actif avec cet email n'est déjà rattaché à l'`Account` ; sinon 409.
4. Générer un token clair via `secrets.token_urlsafe(32)`.
5. Hasher le token via bcrypt et stocker dans `account_invitations.token_hash`.
6. Calculer `expires_at = now() + INVITE_TOKEN_TTL_DAYS days` (défaut 7).
7. Insérer la ligne `account_invitations`.
8. Construire l'URL d'invitation : `https://<frontend_url>/register?invite=<token_clair>`.
9. Appeler `email_service.send(to=email, subject=..., body=...)` ; en F02 c'est `LoggingEmailDelivery` qui logge en INFO.
10. Retourner 201 avec la fiche d'invitation.

### Response 409

```json
{ "detail": "Une invitation est déjà en cours pour cet email" }
```

### Response 403

```json
{ "detail": "Seuls les utilisateurs PME peuvent inviter des collaborateurs" }
```

(Cas Admin tentant d'utiliser cet endpoint.)

---

## GET /api/account/users

**Description** : Liste les membres actifs et les invitations en cours de l'`Account` courant.

**Method** : GET
**Path** : `/api/account/users`
**Auth** : Bearer access_token (rôle `PME`)

### Response 200

```json
{
  "members": [
    {
      "id": "uuid",
      "email": "owner@example.com",
      "full_name": "Jean Dupont",
      "role": "PME",
      "is_active": true,
      "joined_at": "2025-12-01T10:00:00Z"
    },
    {
      "id": "uuid",
      "email": "collegue@example.com",
      "full_name": "Marie Martin",
      "role": "PME",
      "is_active": true,
      "joined_at": "2026-04-15T10:00:00Z"
    }
  ],
  "pending_invitations": [
    {
      "id": "uuid",
      "email": "nouveau@example.com",
      "status": "pending",
      "expires_at": "2026-05-13T10:00:00Z",
      "invited_by": { "id": "uuid", "full_name": "Jean Dupont" },
      "created_at": "2026-05-06T10:00:00Z"
    }
  ]
}
```

**Comportement** :
1. Lookup tous les `users` avec `account_id = current_user.account_id` ET `is_active = true`.
2. Lookup toutes les `account_invitations` avec `account_id = current_user.account_id` ET `status = 'pending'` ET `expires_at > now()`.
3. Retourner la liste consolidée.

### Response 403 (Admin)

```json
{ "detail": "Cet endpoint est réservé aux utilisateurs PME" }
```

---

## DELETE /api/account/users/{user_id}

**Description** : Retire un collaborateur de l'`Account` (ou révoque une invitation pending si l'`id` correspond à une invitation).

**Method** : DELETE
**Path** : `/api/account/users/{user_id}`
**Auth** : Bearer access_token (rôle `PME`)

### Path params

- `user_id` : UUID du `User` à retirer OU UUID d'une `AccountInvitation` à révoquer.

### Response 204

Pas de contenu.

**Comportement** :
1. Si `user_id` correspond à un `User` actif du même `Account` :
   - Vérifier qu'il reste au moins un autre user actif dans l'`Account` ; sinon 409.
   - Marquer `users.is_active = false` (soft delete).
   - Révoquer tous ses `refresh_tokens` (`UPDATE ... SET revoked_at = now() WHERE user_id = ... AND revoked_at IS NULL`).
2. Sinon, si `user_id` correspond à une `AccountInvitation` `pending` du même `Account` :
   - Marquer `status = 'revoked'`.
3. Sinon : 404.

### Response 404

```json
{ "detail": "Utilisateur ou invitation introuvable" }
```

### Response 409

```json
{ "detail": "Impossible de retirer le dernier membre actif du compte" }
```

---

## POST /api/account/accept-invitation (utilisé indirectement par /register)

**Description** : Endpoint interne, appelé par le flux register quand `?invite=<token>` est présent. Pas exposé directement aux clients (le frontend utilise `/auth/register` qui orchestre).

**Comportement combiné** (dans `/auth/register` étendu) :
1. Si query string ou body contient `invite_token`, lookup `account_invitations` :
   - Hasher le token reçu, comparer aux `token_hash` dans la table (on parcourt les invitations pending non expirées de la même journée pour optimiser ; ou alternative : stocker un `token_hint = <8 premiers chars>` indexé).
   - Variante simplifiée : stocker le token clair haché identifiable via une colonne `token_lookup = SHA256(token).hex()` indexée, et faire le lookup direct.
2. Si invitation valide (`status='pending'`, `expires_at > now()`) :
   - Créer le user avec `account_id = invitation.account_id`, `role = 'PME'`.
   - Marquer invitation : `status = 'accepted'`, `accepted_at = now()`, `accepted_by_user_id = <new_user.id>`.
3. Sinon : 400 `Invitation invalide ou expirée`.
4. Si pas d'`invite_token`, créer un nouvel `Account` et y rattacher le user (flow standard).

---

## Comportement RLS

Toutes les lectures (`GET /api/account/users`) sont protégées par RLS : impossible de lister les users d'un autre `Account` même via injection SQL ou bug de service. La policy `pme_access_own_account` sur `users` (à étendre dans F02) filtre par `account_id`.

⚠️ La table `users` reçoit une RLS spéciale : un user PME voit uniquement les users de son propre `Account`, un Admin voit tous les users. Variante de la policy générique :

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account_users ON users
  FOR ALL
  USING (
    account_id = current_setting('app.current_account_id', true)::uuid
    OR id = current_setting('app.current_user_id', true)::uuid  -- soi-même même si Admin sans account
  )
  WITH CHECK (
    account_id = current_setting('app.current_account_id', true)::uuid
  );

CREATE POLICY admin_full_access_users ON users
  FOR ALL
  USING (current_setting('app.current_role', true) = 'ADMIN')
  WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');
```

(L'inclusion d'`app.current_user_id` permet à un Admin de toujours voir sa propre ligne malgré son `account_id = NULL`.)
