# F03 — Audit Log Append-Only

## Vue d'ensemble

Toute mutation métier (CompanyProfile, FundApplication, ESGAssessment,
CarbonAssessment, CreditScore, ActionPlan, ActionItem) est tracée
automatiquement dans la table `audit_log` strictement append-only. La trace
contient *qui* a fait *quoi*, *quand*, sur *quelle* entité, avec les
*anciennes* et *nouvelles* valeurs, et la *source* de la mutation
(`manual` / `llm` / `import` / `admin`).

Les administrateurs Mefali qui consultent un compte PME laissent une trace
`view_admin` visible côté PME pour transparence (engagement de confiance).

## Modèle de menaces

| Menace | Vecteur | Mitigation F03 |
|---|---|---|
| Mutation silencieuse non tracée | Tool LangChain qui commit direct | Mixin `Auditable` + listener global `before_flush` capte toute instance attachée à la session |
| Falsification d'une trace | `UPDATE audit_log SET ...` | Trigger `BEFORE UPDATE` `RAISE EXCEPTION` + `REVOKE UPDATE` (best-effort) |
| Effacement d'une trace | `DELETE FROM audit_log` | Trigger `BEFORE DELETE` `RAISE EXCEPTION` + `REVOKE DELETE` (best-effort) |
| Fuite inter-comptes | PME A voit log de PME B | RLS PostgreSQL `pme_access_own_account` (héritée F02) |
| Surveillance admin masquée | Admin lit un compte sans trace | `record_admin_view` automatique + visible côté PME |
| Volume DoS | 100k+ inserts/jour | Indexes ciblés ; pagination 50/page ; partitionnement post-MVP |
| Données personnelles dans le log (RGPD) | `old_value`/`new_value` PII | Limitation MVP documentée ; mécanisme DPO post-MVP |

