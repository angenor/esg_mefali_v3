# Authentification, multi-tenant et RLS — F02

> Référence opérationnelle : modèle de menaces, architecture RLS PostgreSQL,
> rotation refresh token, ajout de tables métier multi-tenant, seed Admin,
> troubleshooting.

## 1. Modèle de menaces

### Acteurs

| Acteur | Position | Privilèges |
|--------|----------|------------|
| Utilisateur PME | externe authentifié | accès aux seules données de **son Account** |
| Admin plateforme | externe authentifié | accès **transverse** (gestion catalogue, sources, comptes PME) |
| Attaquant externe | non authentifié | aucun accès aux endpoints protégés |
| Attaquant interne (compte compromis) | authentifié sur PME-A | NE DOIT JAMAIS lire / écrire les données de PME-B |

### Vecteurs

1. **Bug applicatif** : un service oublie de filtrer par `account_id` →
   fuite croisée entre PMEs.
2. **Replay refresh token** : un token capté est réutilisé pour générer
   indéfiniment de nouveaux access tokens.
3. **Privilege escalation** : un utilisateur PME tente d'accéder à un
   endpoint Admin (`/api/admin/*`).
4. **Whitelist email** : ancien anti-pattern où l'autorisation était basée
   sur l'email plutôt que sur un rôle persistant en BDD.
5. **Compte désactivé** : un Account banni continue à émettre des requêtes
   valides via JWT non encore expiré.

### Mitigations

| Vecteur | Mitigation F02 |
|--------|---------------|
| Bug applicatif | **Row-Level Security (RLS) ENABLE+FORCE** sur 14 tables métier |
| Replay refresh token | **Rotation systématique** + fenêtre de grâce 5 s + révocation `replaced_by_jti` |
| Privilege escalation | dépendance **`get_current_admin`** + middleware Nuxt `admin.ts` |
| Whitelist email | suppression complète (`backend/app/modules/financing/router.py` ne contient plus `admin@esg-mefali.com`) |
| Compte désactivé | login + refresh vérifient `accounts.is_active` ; révocation des refresh tokens à la désactivation |

## 2. Architecture RLS

### Principe

PostgreSQL applique des **policies SQL** au niveau de chaque ligne, dépendantes
d'une variable de session. Notre implémentation utilise :

- `SET LOCAL app.current_account_id = '<uuid>'` — propage l'Account courant
- `SET LOCAL app.current_role = 'PME' | 'ADMIN'` — distingue le scope
- `SET LOCAL app.current_user_id = '<uuid>'` — pour les self-access Admin

### Activation

```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;

CREATE POLICY pme_access_own_account ON conversations
  FOR ALL
  USING (account_id::text = current_setting('app.current_account_id', true))
  WITH CHECK (account_id::text = current_setting('app.current_account_id', true));

CREATE POLICY admin_full_access ON conversations
  FOR ALL
  USING (current_setting('app.current_role', true) = 'ADMIN');
```

`FORCE ROW LEVEL SECURITY` est crucial : sans lui, le superuser PostgreSQL
contournerait les policies.

### Fail-closed

Si `app.current_account_id` n'est jamais SET (ex : une route oublie d'appeler
`get_current_user` qui appelle `set_rls_context`), `current_setting('app.current_account_id', true)`
retourne `''`, qui ne matche aucun `account_id` → **0 ligne retournée**, write
échoue avec `WITH CHECK violation`.

### Helper `set_rls_context`

```python
# app/core/rls_session.py
async def set_rls_context(
    session: AsyncSession,
    account_id: uuid.UUID | None,
    role: str,
    user_id: uuid.UUID,
) -> None:
    """Propage le contexte RLS sur la session SQL en cours."""
    await session.execute(text("SELECT set_config('app.current_account_id', :v, true)"),
        {"v": str(account_id) if account_id else ""})
    await session.execute(text("SELECT set_config('app.current_role', :v, true)"),
        {"v": role})
    await session.execute(text("SELECT set_config('app.current_user_id', :v, true)"),
        {"v": str(user_id)})
```

Câblé dans `app/api/deps.py::get_current_user` — toute route protégée par
`Depends(get_current_user)` bénéficie automatiquement du RLS.

## 3. Rotation refresh token

### Algorithme

```
1. Login → access_token (24 h) + refresh_token RT1 (jti=A, exp=30 j)
2. POST /auth/refresh { refresh_token: RT1 } à T0
   → marque RT1 (jti=A) comme revoked, replaced_by_jti=B
   → émet RT2 (jti=B)
3. À T0+3 s, replay RT1 :
   → fenêtre de grâce 5 s active → retourne RT2 (le successeur)
   → log événement `grace_window_reuse`
4. À T0+10 s, replay RT1 :
   → 401 + log événement `refresh_token_replay`
5. POST /auth/logout :
   → revoke_all_refresh_tokens(user_id)
   → 204
```

