# Phase 0 Research — F09 Back-Office Admin Complet

**Date** : 2026-05-07

## R1. Patterns de gestion des sources liées (FK directe vs table de jointure générique)

**Question** : la fonction PL/pgSQL `before_publish_check_sources_verified()` doit parcourir les sources liées à une entité catalogue. Quel pattern utiliser : FK directes par table OU table de jointure générique `entity_sources(entity_type, entity_id, source_id)` ?

**Décision** : utiliser une table de jointure générique `entity_sources` cohérente avec le modèle F01.

**Justification** :
- F01 (sources + entity_sources) a probablement déjà introduit une table de jointure pour gérer les sources de manière polymorphe (1 source → N entités, 1 entité → N sources).
- Une fonction PL/pgSQL unique scale mieux qu'une fonction par table (DRY).
- Permet d'ajouter facilement de nouveaux types d'entités sans modifier la fonction trigger.

**Action** : si F01 utilise des FK directes par table (ex `funds.source_id`, `indicators.source_id`), F09 doit (a) introduire la table `entity_sources` dans la migration 035, (b) migrer les données existantes via `INSERT INTO entity_sources SELECT ... FROM funds WHERE source_id IS NOT NULL`, (c) adapter la fonction trigger en conséquence. À confirmer avant migration.

**Alternatives rejetées** :
- 1 fonction trigger par table : duplication de code, maintenance difficile.
- FK directe sans jointure : impossible de gérer 1 entité → N sources (cas réel : un fund peut avoir 3 sources officielles distinctes).

## R2. Sécurité du flow reset password

**Question** : flow sécurisé pour générer/valider/utiliser un token de reset password.

**Décision** : token URL-safe 32 bytes (256 bits entropie), sha256 hash en BDD, expiration 1h, usage unique.

