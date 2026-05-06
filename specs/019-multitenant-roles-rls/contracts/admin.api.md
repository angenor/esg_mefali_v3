# Contracts — Admin (F02 squelette pour F09)

Module `app/modules/admin/` exposant le squelette du back-office. F02 livre uniquement le routeur protégé + un endpoint de health-check. F09 (Back-Office Admin) peuplera le routeur avec les CRUD catalogue.

---

## GET /api/admin/health

**Description** : Health-check du back-office Admin. Retourne 200 si le caller est Admin, 403 sinon. Utilisé par le frontend pour valider que l'utilisateur a bien accès aux pages `/admin/*`.

**Method** : GET
**Path** : `/api/admin/health`
**Auth** : Bearer access_token (rôle `ADMIN` uniquement)

### Response 200

```json
{
  "status": "ok",
  "role": "ADMIN",
  "service": "admin"
}
```

### Response 403

```json
{ "detail": "Accès réservé aux administrateurs" }
```

**Comportement** :
1. Le routeur est monté avec `Depends(get_current_admin)` (dépendance globale du module).
2. `get_current_admin` lève `HTTPException(403)` si `current_user.role != 'ADMIN'`.
3. L'endpoint retourne simplement `{ status, role, service }` si tout est OK.

---

## Dépendance `get_current_admin`

```python
async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Lève HTTPException(403) si l'utilisateur n'est pas Admin."""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user
```

À utiliser sur tous les endpoints réservés aux Admin Mefali. Premier consommateur en F02 : suppression de la whitelist email dans `backend/app/modules/financing/router.py:118`, qui devient :

```python
@router.post("/funds", response_model=FundResponse, status_code=201)
async def create_fund_endpoint(
    body: FundCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),  # remplace la whitelist email
) -> FundResponse:
    ...
```

---

## Frontend — Routes admin protégées

Le frontend consomme `/api/admin/health` pour vérifier que le rôle Admin est valide avant d'afficher les pages `/admin/*`. Le middleware `admin.ts` (Nuxt) appelle cet endpoint au load et redirige vers `/dashboard` en cas de 403.

```typescript
// frontend/app/middleware/admin.ts
export default defineNuxtRouteMiddleware(async (to) => {
  const { user, isAdmin } = useAuth()
  if (!isAdmin.value) {
    return navigateTo('/dashboard')
  }
  // Optionnel : double-check via /api/admin/health
})
```

---

## Périmètre F02 vs F09

| Endpoint | F02 | F09 |
|---|---|---|
| `GET /api/admin/health` | ✅ | — |
| `GET /api/admin/funds` | — | ✅ |
| `POST /api/admin/funds` | — | ✅ |
| `GET /api/admin/sources` | — | ✅ |
| `GET /api/admin/accounts` (lister PME) | — | ✅ |
| `GET /api/admin/audit-log` | — | ✅ (dépend de F03) |
| ... | — | ✅ |

F02 garantit uniquement que **le squelette protégé existe** ; F09 en ajoutera les routes de gestion catalogue.
