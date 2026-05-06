# Research — F02 Multi-tenant + Roles + RLS

**Feature** : 019-multitenant-roles-rls
**Date** : 2026-05-06

Ce document consolide les décisions techniques prises en Phase 0 du plan F02. Pour chaque décision : ce qui a été choisi, pourquoi, et les alternatives évaluées.

---

## D1 — Stockage des refresh tokens : PostgreSQL vs Redis

**Decision** : Stocker les refresh tokens dans une table PostgreSQL `refresh_tokens` indexée sur `jti`.

**Rationale** :
- Cohérent avec l'invariant projet « Pas de Redis MVP » (`CLAUDE.md` § Workflow → « Synchronisation : Synchrone (Redis + Celery plus tard) »).
- Une table PostgreSQL offre indexation O(log n) sur `jti`, jointure naturelle vers `users`, audit chain via `replaced_by_jti`.
- La fenêtre de grâce 5 s est triviale à implémenter avec une comparaison `revoked_at` + `replaced_by_jti`.
- Auditabilité native : conservation historique des rotations pour 30 jours (purge périodique).

**Alternatives évaluées** :
- **Redis blacklist (set des JTI révoqués)** : rejeté, introduit une dépendance d'infrastructure non nécessaire en MVP.
- **JTI dans un cache in-memory FastAPI** : rejeté, ne survit pas aux redémarrages, pas multi-instance.
- **JWT sans état (pas de table)** : rejeté, ne permet ni rotation ni révocation explicite.

---

## D2 — Mécanisme RLS PostgreSQL

**Decision** : Activer `ENABLE ROW LEVEL SECURITY` ET `FORCE ROW LEVEL SECURITY` sur les 14 tables métier. Deux policies par table :

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

**Rationale** :
- `FORCE ROW LEVEL SECURITY` est crucial : sans lui, le propriétaire d'une table (le rôle PostgreSQL utilisé par l'app pour les migrations Alembic) bypasse les policies. Avec `FORCE`, même le owner est soumis.
- `current_setting('app.current_account_id', true)` retourne `NULL` si la variable n'est pas SET. Le cast `::uuid` sur NULL provoque une erreur ou rend la condition fausse → 0 ligne retournée → fail-closed.
- `WITH CHECK` empêche aussi les INSERT/UPDATE de créer des lignes appartenant à un autre `account_id`.
- 2 policies (PME + Admin) couvrent tous les cas : chacune est OR-évaluée par PostgreSQL ; un user PME ne matche que la première, un Admin matche la seconde.

**Alternatives évaluées** :
- **Application-only filtering (`WHERE account_id = ...` partout)** : rejeté, US1 explicite que l'isolation doit survivre à un bug de service. Le filtrage applicatif seul est cassable.
- **Tenant per schema** (un schema PostgreSQL par PME) : rejeté, ne scale pas (~10k PME = 10k schemas, problèmes de migrations, vues, indexes).
- **Tenant per database** : rejeté pour la même raison + ressources serveur.
- **Vues filtrées** : rejeté, augmente la complexité (vues + triggers pour les writes), équivalent fonctionnellement à RLS mais moins natif.

---

## D3 — Variables de session PostgreSQL et hook applicatif

**Decision** : Utiliser trois GUC (Grand Unified Configuration) PostgreSQL : `app.current_account_id` (UUID en string), `app.current_role` (`'PME'` ou `'ADMIN'`), et `app.current_user_id` (UUID en string — utile pour la policy `users` qui doit autoriser un Admin à voir sa propre ligne malgré son `account_id NULL`). SET via `SET LOCAL` au début de chaque transaction authentifiée par un helper `set_rls_context(session, account_id, role, user_id)` appelé dans la dépendance `get_current_user`.

```python
async def set_rls_context(
    session: AsyncSession,
    account_id: uuid.UUID | None,
    role: str,
    user_id: uuid.UUID,
) -> None:
    # SET LOCAL ne nécessite pas de privilèges spéciaux ; valable pour la transaction courante uniquement
    await session.execute(text("SET LOCAL app.current_account_id = :aid"),
                          {"aid": str(account_id) if account_id else ""})
    await session.execute(text("SET LOCAL app.current_role = :role"),
                          {"role": role})
    await session.execute(text("SET LOCAL app.current_user_id = :uid"),
                          {"uid": str(user_id)})
```

**Rationale** :
- `SET LOCAL` est natif PostgreSQL, ne nécessite aucune extension, n'a aucun impact de performance mesurable.
- Les variables sont scopées à la transaction (rollback automatique en fin), donc pas de fuite de contexte entre requêtes même en cas de pool de connexions.
- L'appel via une dépendance FastAPI (`get_current_user`) garantit l'application avant toute query métier.
- Asyncpg + SQLAlchemy async supportent nativement `SET LOCAL` via `session.execute(text(...))`.