## Schéma `audit_log`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Identifiant unique |
| `user_id` | `UUID` | FK `users.id` ON DELETE RESTRICT, NOT NULL | Acteur (l'admin pour `view_admin`) |
| `account_id` | `UUID` | FK `accounts.id` ON DELETE RESTRICT, NOT NULL | Compte cible/propriétaire |
| `timestamp` | `timestamptz` | NOT NULL, DEFAULT `now()` | Horodatage |
| `entity_type` | `varchar(64)` | NOT NULL | Ex. `company_profiles`, `account` |
| `entity_id` | `UUID` | NOT NULL | UUID de l'entité affectée |
| `action` | ENUM `audit_action` | NOT NULL | `create` / `update` / `delete` / `view_admin` |
| `field` | `varchar(128)` | NULL admise | NULL pour create/delete/view_admin |
| `old_value` | `JSONB` | NULL admise | Valeur avant (NULL pour create/view_admin) |
| `new_value` | `JSONB` | NULL admise | Valeur après (NULL pour delete/view_admin) |
| `source_of_change` | ENUM `audit_source` | NOT NULL | `manual` / `llm` / `import` / `admin` |
| `actor_metadata` | `JSONB` | NULL admise | `tool_name`, `conversation_id`, `request_id`, `ip_address`, `user_agent`, `endpoint` |

### ENUMs PostgreSQL

```sql
CREATE TYPE audit_action AS ENUM ('create', 'update', 'delete', 'view_admin');
CREATE TYPE audit_source AS ENUM ('manual', 'llm', 'import', 'admin');
```

### Triggers append-only

```sql
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_update();
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION raise_audit_log_no_delete();
```

Les fonctions PL/pgSQL exécutent `RAISE EXCEPTION 'audit_log is append-only ; UPDATE/DELETE is forbidden'`.

### Permissions (best-effort)

```sql
DO $$ BEGIN
    BEGIN
        REVOKE UPDATE, DELETE ON audit_log FROM CURRENT_USER;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'REVOKE UPDATE, DELETE failed (rôle superuser/owner) : %. Trigger remains effective.', SQLERRM;
    END;
END $$;
```

Si le rôle applicatif est superuser/owner, le `REVOKE` est no-op
(PostgreSQL ne peut pas restreindre un superuser). Le trigger reste la
défense effective. La séparation de rôle est documentée comme évolution
post-MVP.

### RLS (héritée F02)

```sql
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY pme_access_own_account ON audit_log FOR SELECT
    USING (account_id = current_setting('app.current_account_id', true)::uuid);
CREATE POLICY pme_insert_own_account ON audit_log FOR INSERT
    WITH CHECK (account_id = current_setting('app.current_account_id', true)::uuid);
CREATE POLICY admin_full_access ON audit_log FOR SELECT
    USING (current_setting('app.current_role', true) = 'ADMIN');
CREATE POLICY admin_insert_anywhere ON audit_log FOR INSERT
    WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');
```

Aucune policy `UPDATE/DELETE` n'existe — triggers + REVOKE prévalent.

### Indexes

- `idx_audit_log_account_timestamp` ON `(account_id, timestamp DESC)` — scrolling chronologique
- `idx_audit_log_account_entity` ON `(account_id, entity_type, entity_id)` — historique d'une entité
- `idx_audit_log_user_timestamp` ON `(user_id, timestamp DESC)` — audit par acteur
- `idx_audit_log_source_timestamp` ON `(source_of_change, timestamp DESC)` — métriques admin

## Requêtes SQL communes

### Reconstituer l'historique d'une candidature

```sql
SELECT timestamp, action, field, old_value, new_value, source_of_change, actor_metadata
FROM audit_log
WHERE entity_type = 'fund_applications'
  AND entity_id = '<application_uuid>'
ORDER BY timestamp ASC;
```

### Tous les events d'un user

```sql
SELECT * FROM audit_log
WHERE user_id = '<user_uuid>'
ORDER BY timestamp DESC
LIMIT 100;
```

### Toutes les consultations admin sur un compte

```sql
SELECT timestamp, user_id, actor_metadata
FROM audit_log
WHERE entity_type = 'account'
  AND action = 'view_admin'
  AND account_id = '<pme_account_uuid>'
ORDER BY timestamp DESC;
```

### Détecter une rafale de mutations LLM (anomalie)

```sql
SELECT date_trunc('minute', timestamp) AS minute, COUNT(*)
FROM audit_log
WHERE source_of_change = 'llm'
  AND timestamp > now() - interval '1 hour'
GROUP BY 1
HAVING COUNT(*) > 50
ORDER BY 1 DESC;
```

## Format export CSV / JSON

### CSV

- Encodage : UTF-8 BOM (préfixe `\xef\xbb\xbf`) — lisibilité Excel native
- Colonnes (ordre stable) : `id, timestamp, user_email, user_id, account_id,
  entity_type, entity_id, action, field, old_value, new_value, source_of_change,
  actor_metadata`
- Valeurs `dict`/`list` sérialisées en JSON inline
- Filename : `audit-log-<account_id>-<YYYYMMDD>.csv`

### JSON

- Tableau JSON streaming (pas de wrapper)
- Mêmes champs que `AuditEvent` (Pydantic)
- Filename : `audit-log-<account_id>-<YYYYMMDD>.json`

## Limites MVP

- **RGPD vs append-only** : conflit reconnu. La suppression formelle (Art. 17)
  n'est pas implémentée en MVP. Une documentation séparée et un mécanisme
  DPO (anonymisation tombstone + hash) sont prévus post-MVP.
- **Pas de hashing chaîné Merkle** : pas de preuve d'intégrité forte ; le
  trigger + REVOKE protège déjà l'invariant. Évolution post-MVP.
- **Pas de PDF signé Ed25519** : F08 fournira la signature ; F03 sera
  référencé dans les rapports.
- **Pas de partitionnement** : les indexes ciblés suffisent jusqu'à
  100k+ lignes par compte. Évolution post-MVP si volumétrie >> 1M lignes.
- **Pas de rôle PostgreSQL séparé** : le rôle applicatif est typiquement
  superuser/owner, donc `REVOKE` est no-op. Le trigger reste la défense
  effective. La séparation de rôle (post-MVP) permettra un REVOKE effectif
  et une RLS PME testable.
- **CarbonEmissionEntry et CreditDataPoint** : non auditables individuellement
  (pas d'`account_id` propre). Leurs mutations sont tracées via le snapshot
  JSONB du parent (`CarbonAssessment`, `CreditScore`).
- **ESGCriterionScore** : pas de table dédiée en MVP (les scores vivent dans
  `ESGAssessment.assessment_data`). Évolution éventuelle post-MVP avec table
  dédiée.

## Procédure pour rendre auditable un nouveau modèle

1. Importer le marqueur dans le fichier modèle :
   ```python
   from app.core.auditable import Auditable
   ```

2. Faire hériter la classe :
   ```python
   class MaNouvelleEntite(Auditable, UUIDMixin, TimestampMixin, Base):
       ...
       account_id: Mapped[uuid.UUID | None] = mapped_column(
           UUID(as_uuid=True),
           ForeignKey("accounts.id", ondelete="RESTRICT"),
           nullable=True,
       )
   ```

3. Ajouter le nom à `AUDITABLE_MODELS` dans `app/core/auditable.py` :
   ```python
   AUDITABLE_MODELS: frozenset[str] = frozenset({
       ...,
       "MaNouvelleEntite",
   })
   ```

4. Le test CI `test_auditable_models_whitelist_complete` validera la
   présence du modèle dans `AUDITABLE_MODELS` ou dans `EXEMPT_MODELS`.

5. Si le modèle est un détail interne (pas d'`account_id` propre), l'ajouter
   à `EXEMPT_MODELS` avec une justification commentée :
   ```python
   EXEMPT_MODELS: frozenset[str] = frozenset({
       ...,
       # MaNouvelleEntite : détail interne d'un parent X, audit via le parent.
       "MaNouvelleEntite",
   })
   ```

## ContextVar `source_of_change`

Toute mutation est étiquetée par la valeur courante de la `ContextVar`
Python `current_source_of_change` :

| Source | Positionnée par | Utilisation |
|---|---|---|
| `manual` | défaut (API REST PME) | endpoints `/api/companies/me`, `/api/esg/*`, etc. |
| `llm` | décorateur `@_with_llm_source` sur les 9 nœuds LangGraph | tools LangChain qui mutent (`update_company_profile`, `create_fund_application`, ...) |
| `admin` | middleware `AdminAuditContextMiddleware` sur `/api/admin/*` | endpoints admin qui mutent un compte PME |
| `import` | scripts CLI futurs (post-MVP) | imports batch (CSV bulk, etc.) |

Helper recommandé :

```python
from app.core.audit_context import source_of_change_scope

with source_of_change_scope("llm"):
    await service.update_company_profile(...)
```

## Endpoints API

### `GET /api/audit/me`

Liste paginée du log du PME courant.

Query params : `entity_type`, `entity_id`, `action`, `source_of_change`,
`since`, `until`, `page` (défaut 1), `limit` (défaut 50, max 200), `order`
(défaut `desc`).

Réponse : `{"events": [...], "total": N, "page": N, "limit": N}`.

### `GET /api/audit/me/export`

Export CSV (UTF-8 BOM) ou JSON streaming. Query params : tous les filtres ci-dessus + `format=csv|json`.

### `GET /api/admin/audit/{account_id}`

Log d'un compte PME spécifique (admin uniquement). **Effet de bord** :
insère une ligne `view_admin` côté PME (idempotent par requête).

### `GET /api/admin/audit`

Log global filtrable (admin uniquement). Filtres additionnels : `account_id`, `user_id`. Aucun `view_admin` créé.

## Tests CI

| Test | Fichier | Vérification |
|---|---|---|
| `test_audit_context.py` | unit | ContextVar défaut + scope + isolation asyncio |
| `test_audit_truncate.py` | unit | Troncature 10 KB + sérialisation UUID/Decimal/datetime/Enum |
| `test_models_audit_log.py` | unit | Modèle SQLAlchemy AuditLog (FK NOT NULL, JSON arbitraire) |
| `test_auditable_mixin.py` | unit | Listener before_flush (create/update/delete, anti-récursion, rollback) |
| `test_audit_csv_writer.py` | unit | CSV BOM UTF-8, accents français, virgules embedded |
| `test_audit_endpoints.py` | integration | 4 endpoints PME/admin (filtres, pagination, export) |
| `test_audit_source_of_change.py` | integration | source `manual`/`llm`/`admin` correctement positionnée |
| `test_audit_models_whitelist.py` | integration | Garde-fou CI : tous les modèles métier sont auditable ou exempt |
| `test_alembic_021_upgrade_downgrade.py` | postgres | Migration 021 (ENUMs, table, indexes, triggers, RLS, policies) |
| `test_audit_append_only_trigger.py` | postgres | UPDATE/DELETE échouent + RLS PME (skip si superuser) |
| `frontend/tests/audit/AuditLogEntry.test.ts` | vitest | Rendu lignes en français + dark mode |
| `frontend/tests/audit/useAuditLog.test.ts` | vitest | Composable fetchMe / fetchByAccount / exports |
| `frontend/tests/audit/AuditFilters.test.ts` | vitest | Sélecteurs + emit update + reset |
| `frontend/tests/e2e/F03-audit-log.spec.ts` | playwright | 4 scénarios E2E (manual, llm, view_admin, export CSV) |

## Liste des tools LangChain à migrer (audit en cours)

Ce projet utilise des tools LangChain qui peuvent muter directement la base
sans passer par le service métier. Le mixin global `before_flush` capture
néanmoins ces mutations (tant que la session est utilisée). La migration vers
les services métier (post-MVP) renforcera la traçabilité (validation,
ContextVar admin, etc.).

À auditer :

- `app/graph/tools/profiling_tools.py` : `update_company_profile`
- `app/graph/tools/esg_tools.py` : `save_esg_score`, `batch_save_esg_criteria`
- `app/graph/tools/application_tools.py` : `create_fund_application`
- `app/graph/tools/carbon_tools.py`, `credit_tools.py`, `action_plan_tools.py`,
  `financing_tools.py`

Couverte par le décorateur `@_with_llm_source` sur les 9 nœuds LangGraph
(setSource = `llm` au début du nœud, reset en fin).
