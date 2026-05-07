# Implementation Plan: F03 — Audit Log Append-Only

**Branch**: `feat/F03-audit-log` (folder `specs/021-audit-log/`) | **Date**: 2026-05-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-audit-log/spec.md`

## Summary

Introduire une table `audit_log` strictement append-only (triggers PostgreSQL `BEFORE UPDATE/DELETE` qui `RAISE EXCEPTION` + `REVOKE UPDATE, DELETE` sur le rôle applicatif) qui trace toute mutation métier sur 9 entités auditables (`CompanyProfile`, `FundApplication`, `ESGAssessment`, `ESGCriterionScore`, `CarbonAssessment`, `CarbonEmissionEntry`, `CreditScore`, `ActionPlan`, `ActionItem`). La capture est automatique via un mixin SQLAlchemy `Auditable` couplé à un listener global `event.listens_for(Session, 'before_flush')` qui parcourt `session.new/dirty/deleted`, calcule un diff field-level borné à 10 KB par valeur, et insère N lignes `audit_log` (une par champ muté) dans la même transaction. La source du changement (`manual` / `llm` / `import` / `admin`) est portée par une `ContextVar` Python positionnée par les nœuds LangGraph (`set('llm')` au démarrage) et un middleware admin (`set('admin')` sur `/api/admin/*`). Un service `AuditService.record_admin_view()` est appelé automatiquement par les endpoints admin qui consultent un compte PME, traçant l'action `view_admin` visible côté PME pour transparence. Côté API : 2 endpoints PME (`GET /api/audit/me`, `GET /api/audit/me/export`) et 2 endpoints admin (`GET /api/admin/audit/{account_id}`, `GET /api/admin/audit`). Côté frontend : page `/historique` (timeline + filtres + pagination + export CSV/JSON UTF-8 BOM), pages `/admin/audit` et `/admin/audit/:accountId`, composants `AuditLogEntry`, `AuditExportButton`, `AuditFilters`, composable `useAuditLog`, store Pinia `audit`. F03 hérite intégralement de F02 (RLS, `account_id`, `get_current_admin`, ContextVars PostgreSQL).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)

**Primary Dependencies**:
- Backend : FastAPI, SQLAlchemy async (`asyncpg`), Alembic, Pydantic v2, événements SQLAlchemy `before_flush` (déjà disponibles), `csv` (stdlib), `json` (stdlib)
- Frontend : Nuxt 4, Vue 3 Composition API, Pinia, TailwindCSS 4, Chart.js (déjà présent — non requis pour F03)
- Tests : pytest + pytest-asyncio + pytest-cov (backend), Vitest + @vue/test-utils + happy-dom (frontend), Playwright (E2E)

**Storage**: PostgreSQL 16 + pgvector (existant). Nouvelle table : `audit_log` avec triggers `BEFORE UPDATE/DELETE` (PL/pgSQL) qui `RAISE EXCEPTION`. RLS PostgreSQL `ENABLE` + `FORCE` cohérente avec F02 (policies `pme_access_own_account` et `admin_full_access`, mais sans `UPDATE/DELETE`). Permission DB : `REVOKE UPDATE, DELETE ON audit_log FROM <role>` (avec avertissement si rôle superuser/owner). Indexes : 4 indexes spécifiés dans la spec FR-004.

**Testing**: pytest (`backend/tests/test_audit_*.py`), Vitest (`frontend/tests/unit/audit/*.spec.ts`), Playwright (`frontend/tests/e2e/F03-audit-log.spec.ts`). Cible couverture ≥ 85 %.

**Target Platform**: Linux server (Docker Compose en local), navigateurs modernes côté frontend (Chromium/Firefox/Safari récents).

**Project Type**: Web application multi-tenant — backend FastAPI séparé du frontend Nuxt. F03 est une feature d'infrastructure transversale qui touche les 9 modèles métier et les 9 nœuds LangGraph.

**Performance Goals**:
- Pas de dégradation > 5 ms par mutation sur les 5 endpoints les plus chauds qui touchent un modèle auditable (chat, dashboard mutations, applications create, esg score update, profile update), mesuré par benchmark CI avant/après mixin.
- `GET /api/audit/me?page=1&limit=50` répond en moins de 500 ms P95 sur un compte avec 100 000 lignes `audit_log` (mesure CI).
- Insertion d'une ligne `audit_log` dans la même transaction que la mutation (ACID, pas de queue async en MVP).
- Export CSV de 100 000 lignes en streaming (`StreamingResponse` FastAPI) sans charger tout en mémoire.

**Constraints**:
- Pas de Redis introduit : tout reste synchrone via PostgreSQL (cohérent F02).
- RLS en mode « fail-closed » : sans `app.current_account_id` SET, requêtes retournent 0 ligne.
- Append-only strict : aucun `UPDATE/DELETE` par le rôle applicatif (trigger + REVOKE).
- Diff field-level avec troncature 10 KB par valeur (marqueur `_truncated`).
- ContextVar Python pour `source_of_change` — propagation explicite, pas d'introspection automatique.
- Aucun secret hardcodé ; toutes les configs via `core/config.py` (env vars).
- Mode sombre obligatoire sur tout nouveau composant frontend (variantes `dark:` Tailwind).
- Aucune mutation du catalogue (Source, EmissionFactor, etc.) — seulement les modèles métier listés dans `AUDITABLE_MODELS`.
- Format CSV : UTF-8 BOM (compatibilité Excel) + en-têtes lisibles français/anglais.

**Scale/Scope**:
- 1 nouvelle table métier (`audit_log`) avec triggers + RLS.
- 1 migration Alembic (`021_create_audit_log.py`) avec `down_revision = '020_sources'`.
- 1 nouveau modèle SQLAlchemy (`app/models/audit_log.py`).
- 1 mixin SQLAlchemy (`app/core/auditable.py`) + 1 module ContextVar (`app/core/audit_context.py`).
- 1 nouveau module (`app/modules/audit/` avec `service.py`, `router.py`, `schemas.py`).
- ~9 modèles existants modifiés pour appliquer le mixin `Auditable` (changement non-disruptif : ajout d'une classe parente).
- ~9 nœuds LangGraph modifiés pour `set_source_of_change("llm")` (1 ligne par nœud, dans un `try/finally` ou context manager).
- 1 middleware FastAPI `AdminAuditContextMiddleware` monté sur `/api/admin/*`.
- 4 endpoints API (`GET /api/audit/me`, `GET /api/audit/me/export`, `GET /api/admin/audit/{account_id}`, `GET /api/admin/audit`).
- 1 page Nuxt PME (`pages/historique.vue`), 2 pages Nuxt admin (`pages/admin/audit/index.vue`, `pages/admin/audit/[accountId].vue`).
- 4 composants Vue (`AuditLogEntry`, `AuditExportButton`, `AuditFilters`, `AuditTimeline`).
- 1 composable (`composables/useAuditLog.ts`), 1 store Pinia (`stores/audit.ts`).
- 1 doc (`docs/audit-log.md`).
- 1 fichier test E2E (`frontend/tests/e2e/F03-audit-log.spec.ts`).
- ~30+ tests backend unit/intégration (capture mutations, append-only triggers, RLS, source_of_change, view_admin, troncature, performance, whitelist `AUDITABLE_MODELS`).
- ~10+ tests frontend (Vitest) sur composants et composable.

## Constitution Check

*GATE: doit passer avant Phase 0 research. Re-check après Phase 1 design.*

Évaluation par principe (constitution v1.0.0) :

| Principe | Évaluation | Justification |
|---|---|---|
| I. Francophone-First | PASS | Toutes les UI strings (`/historique`, page admin, libellés AuditLogEntry « Création », « Modification », « Consultation Admin »), messages d'erreur, doc `docs/audit-log.md` en français avec accents (é, è, ç, à, ù). Code en anglais, commentaires/docstrings en français. |
| II. Architecture Modulaire | PASS | Module `app/modules/audit/` créé en isolation. Mixin `Auditable` dans `app/core/auditable.py` est transversal mais reste un mécanisme infrastructure (event listener) sans dépendance fonctionnelle. |
| III. Conversation-Driven UX | PASS (non-bloquant) | F03 est une feature d'infrastructure ; aucun impact négatif sur la conversation. Les nœuds LangGraph ajoutent 2 lignes (`set` + `reset` dans un context manager) avant chaque service. La page `/historique` est secondaire (consultation, pas conversation). |
| IV. Test-First (NON-NÉGOCIABLE) | PASS | tasks.md spécifie tests AVANT implémentation. Couverture cible ≥ 85 %. Tests : unitaires (mixin, ContextVar, troncature, export CSV/JSON), intégration (capture mutations, triggers append-only, RLS isolation, source_of_change, view_admin), E2E (Playwright avec 4 scénarios). |
| V. Sécurité & Données | PASS (renforcé) | F03 EST une feature de sécurité défensive : append-only triggers + permission DB stricte, RLS, traçabilité view_admin pour transparence. Aucun secret hardcodé. SQLAlchemy parameterized queries. Aucun bypass possible (mixin global). |
| VI. Inclusivité & Accessibilité | PASS | Messages clairs en français (« Vous avez modifié votre profil », « Un admin Mefali a consulté votre compte »). Page `/historique` accessible (timeline sémantique, filtres clavier, pagination ARIA), dark mode obligatoire. Pas d'emoji obligatoire (CLAUDE.md respecté ; libellés textuels possibles). |
| VII. Simplicité & YAGNI | PASS | Pas de Merkle tree (post-MVP). Pas de PDF signé (post-MVP). Pas de diff visuel side-by-side (post-MVP). Pas de partitionnement (post-MVP). ContextVar Python plutôt qu'AsyncLocal/AsyncContext (Python 3.12 natif). |

**Verdict** : PASS sur tous les principes. Aucune dérogation à justifier.

## Project Structure

### Documentation (this feature)

```text
specs/021-audit-log/
├── plan.md                       # Ce fichier (/speckit.plan output)
├── spec.md                       # Spec clarifiée (/speckit.specify + /speckit.clarify output)
├── research.md                   # Phase 0 output
├── data-model.md                 # Phase 1 output
├── quickstart.md                 # Phase 1 output
├── contracts/                    # Phase 1 output
│   ├── audit-pme.api.md          # GET /api/audit/me, GET /api/audit/me/export
│   └── audit-admin.api.md        # GET /api/admin/audit/{account_id}, GET /api/admin/audit
├── checklists/
│   └── requirements.md           # Spec quality checklist
└── tasks.md                      # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 021_create_audit_log.py            # NOUVEAU — migration unique F03 (down_revision='020_sources')
├── app/
│   ├── core/
│   │   ├── auditable.py                        # NOUVEAU : mixin Auditable + listener before_flush + AUDITABLE_MODELS + EXEMPT_MODELS + helper truncate_value
│   │   └── audit_context.py                    # NOUVEAU : ContextVar current_source_of_change + helpers set_source_of_change / source_of_change_scope
│   ├── api/
│   │   └── deps.py                             # MODIFIÉ : ajouter get_audit_admin_view_dep (Depends pour endpoints admin sensibles, factorise record_admin_view)
│   ├── models/
│   │   ├── audit_log.py                        # NOUVEAU : modèle SQLAlchemy AuditLog + ENUMs AuditAction, AuditSourceOfChange
│   │   ├── company.py                          # MODIFIÉ : class CompanyProfile(Auditable, UUIDMixin, TimestampMixin, Base)
│   │   ├── application.py                      # MODIFIÉ : class FundApplication(Auditable, ...)
│   │   ├── esg.py                              # MODIFIÉ : ESGAssessment, ESGCriterionScore appliquent Auditable
│   │   ├── carbon.py                           # MODIFIÉ : CarbonAssessment, CarbonEmissionEntry appliquent Auditable
│   │   ├── credit.py                           # MODIFIÉ : CreditScore applique Auditable
│   │   └── action_plan.py                      # MODIFIÉ : ActionPlan, ActionItem appliquent Auditable
│   ├── modules/
│   │   ├── audit/                              # NOUVEAU
│   │   │   ├── __init__.py
│   │   │   ├── router.py                       # NOUVEAU : /api/audit/me, /api/audit/me/export, /api/admin/audit/{account_id}, /api/admin/audit
│   │   │   ├── service.py                      # NOUVEAU : query helpers (list_for_account, list_global, format_for_render), record_admin_view (idempotent par requête), export CSV/JSON
│   │   │   ├── schemas.py                      # NOUVEAU : AuditEvent (Pydantic v2), AuditEventList, AuditFilters, AuditExportFormat enum
│   │   │   └── csv_writer.py                   # NOUVEAU : helper streaming CSV UTF-8 BOM
│   │   └── admin/
│   │       └── middleware.py                   # NOUVEAU (ou MODIFIÉ si déjà existant) : AdminAuditContextMiddleware qui set_source_of_change("admin") sur /api/admin/*
│   ├── graph/
│   │   ├── nodes/
│   │   │   ├── chat_node.py                    # MODIFIÉ : entrer dans context manager source_of_change_scope("llm")
│   │   │   ├── esg_scoring_node.py             # MODIFIÉ
│   │   │   ├── carbon_node.py                  # MODIFIÉ
│   │   │   ├── financing_node.py               # MODIFIÉ
│   │   │   ├── application_node.py             # MODIFIÉ
│   │   │   ├── credit_node.py                  # MODIFIÉ
│   │   │   ├── action_plan_node.py             # MODIFIÉ
│   │   │   ├── document_node.py                # MODIFIÉ
│   │   │   └── profiling_node.py               # MODIFIÉ
│   │   └── tools/                              # MODIFIÉ : audit des tools qui font db.commit() direct → migration vers services métier (cf. research.md)
│   └── main.py                                 # MODIFIÉ : registration du router audit + middleware admin (zone interdite — sérialisé par orchestrateur)
└── tests/
    ├── unit/
    │   ├── test_audit_context.py                # NOUVEAU : ContextVar par défaut, set/reset, scope helper
    │   ├── test_auditable_mixin.py              # NOUVEAU : capture before_flush sur create/update/delete, anti-récursion, diff field-by-field
    │   ├── test_audit_truncate.py               # NOUVEAU : valeur > 10 KB → marqueur _truncated
    │   └── test_audit_csv_writer.py             # NOUVEAU : UTF-8 BOM, accents, streaming
    └── integration/
        ├── test_audit_create_update_delete.py   # NOUVEAU : intégration sur les 9 modèles auditables
        ├── test_audit_append_only_trigger.py    # NOUVEAU : UPDATE/DELETE → ProgrammingError
        ├── test_audit_rls_isolation.py          # NOUVEAU : audit_log A invisible depuis user B
        ├── test_audit_source_of_change.py       # NOUVEAU : manual / llm / admin paramétrés
        ├── test_audit_view_admin.py             # NOUVEAU : appel admin sur compte PME → entrée view_admin
        ├── test_audit_endpoints_pme.py          # NOUVEAU : GET /api/audit/me + filtres + pagination + export
        ├── test_audit_endpoints_admin.py        # NOUVEAU : GET /api/admin/audit/{account_id} + 403 pour PME
        ├── test_audit_models_whitelist.py       # NOUVEAU : test CI vérifiant AUDITABLE_MODELS complet
        └── test_audit_performance.py            # NOUVEAU : benchmark < 5 ms overhead par mutation, < 500 ms P95 sur 100k lignes

frontend/
├── app/
│   ├── pages/
│   │   ├── historique.vue                       # NOUVEAU : page PME timeline + filtres + pagination + export
│   │   └── admin/
│   │       └── audit/
│   │           ├── index.vue                    # NOUVEAU : log global filtrable
│   │           └── [accountId].vue              # NOUVEAU : log d'un compte PME spécifique
│   ├── components/
│   │   └── audit/
│   │       ├── AuditLogEntry.vue                # NOUVEAU : ligne lisible (acteur, action, diff, horodatage relatif)
│   │       ├── AuditTimeline.vue                # NOUVEAU : conteneur timeline verticale + scroll/load-more
│   │       ├── AuditExportButton.vue            # NOUVEAU : bouton CSV/JSON + déclenche download
│   │       └── AuditFilters.vue                 # NOUVEAU : filtres entité/source/période + sync URL query params
│   ├── composables/
│   │   └── useAuditLog.ts                       # NOUVEAU : fetchMe, fetchByAccount (admin), fetchGlobal (admin), exportCsv, exportJson
│   ├── stores/
│   │   └── audit.ts                             # NOUVEAU : Pinia store (events, filters, pagination state, total)
│   └── types/
│       └── audit.ts                             # NOUVEAU : types AuditEvent, AuditAction, AuditSourceOfChange, AuditFilters
└── tests/
    ├── unit/
    │   └── audit/
    │       ├── AuditLogEntry.spec.ts            # NOUVEAU : rendu acteur, action, diff, horodatage
    │       ├── AuditFilters.spec.ts             # NOUVEAU : sync URL query params
    │       └── useAuditLog.spec.ts              # NOUVEAU : fetch, pagination, export
    └── e2e/
        └── F03-audit-log.spec.ts                # NOUVEAU : 4 scénarios Playwright (manual, llm, view_admin, export)

docs/
└── audit-log.md                                 # NOUVEAU : modèle de menaces, schéma, requêtes communes, format export, limites MVP, procédure rendre auditable

CLAUDE.md                                        # MODIFIÉ (zone interdite — sérialisé par orchestrateur) : section "Active Technologies" + entrée "Recent Changes" pour F03
```

**Structure Decision** :
- **Backend** : modèle `audit_log` séparé, mixin et ContextVar dans `core/`, module `audit/` avec router/service/schemas/csv_writer ; les 9 modèles métier reçoivent uniquement `class X(Auditable, ...)` (changement minimal).
- **Frontend** : page `/historique` (PME) + sous-arbre `/admin/audit/*` (Admin), composants dans `components/audit/`, composable et store dédiés, types stricts.
- **Tests** : pyramide classique unit < intégration < E2E. Tests d'intégration valident les invariants append-only et la propagation de `source_of_change`.

## Phase 0 — Research

Voir `research.md`. Synthèse :

1. **SQLAlchemy event listener strategy** : décision retenue = `event.listens_for(Session, 'before_flush')` global + filtrage `isinstance(obj, Auditable)`. Alternative étudiée et rejetée : décorateurs `@auditable_method` sur services (trop intrusif, contournable). Alternative `before_insert/before_update/before_delete` sur Mapper rejetée car ne donne pas accès aux deltas multi-attributs en une passe.
2. **PostgreSQL trigger PL/pgSQL** : pattern standard `CREATE OR REPLACE FUNCTION ... RAISE EXCEPTION ...`, déclenché `BEFORE UPDATE OR DELETE`. Testé par `test_audit_append_only_trigger.py` qui exécute les 2 opérations interdites.
3. **REVOKE UPDATE, DELETE** : si le rôle applicatif est superuser/owner, le REVOKE est no-op et l'avertissement est journalisé en migration. Le trigger reste la défense effective. Documentation `docs/audit-log.md` détaille le passage post-MVP à un rôle séparé.
4. **ContextVar Python 3.12** : `contextvars.ContextVar` est compatible asyncio (chaque task asyncio a son propre `Context`). Validé pour FastAPI async + LangGraph async. Helper `source_of_change_scope` exposé comme context manager (`with source_of_change_scope('llm'): ...`).
5. **CSV streaming UTF-8 BOM** : `StreamingResponse` FastAPI + générateur Python `yield` ligne par ligne via `csv.writer` sur un buffer `io.StringIO` réinitialisé. BOM `﻿` préfixé sur la première ligne. Compatibilité Excel validée par test E2E qui décode le fichier exporté.
6. **Audit des tools LangChain qui font `db.commit()` direct** : recensement initial via `grep -rn "db.commit()\|session.commit()" backend/app/graph/tools/`. Liste précise documentée dans `research.md`. Les tools concernés sont migrés vers les services métier (qui appellent `session.flush()` / commit géré par le contexte FastAPI).
7. **Indexes performance** : 4 indexes (cf. FR-004). Benchmark sur 100k lignes valide `< 500 ms P95`. Pas de partitionnement en MVP (post-MVP : partitionnement par mois si volumétrie >> 1M lignes).
8. **Export volumineux** : streaming via `StreamingResponse` + cursor SQLAlchemy `yield_per(1000)` pour ne pas charger toutes les lignes en mémoire.
9. **Idempotence `view_admin`** : cache `request.state.audit_view_recorded: dict[UUID, bool]` initialisé par middleware, consulté par `record_admin_view`. Invalidation à chaque nouvelle requête (FastAPI `Request.state` est par-requête).
10. **Compatibilité SQLite (tests unitaires)** : les triggers `BEFORE UPDATE/DELETE` PostgreSQL ne sont pas portables sur SQLite. Stratégie de test : tests unitaires utilisent SQLite (rapide, isolé) avec un mock de trigger via `event.listens_for(Mapper, 'before_update')` qui lève `RuntimeError`. Tests d'intégration réels utilisent PostgreSQL (Docker Compose) pour valider les triggers PL/pgSQL.

## Phase 1 — Design Artifacts

### 1. Data Model (cf. `data-model.md`)

#### Table `audit_log` (nouvelle)

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Identifiant unique |
| `user_id` | `UUID` | FK `users.id` ON DELETE RESTRICT, NOT NULL | Acteur (qui a fait l'action) |
| `account_id` | `UUID` | FK `accounts.id` ON DELETE RESTRICT, NOT NULL | Compte propriétaire (cible de l'audit) |
| `timestamp` | `timestamptz` | NOT NULL, DEFAULT `now()` | Horodatage |
| `entity_type` | `varchar(64)` | NOT NULL | Ex. `company_profile`, `fund_application` |
| `entity_id` | `UUID` | NOT NULL | Identifiant de l'entité affectée |
| `action` | ENUM `audit_action` | NOT NULL | `create` / `update` / `delete` / `view_admin` |
| `field` | `varchar(128)` | NULL admise | Champ muté (NULL pour create/delete/view_admin) |
| `old_value` | `JSONB` | NULL admise | Valeur avant (NULL pour create/view_admin) |
| `new_value` | `JSONB` | NULL admise | Valeur après (NULL pour delete/view_admin) |
| `source_of_change` | ENUM `audit_source` | NOT NULL | `manual` / `llm` / `import` / `admin` |
| `actor_metadata` | `JSONB` | NULL admise | `tool_name`, `conversation_id`, `request_id`, `ip_address`, `user_agent`, `endpoint` |

**Contraintes & triggers** :
- Trigger `audit_log_no_update` (`BEFORE UPDATE`) : `RAISE EXCEPTION 'audit_log is append-only ; UPDATE is forbidden'`.
- Trigger `audit_log_no_delete` (`BEFORE DELETE`) : `RAISE EXCEPTION 'audit_log is append-only ; DELETE is forbidden'`.
- `REVOKE UPDATE, DELETE ON audit_log FROM CURRENT_USER` (avec avertissement si rôle superuser).
- `ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY; ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;`
- Policy `pme_access_own_account` : `USING (account_id = current_setting('app.current_account_id', true)::uuid)` pour `SELECT`, `INSERT`.
- Policy `admin_full_access` : `USING (current_setting('app.current_role', true) = 'ADMIN')` pour `SELECT`, `INSERT`.

**Indexes** :
- `idx_audit_log_account_timestamp` ON `(account_id, timestamp DESC)`
- `idx_audit_log_account_entity` ON `(account_id, entity_type, entity_id)`
- `idx_audit_log_user_timestamp` ON `(user_id, timestamp DESC)`
- `idx_audit_log_source_timestamp` ON `(source_of_change, timestamp DESC)`

#### ENUMs PostgreSQL

```sql
CREATE TYPE audit_action AS ENUM ('create', 'update', 'delete', 'view_admin');
CREATE TYPE audit_source AS ENUM ('manual', 'llm', 'import', 'admin');
```

#### Mixin `Auditable` (Python)

```text
class Auditable:
    """Marqueur appliqué aux modèles métier. Activate auto-capture via before_flush listener."""
    pass


AUDITABLE_MODELS = {
    "CompanyProfile",
    "FundApplication",
    "ESGAssessment",
    "ESGCriterionScore",
    "CarbonAssessment",
    "CarbonEmissionEntry",
    "CreditScore",
    "ActionPlan",
    "ActionItem",
}

EXEMPT_MODELS = {
    # Catalogue, pas de capture (cohérent F01) :
    "Source", "Indicator", "Criterion", "Formula", "Threshold", "Referential",
    "ReferentialIndicator", "EmissionFactor", "RequiredDocument",
    "SimulationFactor", "UnsourcedFlag",
    # Infrastructure, pas de capture :
    "User", "Account", "AccountInvitation", "RefreshToken",
    "Conversation", "Message", "InteractiveQuestion", "ToolCallLog",
    "Document", "Report",
}
```

#### ContextVar (Python)

```text
current_source_of_change: ContextVar[str] = ContextVar('current_source_of_change', default='manual')


@contextlib.contextmanager
def source_of_change_scope(value: Literal['manual','llm','import','admin']):
    token = current_source_of_change.set(value)
    try:
        yield
    finally:
        current_source_of_change.reset(token)
```

### 2. API Contracts (cf. `contracts/`)

#### `GET /api/audit/me`

**Auth** : `Depends(get_current_user)` (PME ou Admin — un Admin peut consulter son propre log mais c'est un cas d'usage rare).

**Query params** :
| Paramètre | Type | Optional | Description |
|---|---|---|---|
| `entity_type` | string | yes | Filtre par type d'entité |
| `entity_id` | UUID | yes | Filtre par identifiant d'entité |
| `action` | enum | yes | `create` / `update` / `delete` / `view_admin` |
| `source_of_change` | enum | yes | `manual` / `llm` / `import` / `admin` |
| `since` | datetime ISO 8601 | yes | Borne basse |
| `until` | datetime ISO 8601 | yes | Borne haute |
| `page` | int | yes (défaut 1) | Pagination |
| `limit` | int | yes (défaut 50, max 200) | Taille page |
| `order` | string | yes (défaut `desc`) | `asc` ou `desc` sur `timestamp` |

**Réponse** : `200 OK`
```json
{
  "events": [
    {
      "id": "uuid",
      "timestamp": "2026-05-06T14:23:45.123Z",
      "user_id": "uuid",
      "user_email": "user@example.com",
      "account_id": "uuid",
      "entity_type": "company_profile",
      "entity_id": "uuid",
      "action": "update",
      "field": "sector",
      "old_value": "agriculture",
      "new_value": "energie",
      "source_of_change": "manual",
      "actor_metadata": {"endpoint": "/api/companies/me", "request_id": "uuid"}
    }
  ],
  "total": 1234,
  "page": 1,
  "limit": 50
}
```

**Erreurs** : `401` non authentifié, `400` paramètres invalides.

#### `GET /api/audit/me/export`

**Auth** : idem.

**Query params** : tous ceux de `GET /api/audit/me` + `format` (`csv` ou `json`, défaut `csv`).

**Réponse** : `200 OK`
- `Content-Type: text/csv; charset=utf-8` ou `application/json`
- `Content-Disposition: attachment; filename="audit-log-<account_id>-<YYYYMMDD>.<ext>"`
- Body : streaming CSV (UTF-8 BOM en première ligne) ou JSON array.

#### `GET /api/admin/audit/{account_id}`

**Auth** : `Depends(get_current_admin)` (cohérent F02).

**Effet de bord** : déclenche `record_admin_view(admin, account_id, request_context)` au début du handler (idempotent par requête).

**Query params** : idem `GET /api/audit/me`.

**Réponse** : `200 OK` (mêmes champs).

**Erreurs** : `403` non Admin, `404` `account_id` inconnu.

#### `GET /api/admin/audit`

**Auth** : `Depends(get_current_admin)`.

**Query params** : tous ceux de `GET /api/audit/me` + `account_id`, `user_id`. Pas de `record_admin_view` (pas de cible PME unique).

**Réponse** : `200 OK`.

### 3. Quickstart (cf. `quickstart.md`)

#### Lancer la feature en local

```bash
# 1. Activer venv backend
cd backend && source venv/bin/activate

# 2. Installer dépendances (aucune nouvelle pour F03 ; tout est déjà dans requirements.txt)

# 3. Démarrer Postgres (Docker Compose)
docker compose up postgres -d

# 4. Appliquer migration F03
alembic upgrade head
# La migration 021_create_audit_log doit s'appliquer après 020_sources

# 5. Lancer backend (devrait charger Auditable et le listener before_flush au démarrage)
uvicorn app.main:app --reload

# 6. Frontend
cd ../frontend && npm run dev

# 7. Tester
# - PME : éditer profil → ouvrir /historique → voir l'entrée
# - PME : créer candidature via chat → ouvrir /historique → voir entrée llm
# - Admin : consulter /admin/audit/<pme_account_id> → côté PME voir entrée view_admin
```

#### Vérifier les triggers append-only

```bash
psql $DATABASE_URL
> UPDATE audit_log SET source_of_change='manual' WHERE id='<some_id>';
ERROR:  audit_log is append-only ; UPDATE is forbidden
> DELETE FROM audit_log WHERE id='<some_id>';
ERROR:  audit_log is append-only ; DELETE is forbidden
```

#### Lancer tests

```bash
# Backend (unit + intégration)
cd backend && source venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend (unit)
cd frontend && npm run test -- --coverage

# E2E (Playwright)
cd frontend && npx playwright test tests/e2e/F03-audit-log.spec.ts --reporter=html
```

### 4. Agent file update (`CLAUDE.md`)

Ajouter dans "Active Technologies" :
```
- Python 3.12 (backend), TypeScript 5.x strict (frontend) + FastAPI, SQLAlchemy async (event listeners before_flush), Alembic, Pydantic v2, Nuxt 4, Vue Composition API, Pinia, TailwindCSS (021-audit-log)
- PostgreSQL 16 + pgvector, triggers PL/pgSQL append-only, RLS hérité de F02, ContextVar Python pour source_of_change (021-audit-log)
```

Ajouter dans "Recent Changes" :
```
- 021-audit-log: Module audit log append-only complet. Table audit_log avec triggers PostgreSQL BEFORE UPDATE/DELETE qui RAISE EXCEPTION + REVOKE UPDATE, DELETE sur le rôle applicatif (double défense). Mixin SQLAlchemy `Auditable` couplé à un listener global `before_flush` qui parcourt session.new/dirty/deleted, calcule un diff field-level borné à 10 KB par valeur (marqueur _truncated), et insère N lignes audit_log dans la même transaction. ContextVar `current_source_of_change` (default 'manual'), positionnée par les 9 nœuds LangGraph (set 'llm') et un middleware admin (set 'admin'). 9 modèles auditables : CompanyProfile, FundApplication, ESGAssessment, ESGCriterionScore, CarbonAssessment, CarbonEmissionEntry, CreditScore, ActionPlan, ActionItem. Service `AuditService.record_admin_view` appelé automatiquement par les endpoints admin sensibles (idempotent par requête via request.state). 4 endpoints API : GET /api/audit/me, GET /api/audit/me/export (CSV UTF-8 BOM ou JSON streaming), GET /api/admin/audit/{account_id}, GET /api/admin/audit. Frontend : page /historique (PME, timeline + filtres + pagination + export), pages /admin/audit et /admin/audit/:accountId (Admin), composants AuditLogEntry/AuditTimeline/AuditExportButton/AuditFilters, composable useAuditLog, store Pinia audit. Migration Alembic 021_create_audit_log avec down_revision='020_sources'. RLS héritée de F02 (policies pme_access_own_account et admin_full_access, INSERT+SELECT only). Tests : 30+ backend (unit, intégration triggers/RLS/source_of_change/view_admin/whitelist AUDITABLE_MODELS/performance) + 10+ frontend Vitest + 4 scénarios Playwright. Couverture cible ≥ 85 %. Documentation docs/audit-log.md (modèle de menaces, schéma, requêtes, format export, limites MVP RGPD).
```

## Complexity Tracking

*Aucune dérogation à justifier.* Constitution Check : PASS.

| Décision | Choix retenu | Alternative rejetée | Raison |
|---|---|---|---|
| Capture mutations | Mixin `Auditable` + listener `before_flush` global | Décorateurs `@auditable_method` sur services | Listener global = invariant non-contournable ; décorateurs pourraient être oubliés. |
| Append-only enforcement | Trigger PL/pgSQL **+** REVOKE permission | Trigger seul OU REVOKE seul | Double défense en profondeur ; chaque mécanisme peut être bypassé isolément. |
| Source of change | ContextVar Python explicite | Introspection automatique du frame courant | Explicite > implicite (Zen of Python) ; testable. |
| Diff format | Field-level (1 row par champ muté) | Object-level (1 row pour tout l'objet) | Requêtage par champ trivial (`WHERE field='sector'`) ; volume similaire car limite 10 KB par valeur. |
| Troncature valeurs | Côté Python (avant insertion) | Contrainte SQL CHECK sur taille | Permet stockage du marqueur `_truncated` ; pas de rejet PostgreSQL. |
| Format export | CSV UTF-8 BOM + JSON streaming | XLSX | XLSX nécessite openpyxl en plus ; CSV suffisant pour Excel + outils audit. |
| Rôle DB séparé | Pas en MVP (utilise rôle existant) | Rôle `application_user` distinct créé en migration | Cohérent décision F02 ; trigger reste défense effective. |
| Partitionnement audit_log | Pas en MVP (post-MVP si > 1M lignes) | Partitionnement par mois immediate | YAGNI ; index suffisent jusqu'à 100k+ lignes par compte. |
| Hashing/Merkle | Hors-scope MVP | Chaîne Merkle pour preuve d'intégrité | Post-MVP ; le trigger + REVOKE protège déjà l'invariant. |