### Fenêtre de grâce

5 secondes par défaut (`refresh_token_grace_window_seconds`). Permet de
gérer les cas réseau réels où un client envoie 2 refresh quasi-simultanés
(ex : retry après timeout). Configurable via env.

### Logout côté serveur

`POST /api/auth/logout` (Bearer access_token) appelle
`revoke_all_refresh_tokens(user_id)` qui passe `revoked_at = now()` sur
**tous** les refresh tokens actifs du user. Toutes les autres sessions
(autres onglets, autres appareils) recevront 401 au prochain refresh.

## 4. Ajouter une table métier multi-tenant

### Procédure pas-à-pas

1. **Modèle SQLAlchemy** : ajouter `account_id` FK + index :
   ```python
   account_id: Mapped[uuid.UUID | None] = mapped_column(
       UUID(as_uuid=True),
       ForeignKey("accounts.id", ondelete="RESTRICT"),
       nullable=True,  # peut être NOT NULL côté DB via migration
   )
   __table_args__ = (Index("idx_<table>_account_id", "account_id"),)
   ```

2. **Migration Alembic** :
   ```python
   # 1. ADD COLUMN account_id NULL
   op.add_column("<table>", sa.Column("account_id", UUID(...)))
   # 2. Backfill via users
   op.execute("""
       UPDATE <table> t SET account_id = u.account_id
       FROM users u WHERE t.user_id = u.id
   """)
   # 3. ALTER COLUMN NOT NULL + FK
   op.alter_column("<table>", "account_id", nullable=False)
   op.create_foreign_key(...)
   # 4. CREATE INDEX
   op.create_index(...)
   # 5. ENABLE + FORCE RLS + 2 policies
   op.execute("ALTER TABLE <table> ENABLE ROW LEVEL SECURITY")
   op.execute("ALTER TABLE <table> FORCE ROW LEVEL SECURITY")
   op.execute("CREATE POLICY pme_access_own_account ON <table> FOR ALL ...")
   op.execute("CREATE POLICY admin_full_access ON <table> FOR ALL ...")
   ```

3. **Test d'isolation** : ajouter un scénario dans
   `tests/integration/test_rls_metier_tables.py` qui vérifie
   ENABLE+FORCE+2 policies sur la nouvelle table.

4. **CI garde-fou** : le test
   `tests/ci/test_no_metier_table_without_account_id.py` échoue
   automatiquement si une table métier est ajoutée sans suivre cette
   procédure.

## 5. Convention de seed Admin

```bash
cd backend && source venv/bin/activate
python -m app.scripts.seed_admin \
    --email admin@esg-mefali.com \
    --password 'mot-de-passe-ultra-fort' \
    --full-name "Admin Principal"
```

Sortie : un UUID par ligne (pour intégration dans pipelines de seed).

**Important** : aucun endpoint public ne crée d'Admin. La création est
exclusivement CLI (off-server), pour éviter toute escalade depuis le
trafic web.

## 6. Troubleshooting

### Problème : « Je ne vois aucune donnée alors que je suis connecté »

Symptôme : `SELECT * FROM conversations` retourne 0 ligne.

Cause probable : `set_rls_context` n'a pas été appelé sur la session.
Vérifier que `Depends(get_current_user)` est bien sur la route.

```sql
-- Vérifier la valeur courante
SELECT current_setting('app.current_account_id', true);
-- Doit retourner un UUID (et pas '')
```

### Problème : « La migration 019 échoue en downgrade »

Vérifier l'ordre inverse : DROP policies → DISABLE RLS → DROP FK →
DROP INDEX → DROP COLUMN → DROP TABLE → DROP TYPE.

### Problème : « Replay refresh token retourne 401 »

Si le replay se produit dans la fenêtre de grâce (5 s) → comportement
normal, doit retourner le successeur.
Si > 5 s → 401 attendu, log `refresh_token_replay` SecOps signal.

### Problème : « Test legacy échoue avec `users_role_account_consistency` »

Cause : un test legacy crée un User PME sans `account_id`.
Solution : créer d'abord un Account, puis passer son ID :

```python
from app.models.account import Account
account = Account(name="Test")
db_session.add(account)
await db_session.flush()
user = User(..., account_id=account.id)
```

Voir aussi `tests/conftest.py::make_pme_user` pour un helper prêt.

## 7. Références

- Migration source : `backend/alembic/versions/019_multitenant_and_roles.py`
- Tests RLS : `backend/tests/integration/test_rls_isolation.py`
- Seed Admin : `backend/app/scripts/seed_admin.py`
- Helper RLS : `backend/app/core/rls_session.py`
- Refresh service : `backend/app/services/refresh_token_service.py`
- Spec : `specs/019-multitenant-roles-rls/spec.md`