**Alternatives évaluées** :
- **Middleware FastAPI bas-niveau** : rejeté, plus difficile à tester unitairement et la dépendance fait déjà partie du chemin authentifié naturel.
- **Hooks `before_execute` SQLAlchemy** : rejeté, opaque et hors flow standard FastAPI.
- **Connexion dédiée par requête avec rôle PostgreSQL distinct** : rejeté, complexité élevée et besoin d'un pool par tenant.

---

## D4 — Format JTI et claim JWT

**Decision** : Inclure un claim `jti` (UUID v4) dans le JWT refresh, indexé dans `refresh_tokens.jti UNIQUE`.

**Rationale** :
- Standard RFC 7519 (JWT Identifier).
- UUID v4 garantit l'unicité sans coordination (pas de séquence partagée).
- Index unique sur `refresh_tokens.jti` permet O(log n) pour vérifier l'état (`revoked_at`).

**Alternatives évaluées** :
- **JTI = SHA256(token)** : rejeté, redondant (le token JWT est déjà signé).
- **Pas de jti, recherche par token complet** : rejeté, le token en clair ne devrait pas transiter en BDD.

---

## D5 — TTL et hash des tokens d'invitation

**Decision** :
- TTL : 7 jours par défaut, configurable via `INVITE_TOKEN_TTL_DAYS` (env var dans `core/config.py`).
- Hash : bcrypt via `passlib.context.CryptContext` (déjà disponible dans le projet pour les mots de passe).
- Token clair généré par `secrets.token_urlsafe(32)` (256 bits d'entropie), stocké hashé en BDD, transmis dans le lien email.

**Rationale** :
- 7 jours = équilibre standard (assez pour qu'un utilisateur reçoive et accepte l'invitation, pas trop pour limiter une fuite d'email).
- bcrypt protège contre une fuite de la table : un attaquant qui exfiltre `account_invitations` ne peut pas réutiliser les tokens directement.
- `secrets.token_urlsafe(32)` = entropie cryptographiquement forte, URL-safe.

**Alternatives évaluées** :
- **JWT signé en token d'invitation** : rejeté, alourdit le format (longueur URL) et duplique la logique d'expiration.
- **Token non hashé en BDD** : rejeté, faille critique en cas de fuite DB.
- **Argon2 au lieu de bcrypt** : rejeté, ajoute une dépendance ; bcrypt suffit pour ce cas d'usage où le token a une entropie native élevée (256 bits).

---

## D6 — Architecture EmailDeliveryService

**Decision** : Définir un `Protocol` Python `EmailDeliveryService` avec une méthode `async def send(to: str, subject: str, body: str) -> None`. Une seule implémentation en F02 : `LoggingEmailDelivery` qui logge en INFO le contenu de l'email. Future implémentation `SmtpEmailDelivery` (hors F02) sera un swap sans modification d'appelants.

```python
from typing import Protocol

class EmailDeliveryService(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...

class LoggingEmailDelivery:
    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("[EMAIL DELIVERY STUB] to=%s subject=%s body=%s", to, subject, body)
```

**Rationale** :
- Pattern SOLID (Dependency Inversion) sans framework supplémentaire.
- Protocol Python = duck typing structurel = pas de hiérarchie d'héritage à maintenir.
- Le swap `LoggingEmailDelivery` → `SmtpEmailDelivery` se fera par injection FastAPI (`Depends(get_email_service)`).

**Alternatives évaluées** :
- **Abstract Base Class (ABC)** : équivalent fonctionnellement, plus verbeux.
- **Service global module-level** : rejeté, casse la testabilité (impossible de mocker proprement).

---

## D7 — Stratégie backfill `account_id` et migration Alembic

**Decision** : Migration `019_multitenant_and_roles.py` en 3 phases atomiques au sein de la même upgrade :

1. **Création des nouvelles tables** : `accounts`, `refresh_tokens`, `account_invitations`.
2. **Backfill** :
   - Pour chaque `company_name` distinct dans `users`, créer un `Account(name=company_name)`.
   - Lier chaque user à son `Account` (`UPDATE users SET account_id = ...`).
   - Users sans `company_name` → `Account name='default'` créé une fois et lié, anomalie loggée par `op.execute("INSERT INTO ... (level, message) VALUES ('WARNING', '...')")` ou simple `RAISE NOTICE`.
   - Pour chaque table métier (14 au total), `ALTER TABLE ADD COLUMN account_id UUID NULL`, puis `UPDATE <table> SET account_id = (SELECT account_id FROM users WHERE users.id = <table>.user_id)`, puis `ALTER COLUMN account_id SET NOT NULL`.
   - Pour `company_profiles` : si plusieurs profils par account après backfill, conserver le plus récent (`created_at MAX`) et marquer les autres `archived = true`.
3. **Activation RLS** : pour chaque table métier, `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, et `CREATE POLICY` (2 policies par table).

**Rationale** :
- Atomicité dans une seule migration = rollback complet si quoi que ce soit échoue.
- L'ordre (création → backfill → contrainte NOT NULL → RLS) garantit qu'aucune donnée n'est perdue.
- La downgrade inverse l'ordre (DROP POLICY → DISABLE RLS → DROP COLUMN account_id → DROP TABLES).

**Alternatives évaluées** :
- **3 migrations séparées** : rejeté, multiplie les fenêtres d'incohérence (ex : tables avec `account_id NULL` en prod entre deux deploys).
- **Backfill via script externe** : rejeté, fragile et hors workflow CI Alembic standard.
- **Rendre `account_id` nullable en permanence** : rejeté, contredit US1 (isolation stricte) et complique les RLS policies (`COALESCE`).

---

## D8 — Numérotation Alembic

**Decision** : `019_multitenant_and_roles.py` (head courant = `018_create_interactive_questions`).

**Rationale** :
- La numérotation séquentielle locale (sans timestamp) est la convention en place (`backend/alembic/versions/` montre `001_create_users.py` à `018_create_interactive_questions.py`).
- L'orchestrateur sérialise les migrations Alembic ; le numéro `019` est verrouillé pour F02.
- Si un conflit numérotation survient (autre feature en flight verrouille `019`), l'orchestrateur signalera `zone_conflict` et la phase B renumérotera selon les directives de l'orchestrateur.

**Alternatives évaluées** :
- **Timestamp prefix Alembic** : rejeté, casse la convention historique du projet.

---

## D9 — Frontend : style admin différencié

**Decision** : Layout `admin.vue` utilise des classes Tailwind directes :
- Sidebar : `bg-red-700 text-red-50 dark:bg-red-900 dark:text-red-50`
- Header : `bg-red-50 dark:bg-red-950` avec un badge `<RoleBadge :role="user.role" />` en pin top-right.
- Accent buttons : `bg-red-600 hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600`.

**Rationale** :
- Pas de modification de la palette TailwindCSS globale → pas d'impact sur les autres pages.
- `red-700` se distingue clairement du thème PME existant (vert/bleu sur green-XXX et primary).
- Mode sombre couvert par les variantes `dark:` (invariant 8 du CLAUDE.md).

**Alternatives évaluées** :
- **Modifier `tailwind.config.ts` pour ajouter une palette `admin.*`** : reporté à F09 si nécessaire ; en F02 on évite les modifications de zones interdites (`tailwind.config.ts` est partagé).
- **Couleur orange (`orange-600`) au lieu de rouge** : ouvert au design ; le spec laisse « rouge OU orange ». Choix retenu : rouge `red-700` car contraste plus net avec le vert dominant du thème PME.

---

## D10 — Composable `useAuth` et store `auth.ts`

**Decision** : Le store Pinia `stores/auth.ts` ajoute deux propriétés au state : `account: AccountSummary | null` et `role: 'PME' | 'ADMIN' | null`. Le composable `useAuth.ts` expose `isAdmin: ComputedRef<boolean>` calculé sur le store.

**Rationale** :
- Pattern existant dans le projet (Pinia + composable wrapper).
- `isAdmin` calculé évite de stocker un bool dérivé.
- `AccountSummary` (interface TypeScript) reflète les champs envoyés par `/auth/me` étendu.

**Alternatives évaluées** :
- **Stocker `isAdmin` directement** : rejeté, dérivable du rôle.
- **Provide/Inject Vue** : rejeté, casse la testabilité Pinia.

---

## D11 — Test E2E Playwright : structure et fixtures

**Decision** : Un fichier unique `frontend/tests/e2e/F02-multitenant-roles-rls.spec.ts` avec 4 scénarios principaux (un par US). Fixtures :
- `createPmeAccount(name)` : helper qui appelle `/auth/register` et retourne `{ user, accessToken }`.
- `createAdminAccount(name)` : helper qui crée un Admin via un endpoint dev-only ou via SQL direct (selon ce qui est disponible).
- `loginAs(page, credentials)` : helper qui passe par `/login` UI.

**Rationale** :
- Un seul fichier = facile à exécuter (`npx playwright test tests/e2e/F02-multitenant-roles-rls.spec.ts`).
- Fixtures réutilisables réduisent la duplication.
- Pattern conforme à la skill `e2e-testing` (Page Object Model léger + fixtures).

**Alternatives évaluées** :
- **Plusieurs fichiers (1 par US)** : rejeté pour la complexité du setup, et car les invariants chiffrent à 1 fichier par feature.

---

## Récapitulatif

11 décisions documentées, toutes alignées avec :
- Les invariants ESG Mefali (multi-tenant strict, simplicité MVP, dark mode, FR avec accents).
- La stack imposée (PostgreSQL 16, asyncpg, FastAPI, Alembic, Pydantic v2, Nuxt 4, TailwindCSS 4, Playwright).
- Le critère « plus simple, plus testable ».

Aucun NEEDS CLARIFICATION ne reste ouvert. Le plan peut passer à la Phase 1 (data-model + contracts).