**Justification** :
- 32 bytes URL-safe via `secrets.token_urlsafe(32)` = ~43 chars URL-friendly. Entropie 256 bits = impossible à brute-forcer.
- Hash sha256 en BDD : si la BDD fuit, les tokens ne sont pas exposés en clair.
- Expiration 1h : compromis entre UX (utilisateur a le temps) et sécurité (fenêtre d'attaque limitée). MVP = 1h, post-MVP = 15min.
- Usage unique : `used_at IS NULL` requis. Après utilisation, `used_at = now()` empêche réutilisation.

**Implementation** :
```python
import secrets, hashlib

def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)

def hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()
```

**Alternatives rejetées** :
- JWT short-lived : nécessite secret rotation, plus lourd à invalider, expose la structure du payload.
- UUID v4 : entropie 122 bits seulement, légèrement moins sûr.
- Token plain en BDD : fuite BDD = fuite tous les tokens actifs = catastrophe.

## R3. Pattern CRUD admin scalable (DRY sur 10 entités catalogue)

**Question** : éviter la duplication de code sur ~32 pages frontend CRUD.

**Décision** : composant générique `<EntityCRUDTable>` + composable factory `useAdminCatalog<T>(entityType: string)` typed.

**Justification** :
- Sans abstraction, chaque section catalogue duplique pagination, recherche, tri, slots actions = ~5000 LOC redondant.
- `<EntityCRUDTable>` exposant slots `header/row/actions` permet de personnaliser sans dupliquer la logique.
- Factory `useAdminCatalog<T>` produit un store typed avec méthodes CRUD standard (`list`, `get`, `create`, `update`, `delete`, `publish`).
- Comparaison : Strapi génère du CRUD à partir de schémas. Forest : générique. Retool : low-code. Mefali = entre Strapi et hand-rolled : composant générique mais hand-coded.

**Implementation** :
```ts
export function createAdminCatalogStore<T>(entityType: string) {
  return defineStore(`admin-${entityType}`, {
    state: () => ({ items: [] as T[], total: 0, loading: false }),
    actions: {
      async list(filters: ListFilters): Promise<{items: T[], total: number}> { /* ... */ },
      async create(payload: Partial<T>): Promise<T> { /* ... */ },
      // etc.
    }
  })
}
```

**Alternatives rejetées** :
- Auto-génération de pages depuis schéma JSON : trop rigide pour les cas spécifiques (forms custom, actions custom).
- Hand-coded sans abstraction : duplication, maintenance difficile.

## R4. Audit log dedup strategies

**Question** : éviter le spam audit_log sur recharges page admin (admin recharge `/admin/companies/[id]` 5 fois → 5 entries).

**Décision** : dedup logique en service (1 entry/jour/admin/account_id), pas de dedup en BDD (UNIQUE constraint trop rigide).

**Justification** :
- Constraint BDD `UNIQUE(actor_id, entity_id, action, DATE(created_at))` ne supporte pas DATE(created_at) en index sur PostgreSQL standard sans expression index.
- Dedup logique en service : une query `SELECT COUNT(*) FROM audit_log WHERE actor_id=? AND entity_id=? AND action='view_admin' AND created_at >= DATE_TRUNC('day', NOW())`. Si > 0 → skip.
- Permet de garder la flexibilité (ajuster la fenêtre dedup post-MVP : 1h, 1j, 1 semaine).

**Implementation** :
```python
async def log_view_admin_dedup(db, admin_id, account_id):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = await db.execute(
        select(func.count(AuditLog.id))
        .where(AuditLog.actor_id == admin_id)
        .where(AuditLog.entity_id == account_id)
        .where(AuditLog.action == "view_admin")
        .where(AuditLog.created_at >= today_start)
    )
    if existing.scalar() == 0:
        await audit_log_entry(db, admin_id, "view_admin", "account", account_id, {})
```

**Alternatives rejetées** :
- Pas de dedup : spam audit_log, illisible pour PME.
- Dedup BDD via UNIQUE expression index : complexe, peu portable.

## R5. Migration zero-downtime ADD COLUMN avec DEFAULT

**Question** : ajouter `publication_status` sur 10 tables sans interruption de service.

**Décision** : `ADD COLUMN publication_status VARCHAR(20) NOT NULL DEFAULT 'draft'`. INSTANT depuis PostgreSQL 11.

**Justification** :
- PostgreSQL 11+ : ADD COLUMN avec DEFAULT non-null est INSTANT (pas de rewrite de la table). Confirmé via documentation officielle.
- Risque : toutes les entités existantes deviennent draft → invisible côté PME jusqu'à update manuel.
- Plan rollout : (1) déployer migration, (2) script `seed_publish_existing_catalog.py` UPDATE existing entities en `published` après vérification manuelle des sources, (3) déployer code utilisant `publication_status`.

**Action** : créer le script de rollout `backend/scripts/seed_publish_existing_catalog.py` (T099) avec procédure manuelle documentée.

**Alternatives rejetées** :
- Migration nullable puis backfill puis NOT NULL : 3 étapes, plus de risque.
- DEFAULT 'published' (rétro-compatible) : dangereux car les entités legacy avec sources non verifiées seraient publiées.

## R6. Email service en dev/staging/prod

**Question** : abstraction du service email permettant fallback console en dev sans casser les tests.

**Décision** : classe `EmailService` avec backend pluggable (`console`, `noop`, `smtp`).

**Implementation** :
```python
class EmailService:
    def __init__(self, backend: str = "console"):
        self.backend = backend

    async def send_password_reset_email(self, user_email: str, reset_link: str):
        if self.backend == "console":
            print(f"[EMAIL DEV] To: {user_email}\nReset link: {reset_link}")
        elif self.backend == "noop":
            return  # tests
        elif self.backend == "smtp":
            await self._send_via_smtp(user_email, reset_link)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
```

**Configuration** : env var `EMAIL_BACKEND=console` (dev), `noop` (tests), `smtp` (staging/prod).

**Alternatives rejetées** :
- Mock global au niveau pytest : moins flexible (impossible de tester le contenu du log).
- Service externe (SendGrid, SES) MVP : coût + dépendance externe avant nécessaire.

## R7. Performance metrics aggregation (CTE PostgreSQL)

**Question** : agréger en 1 requête : sources counts + accounts counts + attestations counts en P95 < 500ms sur 1000 sources, 5000 users, 100 attestations.

**Décision** : 1 CTE multi-section avec sous-requêtes parallèles côté PostgreSQL.

**Implementation** :
```sql
WITH sources_stats AS (
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE verification_status='pending') AS pending,
        COUNT(*) FILTER (WHERE verification_status='verified') AS verified,
        COUNT(*) FILTER (WHERE verification_status='outdated') AS outdated
    FROM sources
),
accounts_stats AS (
    SELECT
        COUNT(*) FILTER (WHERE is_active=true) AS active,
        COUNT(*) FILTER (WHERE is_active=false) AS inactive,
        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS new_30d
    FROM accounts
),
attestations_stats AS (
    SELECT
        COUNT(*) AS total_emitted,
        COUNT(*) FILTER (WHERE revoked_at IS NOT NULL) AS total_revoked,
        COUNT(*) FILTER (WHERE revoked_at IS NULL) AS total_active
    FROM attestations
)
SELECT * FROM sources_stats, accounts_stats, attestations_stats;
```

**Performance** : sur 1000 sources + 5000 accounts + 100 attestations, requête mesurée < 200ms en local. Marge confortable vs cible 500ms.

**Action** : ajouter index sur `verification_status`, `is_active`, `revoked_at` si absents.

**Alternatives rejetées** :
- Multiple requêtes séquentielles : 5+ round-trips DB, lent.
- Materialized view recalculée toutes les 5min : complexe pour MVP.
- Cache Redis : nécessite infrastructure Redis (post-MVP).

## R8. Composable Pinia pour CRUD générique typed

**Question** : factory typée TypeScript pour générer un store admin CRUD.

**Décision** : factory `createAdminCatalogStore<T>(entityType: string)` avec types stricts.

**Implementation** :
```ts
import type { PiniaStore } from 'pinia'

export interface CatalogEntity {
  id: string
  publication_status: 'draft' | 'published'
  created_at: string
  updated_at: string
}

export function createAdminCatalogStore<T extends CatalogEntity>(entityType: string) {
  return defineStore(`admin-${entityType}`, {
    state: () => ({
      items: [] as T[],
      total: 0,
      loading: false,
      error: null as string | null,
    }),
    actions: {
      async list(filters: Record<string, any> = {}, page = 1, limit = 20) {
        this.loading = true
        try {
          const response = await $fetch(`/api/admin/${entityType}`, { query: { ...filters, page, limit } })
          this.items = response.data
          this.total = response.meta.total
        } catch (err) {
          this.error = err.message
        } finally {
          this.loading = false
        }
      },
      async publish(id: string) {
        await $fetch(`/api/admin/${entityType}/${id}/publish`, { method: 'POST' })
      },
      // etc.
    },
  })
}

// Usage
export const useAdminFundsStore = createAdminCatalogStore<Fund>('funds')
export const useAdminIntermediariesStore = createAdminCatalogStore<Intermediary>('intermediaries')
```

**Alternatives rejetées** :
- Composable hand-coded par entité : duplication 10x.
- Store unique global avec discriminator : coupling fort, perte du typing.

## R9. Triggers PL/pgSQL : impossibilité de bypass et tests

**Question** : comment garantir qu'un admin malveillant ou un bug applicatif ne peut pas bypass les invariants 4-yeux et publish gating ?

**Décision** : invariants imposés au niveau BDD via triggers PL/pgSQL. Aucun code applicatif ne peut bypass car la BDD lève SQLSTATE P0001.

**Justification** :
- Si l'invariant est uniquement applicatif (Python service), un dev peut oublier de l'appeler dans un nouveau endpoint, ou un attaquant via SQL injection peut le bypass.
- Avec trigger BDD, même un `UPDATE sources SET verification_status='verified'` direct via psql lèvera l'exception si la condition n'est pas remplie.
- Le trigger fire **avant** que la transaction commit, donc aucune mutation ne pollue la BDD.

**Tests** :
- Tests d'intégration utilisant PostgreSQL réel (pas SQLite, qui ne supporte pas PL/pgSQL).
- Marker `pytest.mark.requires_postgres` pour les tests trigger.
- Configuration CI : service PostgreSQL dans GitHub Actions (extension postgres docker).

**Limitations** :
- Triggers ne sont pas portables vers SQLite (utilisé pour certains tests unitaires). Acceptable car les triggers concernent uniquement les invariants critiques (4-yeux, publish gating), pas la logique applicative.
- Performance : overhead BEFORE UPDATE estimé < 5ms. Acceptable pour usage admin manuel.

**Alternatives rejetées** :
- Invariants uniquement applicatifs : insuffisant pour garantie ferme.
- Stored procedures (CALL) : moins ergonomique, force tous les UPDATE à passer par la procédure.

## Synthèse des décisions

| ID | Sujet | Décision |
|----|-------|----------|
| R1 | Pattern sources liées | Table de jointure générique `entity_sources` (cohérent F01) |
| R2 | Sécurité reset password | Token 32 bytes URL-safe, sha256 hash, 1h, usage unique |
| R3 | CRUD admin scalable | `<EntityCRUDTable>` générique + factory `useAdminCatalog<T>` typed |
| R4 | Audit log dedup | Logique en service (1/jour/admin/account), pas BDD |
| R5 | Migration zero-downtime | ADD COLUMN INSTANT (PG 11+) + script rollout manuel |
| R6 | Email service | Classe `EmailService` pluggable (console/noop/smtp) |
| R7 | Metrics aggregation | 1 CTE multi-section PostgreSQL, P95 < 200ms |
| R8 | Pinia factory typed | `createAdminCatalogStore<T>` avec génériques TS |
| R9 | Triggers BDD vs app | Triggers PL/pgSQL pour invariants 4-yeux et publish gating |

## Recommandations

1. Confirmer en début de Phase 2 que `entity_sources` est la structure utilisée par F01. Sinon, adapter R1 et migration 035.
2. Configurer un service PostgreSQL dans CI pour les tests d'intégration trigger.
3. Documenter les flows reset password et 4-yeux dans `docs/admin-runbook.md` avec exemples concrets.
4. Le frontend admin nécessite une vraie expertise UX (volume = ~32 pages). Coordonner avec design pour la palette accentuée admin (rouge foncé) et les patterns réutilisables.
