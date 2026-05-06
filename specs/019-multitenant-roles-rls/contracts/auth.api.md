# Contracts — Auth (F02 extension)

Les endpoints `/auth/*` existants sont étendus avec rotation refresh, logout, et persistance des refresh tokens.

---

## POST /auth/login

**Description** : Authentifie un utilisateur. Émet un access token JWT et un refresh token persisté en BDD.

**Method** : POST
**Path** : `/auth/login`
**Auth** : aucune

### Request body

```json
{
  "email": "user@example.com",
  "password": "******"
}
```

### Response 200

```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

- `access_token` : JWT signé HS256, claim `sub = user.id`, `exp = now + 1440 min`, `type = 'access'`.
- `refresh_token` : JWT signé HS256, claim `sub = user.id`, claim `jti = <uuid>`, `exp = now + 30 days`, `type = 'refresh'`. Insère une ligne dans `refresh_tokens(jti, user_id, issued_at, expires_at)`.

### Response 401

```json
{ "detail": "Identifiants invalides" }
```

### Response 403 (NEW)

```json
{ "detail": "Ce compte est temporairement désactivé" }
```

Si `accounts.is_active = false` pour le compte de l'utilisateur.

---

## POST /auth/refresh

**Description** : Rafraîchit l'access token. **Comportement étendu en F02 : rotation du refresh token avec fenêtre de grâce 5 s.**

**Method** : POST
**Path** : `/auth/refresh`
**Auth** : refresh_token dans le body

### Request body

```json
{ "refresh_token": "eyJhbGc..." }
```

### Response 200

```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Comportement détaillé** :
1. Décoder le `refresh_token` et extraire `jti`, `sub`.
2. Lookup `refresh_tokens` par `jti` :
   - **Si introuvable** : 401 `Refresh token invalide`.
   - **Si `expires_at < now()`** : 401 `Refresh token expiré`.
   - **Si `revoked_at = NULL`** (cas standard) :
     - Émettre un nouveau JTI2.
     - Mettre à jour la ligne courante : `revoked_at = now()`, `replaced_by_jti = JTI2`.
     - Insérer une nouvelle ligne pour JTI2.
     - Retourner `access_token` + `refresh_token` (nouveau).
   - **Si `revoked_at IS NOT NULL` ET `now() - revoked_at <= 5s` ET `replaced_by_jti IS NOT NULL`** (fenêtre de grâce) :
     - Lookup le successeur `replaced_by_jti`.
     - Réémettre le même `refresh_token` (le successeur déjà émis).
     - Logger un événement `grace_window_reuse` avec le `user_id` et l'instant.
     - Retourner `access_token` + `refresh_token` (le successeur).
   - **Sinon** (révoqué hors fenêtre de grâce) : 401 `Refresh token déjà utilisé`. Logger un événement `refresh_token_replay`.

### Response 401

```json
{ "detail": "Refresh token invalide ou expiré" }
```

### Response 403 (NEW)

```json
{ "detail": "Ce compte est temporairement désactivé" }
```

---

## POST /auth/logout (NEW)

**Description** : Révoque tous les refresh tokens actifs de l'utilisateur courant.

**Method** : POST
**Path** : `/auth/logout`
**Auth** : Bearer access_token

### Request body : aucun

### Response 204

Pas de contenu.

**Comportement** :
1. Récupérer `current_user` via `Depends(get_current_user)`.
2. `UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = current_user.id AND revoked_at IS NULL`.
3. Retourner 204.

### Response 401

```json
{ "detail": "Token d'authentification manquant" }
```

---

## GET /auth/me (existant, étendu)

**Description** : Retourne le profil de l'utilisateur connecté, étendu avec `role` et `account`.

**Method** : GET
**Path** : `/auth/me`
**Auth** : Bearer access_token

### Response 200 (étendu)

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jean Dupont",
  "company_name": "Acme SARL",
  "role": "PME",
  "account": {
    "id": "uuid",
    "name": "Acme SARL",
    "is_active": true,
    "plan": "free"
  },
  "is_active": true,
  "created_at": "2026-01-01T10:00:00Z"
}
```

Pour un Admin, `account = null`.

---

## Comportement RLS appliqué

À chaque appel authentifié (passage par `Depends(get_current_user)`) :
1. La transaction SQL est ouverte.
2. `SET LOCAL app.current_account_id = '<user.account_id ou """>'`.
3. `SET LOCAL app.current_role = '<user.role>'`.
4. La requête métier s'exécute → les policies RLS filtrent automatiquement.
5. La transaction commit/rollback.

⚠️ Si `app.current_account_id` n'est pas SET (bug applicatif), les policies retournent 0 ligne (fail-closed). Aucune donnée ne fuite.
