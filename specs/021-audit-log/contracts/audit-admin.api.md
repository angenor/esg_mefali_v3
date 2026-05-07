# API Contract — F03 Admin endpoints

Routeur : `app/modules/audit/router.py` (sub-router `/admin/audit` monté sous `/api/admin`).
Auth : toutes les routes requièrent `Depends(get_current_admin)` (rôle `ADMIN`).
RLS : `app.current_role = 'ADMIN'` → policy `admin_full_access` autorise la lecture inter-comptes.

## `GET /api/admin/audit/{account_id}`

### Description

Retourne les événements d'audit d'un compte PME spécifique (admin uniquement).

**Effet de bord important** : cet appel déclenche `record_admin_view(admin, account_id, request_context)` au début du handler, qui insère une ligne `audit_log` `action=view_admin, source_of_change=admin, entity_type=account, entity_id=<account_id>, account_id=<account_id>, user_id=<admin_id>`. Cette trace est visible côté PME via `/historique`.

L'enregistrement est idempotent par requête (cache `request.state.audit_view_recorded`).

### Path params

| Paramètre | Type | Description |
|---|---|---|
| `account_id` | UUID | Identifiant du compte PME à consulter |

### Query params

Tous ceux de `GET /api/audit/me` (entity_type, entity_id, action, source_of_change, since, until, page, limit, order).

### Réponse 200

Identique à `GET /api/audit/me` (même schéma `AuditEventList`).

### Erreurs

| Code | Cas | Body |
|---|---|---|
| `401` | Non authentifié | `{"detail": "Token d'authentification manquant"}` |
| `403` | Authentifié mais pas Admin | `{"detail": "Accès réservé aux administrateurs"}` |
| `404` | `account_id` inconnu | `{"detail": "Compte introuvable"}` |

### Exemple `curl`

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/admin/audit/00000000-0000-0000-0000-000000000020?since=2026-05-01"
```

---

## `GET /api/admin/audit`

### Description

Retourne le log d'audit global (tous comptes confondus), filtrable par compte, utilisateur, entité, source. Admin uniquement. **Aucun `record_admin_view` n'est créé** (pas de cible PME unique sur cet endpoint).

### Query params

Tous ceux de `GET /api/audit/me` + :

| Paramètre | Type | Optional | Description |
|---|---|---|---|
| `account_id` | UUID | yes | Filtrer sur un compte spécifique |
| `user_id` | UUID | yes | Filtrer sur un acteur spécifique |

### Réponse 200

Identique à `GET /api/audit/me` (même schéma `AuditEventList`).

### Erreurs

| Code | Cas | Body |
|---|---|---|
| `401` | Non authentifié | idem |
| `403` | Authentifié mais pas Admin | idem |

### Exemple `curl`

```bash
# Tous les events de la dernière heure
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/admin/audit?since=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"

# Tous les events d'un user particulier
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/admin/audit?user_id=00000000-0000-0000-0000-000000000010"
```

---

## Middleware `AdminAuditContextMiddleware`

### Description

Monté sur le routeur `/api/admin/*` ; positionne la ContextVar `current_source_of_change="admin"` au début du traitement de chaque requête admin (avant les Depends), puis reset à la fin.

### Implémentation (résumé)

```text
class AdminAuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/admin/"):
            with source_of_change_scope("admin"):
                return await call_next(request)
        return await call_next(request)
```

Effet : toute mutation faite par un admin sur un endpoint `/api/admin/*` qui passe par un service `Auditable` produit `source_of_change=admin` automatiquement. Les endpoints PME standard restent en `manual`.

---

## Visibilité côté PME (rappel)

Lorsque l'admin appelle `GET /api/admin/audit/{account_id}` :

1. Backend insère `audit_log(action=view_admin, source_of_change=admin, entity_type=account, entity_id=<account_id>, account_id=<account_id>, user_id=<admin_id>, actor_metadata={endpoint, request_id, ip_address, user_agent})`.
2. RLS : la ligne a `account_id=<pme_account_id>`, donc la policy PME `pme_access_own_account` la rend visible à l'utilisateur PME.
3. Frontend PME `/historique` affiche l'entrée via `AuditLogEntry.vue` : « Un admin Mefali a consulté votre compte — il y a X minutes ».

Ce comportement garantit la transparence d'accès admin (engagement de confiance).
