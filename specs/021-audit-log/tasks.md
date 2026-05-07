---
description: "Task list for F03 Audit Log Append-Only"
---

# Tasks: F03 — Audit Log Append-Only

**Input** : Design documents from `/Users/mac/Documents/projets/2025/esg_mefali_v3/specs/021-audit-log/`
**Prerequisites** : plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests** : OBLIGATOIRES — TDD strict (tests AVANT implémentation), couverture ≥ 85 %.

**Organization** : Tasks groupées par user story pour activation/test indépendants. Conventions :

- **[P]** : tâche parallélisable (fichier différent, pas de dépendance bloquante).
- **[USx]** : rattachement à une user story (US1 reconstitution historique, US2 transparence admin, US3 export, US4 perf 100k+, US5 garantie de log).
- Chaque path est ABSOLU. Backend root : `/Users/mac/Documents/projets/2025/esg_mefali_v3/backend/`. Frontend root : `/Users/mac/Documents/projets/2025/esg_mefali_v3/frontend/`.

## Path Conventions

- Backend : `backend/app/...`, `backend/tests/...`, `backend/alembic/versions/...`
- Frontend : `frontend/app/...`, `frontend/tests/unit/...`, `frontend/tests/e2e/...`
- Docs : `docs/...`

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparation des constantes, types, schémas Pydantic communs avant toute implémentation. Aucune logique métier ici.

- [ ] T001 [P] Créer `backend/app/core/audit_context.py` avec : `current_source_of_change: ContextVar[str] = ContextVar("current_source_of_change", default="manual")`, helper `@contextlib.contextmanager source_of_change_scope(value: Literal["manual","llm","import","admin"])` qui fait `set` puis `reset` via Token, et un helper `get_current_source_of_change() -> str`.
- [ ] T002 [P] Étendre `backend/app/core/constants.py` avec : enum `AuditAction` (`create`, `update`, `delete`, `view_admin`) et `AuditSourceOfChange` (`manual`, `llm`, `import_`, `admin`), et constante `AUDIT_VALUE_MAX_BYTES = 10 * 1024`.
- [ ] T003 [P] Créer `backend/app/modules/audit/schemas.py` avec Pydantic v2 : `AuditEvent` (id, timestamp, user_id, user_email, account_id, entity_type, entity_id, action, field, old_value, new_value, source_of_change, actor_metadata), `AuditEventList` (events, total, page, limit), `AuditFilters` (entity_type, entity_id, action, source_of_change, since, until, page=1, limit=50, order='desc', account_id, user_id), `AuditExportFormat` (Literal `csv` ou `json`).
- [ ] T004 [P] Créer types TypeScript `frontend/app/types/audit.ts` avec : `type AuditAction = 'create' | 'update' | 'delete' | 'view_admin'`, `type AuditSourceOfChange = 'manual' | 'llm' | 'import' | 'admin'`, `interface AuditEvent { ... }`, `interface AuditEventList { events; total; page; limit }`, `interface AuditFilters { ... }`.

**Checkpoint Phase 1** : ContextVar, constantes, schémas et types définis. Aucune logique métier touchée.

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Mixin `Auditable`, modèle `AuditLog`, migration Alembic 021, helpers troncature. **Aucune user story ne peut démarrer avant la fin de cette phase.**

**TDD strict** : pour chaque module/helper, écrire les tests AVANT le code.

### Tests fondations (TDD red)

- [ ] T005 [P] Créer `backend/tests/unit/test_audit_context.py` avec tests : (a) défaut `manual`, (b) `set("llm")` puis lecture retourne `"llm"`, (c) `source_of_change_scope("admin")` set puis reset à la sortie, (d) isolation entre 2 tasks asyncio (chaque task a sa propre valeur), (e) la valeur ne fuit pas vers une autre coroutine en parallèle.
- [ ] T006 [P] Créer `backend/tests/unit/test_audit_truncate.py` avec tests pour `_truncate_value(value)` : (a) valeur < 10 KB inchangée, (b) valeur > 10 KB renvoie `{"_truncated": true, "_truncated_size": <bytes>, "_preview": "<8 KB>"}`, (c) valeur exactement 10 KB inchangée, (d) None inchangé, (e) types non-natifs (UUID, Decimal, datetime) sérialisent correctement via `_json_default`.
- [ ] T007 [P] Créer `backend/tests/unit/test_models_audit_log.py` avec tests : (a) création d'un `AuditLog` minimal, (b) `timestamp` auto-rempli si absent, (c) ENUM `action` rejette une valeur invalide, (d) ENUM `source_of_change` rejette une valeur invalide, (e) FK `user_id` et `account_id` requis NOT NULL, (f) `field` autorise NULL, (g) `old_value` et `new_value` autorisent NULL et acceptent du JSON arbitraire.
- [ ] T008 [P] Créer `backend/tests/unit/test_auditable_mixin.py` avec tests (sur SQLite, marqueur `@pytest.mark.unit`) : (a) `class X(Auditable): pass` est `isinstance(X(), Auditable)`, (b) listener `before_flush` enregistré au démarrage, (c) création d'une instance `Auditable` → 1 ligne `audit_log` `action=create` insérée, (d) update 1 champ → 1 ligne `audit_log` `action=update, field=<X>`, (e) update N champs → N lignes `audit_log` (une par champ), (f) suppression → 1 ligne `audit_log` `action=delete`, (g) anti-récursion : insertion d'un `AuditLog` n'entraîne pas d'audit_log d'audit_log, (h) modèle non-`Auditable` (ex. `Source`) ne génère aucune ligne d'audit, (i) rollback : si la transaction métier rollback, l'audit_log rollback aussi.
- [ ] T009 [P] Créer `backend/tests/integration/test_alembic_021_upgrade_downgrade.py` avec tests (marqueur `@pytest.mark.postgres`) : (a) `alembic upgrade head` applique 021 après 020_sources, (b) table `audit_log` créée avec 12 colonnes, (c) 4 indexes présents, (d) 2 ENUMs PostgreSQL `audit_action` et `audit_source` créés, (e) 2 triggers `audit_log_no_update`, `audit_log_no_delete` présents (`SELECT tgname FROM pg_trigger WHERE tgrelid='audit_log'::regclass`), (f) RLS active (`SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='audit_log'` retourne `t,t`), (g) 4 policies (`pme_access_own_account`, `pme_insert_own_account`, `admin_full_access`, `admin_insert_anywhere`), (h) `alembic downgrade -1` supprime tout proprement (table, ENUMs, fonctions, triggers, policies), (i) `alembic upgrade head` re-applique sans erreur.
- [ ] T010 [P] Créer `backend/tests/integration/test_audit_append_only_trigger.py` avec tests (marqueur `@pytest.mark.postgres`) : (a) insérer une ligne `audit_log` directement via SQL → OK, (b) `UPDATE audit_log SET source_of_change='manual' WHERE id=...` → `ProgrammingError` avec message `audit_log is append-only ; UPDATE is forbidden`, (c) `DELETE FROM audit_log WHERE id=...` → `ProgrammingError` avec message `audit_log is append-only ; DELETE is forbidden`, (d) test idempotent : on peut tenter plusieurs UPDATE → tous échouent.

### Implémentation fondations

- [ ] T011 Créer `backend/app/models/audit_log.py` avec : enums Python `AuditAction`, `AuditSourceOfChange` (mappés sur ENUMs PG), modèle `AuditLog(UUIDMixin, Base)` avec colonnes `user_id, account_id, timestamp, entity_type, entity_id, action, field, old_value, new_value, source_of_change, actor_metadata`. Doit faire passer T007.
- [ ] T012 Créer `backend/app/core/auditable.py` avec : (a) marqueur `class Auditable: pass`, (b) constantes `AUDITABLE_MODELS = frozenset({"CompanyProfile", "FundApplication", "ESGAssessment", "ESGCriterionScore", "CarbonAssessment", "CarbonEmissionEntry", "CreditScore", "ActionPlan", "ActionItem"})` et `EXEMPT_MODELS`, (c) helper `_truncate_value(value, max_bytes=AUDIT_VALUE_MAX_BYTES)` avec marqueur `_truncated`, (d) helper `_json_default(obj)` pour UUID/Decimal/datetime/date/Enum, (e) helper `_make_create_row(obj, actor_id, source)`, `_make_update_rows(obj, actor_id, source)`, `_make_delete_row(obj, actor_id, source)`, (f) listener `@event.listens_for(Session, "before_flush")` qui parcourt `session.new/dirty/deleted`, filtre `Auditable`, ignore `AuditLog` (anti-récursion), insère via `session.execute(insert(AuditLog), rows)`. Doit faire passer T006 et T008.
- [ ] T013 Créer migration `backend/alembic/versions/021_create_audit_log.py` : revision `021_audit_log`, down_revision `020_sources`. (a) `CREATE TYPE audit_action AS ENUM ...`, (b) `CREATE TYPE audit_source AS ENUM ...`, (c) `CREATE TABLE audit_log (...)` avec FKs ON DELETE RESTRICT, (d) 4 `CREATE INDEX`, (e) 2 fonctions PL/pgSQL `raise_audit_log_no_update`, `raise_audit_log_no_delete`, (f) 2 triggers `BEFORE UPDATE` et `BEFORE DELETE`, (g) bloc DO `REVOKE UPDATE, DELETE` avec `EXCEPTION WHEN OTHERS THEN RAISE NOTICE` (best-effort), (h) `ENABLE` + `FORCE ROW LEVEL SECURITY`, (i) 4 policies (`pme_access_own_account`, `pme_insert_own_account`, `admin_full_access`, `admin_insert_anywhere`). Downgrade complet en ordre inverse. Doit faire passer T009 et T010.
- [ ] T014 Importer le listener au démarrage de l'app : éditer `backend/app/main.py` (ZONE INTERDITE — sérialiser avec orchestrateur) pour ajouter `import app.core.auditable  # registers before_flush listener` au top-level (chargé une fois lors du chargement du module).

**Checkpoint Phase 2** : modèles, mixin, ContextVar, migration prêts. Tous les tests fondations passent. Les user stories peuvent démarrer.

---

## Phase 3 : User Story 1 — Reconstitution historique (Priority: P1)

**Goal** : Toute mutation sur les 9 modèles auditables produit automatiquement les bonnes lignes audit_log avec source_of_change correct selon le contexte.

**Independent Test** : voir spec.md US1.

### Tests US1 (TDD red)

- [ ] T015 [P] [US1] Créer `backend/tests/integration/test_audit_create_update_delete.py` avec tests pour chacun des 9 modèles auditables (`CompanyProfile`, `FundApplication`, `ESGAssessment`, `ESGCriterionScore`, `CarbonAssessment`, `CarbonEmissionEntry`, `CreditScore`, `ActionPlan`, `ActionItem`) : (a) création → 1 audit_log `action=create` avec `new_value` snapshot, (b) update 1 champ → 1 audit_log `action=update, field=<X>` avec old/new, (c) update 3 champs en une transaction → 3 audit_log distincts (un par champ) tous avec le même timestamp, (d) suppression → 1 audit_log `action=delete` avec `old_value` snapshot.
- [ ] T016 [P] [US1] Créer `backend/tests/integration/test_audit_source_of_change.py` avec tests paramétrés : (a) mutation via API REST PME (`PATCH /api/companies/me`) → audit_log `source_of_change=manual`, (b) mutation via tool LangChain (avec `with source_of_change_scope("llm"): service.update(...)`) → audit_log `source_of_change=llm`, (c) mutation via endpoint admin (avec middleware admin actif) → audit_log `source_of_change=admin`, (d) la valeur par défaut quand aucun scope n'est ouvert est `manual`.
- [ ] T017 [P] [US1] Créer `backend/tests/integration/test_audit_truncate_in_log.py` avec test : insérer une mutation sur un champ JSON dont la valeur sérialisée fait > 10 KB, vérifier que la ligne `audit_log` contient `new_value = {"_truncated": true, "_truncated_size": <bytes>, "_preview": "..."}` et que la valeur originale n'est pas perdue (préservée dans le modèle).

### Implémentation US1

- [ ] T018 [P] [US1] Modifier `backend/app/models/company.py` : ajouter `from app.core.auditable import Auditable` et changer la classe en `class CompanyProfile(Auditable, UUIDMixin, TimestampMixin, Base)`.
- [ ] T019 [P] [US1] Modifier `backend/app/models/application.py` : `class FundApplication(Auditable, ...)`.
- [ ] T020 [P] [US1] Modifier `backend/app/models/esg.py` : `ESGAssessment` et `ESGCriterionScore` héritent de `Auditable`.
- [ ] T021 [P] [US1] Modifier `backend/app/models/carbon.py` : `CarbonAssessment` et `CarbonEmissionEntry` héritent de `Auditable`.
- [ ] T022 [P] [US1] Modifier `backend/app/models/credit.py` : `CreditScore` hérite de `Auditable`.
- [ ] T023 [P] [US1] Modifier `backend/app/models/action_plan.py` : `ActionPlan` et `ActionItem` héritent de `Auditable`.
- [ ] T024 [US1] Auditer les 9 nœuds LangGraph (`backend/app/graph/nodes/{chat,esg_scoring,carbon,financing,application,credit,action_plan,document,profiling}_node.py`) et envelopper chaque appel de service métier dans `with source_of_change_scope("llm"): ...`. Note : appliquer le scope au niveau de l'invocation du nœud (debut/fin), pas par tool individuel, pour couvrir aussi les `await session.flush()` indirects.
- [ ] T025 [US1] Auditer les tools LangChain qui font `db.commit()` direct : `grep -rn "db.commit()\|session.commit()\|self.db.commit()" backend/app/graph/tools/` ; pour chaque occurrence, migrer le tool pour qu'il appelle le service métier (`CompanyService.update`, `FundApplicationService.create`, etc.) au lieu de modifier la session directement. Documenter la liste des tools migrés dans `docs/audit-log.md`.

**Checkpoint US1** : tests T015-T017 verts. Toute mutation passe par le mixin et produit la bonne `source_of_change`. US1 indépendamment testable.

---

## Phase 4 : User Story 2 — Transparence admin (Priority: P1)

**Goal** : Tout accès admin à un compte PME est tracé via `view_admin` et visible côté PME.

**Independent Test** : voir spec.md US2.

### Tests US2 (TDD red)

- [ ] T026 [P] [US2] Créer `backend/tests/integration/test_audit_view_admin.py` avec tests : (a) `GET /api/admin/audit/{account_id}` par un admin → ligne `audit_log` `action=view_admin, source_of_change=admin, entity_type=account, entity_id=<account_id>, account_id=<account_id>, user_id=<admin_id>` créée, (b) la ligne contient `actor_metadata` avec `endpoint`, `request_id`, `ip_address`, `user_agent`, (c) la PME concernée voit cette ligne via `GET /api/audit/me` (RLS), (d) idempotence : 2 sous-handlers d'une même requête appellent `record_admin_view` → 1 seule ligne créée (cache `request.state`), (e) 2 requêtes HTTP distinctes → 2 lignes créées (cache reset par requête).
- [ ] T027 [P] [US2] Créer `backend/tests/integration/test_admin_audit_context_middleware.py` avec tests : (a) une mutation effectuée par un admin sur un endpoint `/api/admin/*` produit un audit_log `source_of_change=admin`, (b) une mutation par un PME sur `/api/companies/me` produit `source_of_change=manual` (le middleware admin n'intercepte pas).

### Implémentation US2

- [ ] T028 [P] [US2] Créer `backend/app/modules/audit/__init__.py` (vide).
- [ ] T029 [US2] Créer `backend/app/modules/audit/service.py` avec : (a) classe `AuditService(db: AsyncSession)`, (b) méthode `async record_admin_view(self, admin_user, target_account_id, request)` qui consulte `request.state.audit_view_recorded` (init si absent), insère un `AuditLog` `action=view_admin, source_of_change=admin, entity_type='account', entity_id=target_account_id, account_id=target_account_id, user_id=admin_user.id, actor_metadata={endpoint, request_id, ip_address, user_agent}`, marque le cache, et flush. Doit faire passer T026.
- [ ] T030 [P] [US2] Créer `backend/app/modules/admin/middleware.py` avec `AdminAuditContextMiddleware(BaseHTTPMiddleware)` : si `request.url.path.startswith("/api/admin/")`, ouvrir `with source_of_change_scope("admin")` autour de `await call_next(request)`. Doit faire passer T027.
- [ ] T031 [US2] Modifier `backend/app/main.py` (ZONE INTERDITE — sérialiser) : registrer `AdminAuditContextMiddleware` (avant les routes admin).

**Checkpoint US2** : tests T026-T027 verts. Tout accès admin laisse une trace visible côté PME. US2 indépendamment testable.

---

## Phase 5 : User Story 3 — Export CSV/JSON (Priority: P2)

**Goal** : Exporter le log filtré en CSV (UTF-8 BOM) ou JSON, avec accents français préservés.

**Independent Test** : voir spec.md US3.

### Tests US3 (TDD red)

- [ ] T032 [P] [US3] Créer `backend/tests/unit/test_audit_csv_writer.py` avec tests : (a) helper `_stream_csv(events: AsyncIterator[AuditEvent]) -> AsyncIterator[bytes]` produit un fichier CSV qui commence par BOM UTF-8 (`\xef\xbb\xbf`), (b) en-tête correct, (c) accents français (`é`, `è`, `ç`, `à`, `ù`) préservés, (d) virgules dans les valeurs sont escapées, (e) retours ligne dans `actor_metadata` JSON sérialisés correctement.
- [ ] T033 [P] [US3] Créer `backend/tests/integration/test_audit_endpoints_pme_export.py` avec tests : (a) `GET /api/audit/me/export?format=csv` retourne `Content-Type: text/csv; charset=utf-8` avec `Content-Disposition` adéquat, (b) `?format=json` retourne `application/json` avec un tableau JSON, (c) filtres respectés (`since`, `entity_type`), (d) export vide retourne 200 avec en-tête CSV ou `[]` JSON (pas 404), (e) non authentifié → 401.

### Implémentation US3

- [ ] T034 [P] [US3] Créer `backend/app/modules/audit/csv_writer.py` avec helper `_stream_csv(events)` produisant bytes avec BOM + en-tête + lignes. Utiliser `csv.writer` sur `io.StringIO` réinitialisé. Doit faire passer T032.
- [ ] T035 [US3] Étendre `backend/app/modules/audit/service.py` avec : `async list_for_account(filters: AuditFilters) -> tuple[list[AuditEvent], int]` (query SQL avec ORDER BY timestamp DESC, OFFSET/LIMIT, COUNT pour total), `async stream_for_account(filters) -> AsyncIterator[AuditEvent]` (cursor `yield_per(1000)` pour export), helper `format_event_for_render(audit_log_row) -> AuditEvent`.
- [ ] T036 [US3] Créer `backend/app/modules/audit/router.py` avec routes : (a) `GET /api/audit/me` → `list_for_account` + JSON `AuditEventList`, (b) `GET /api/audit/me/export?format=csv|json` → `StreamingResponse` (CSV ou JSON streaming). Doit faire passer T033.

**Checkpoint US3** : tests T032-T033 verts. Export CSV/JSON fonctionnel. US3 indépendamment testable.

---

## Phase 6 : User Story 4 — Performance (Priority: P2)

**Goal** : Pagination, filtres et indexes garantissent < 500 ms P95 sur 100k lignes par compte.

**Independent Test** : voir spec.md US4.

### Tests US4 (TDD red)

- [ ] T037 [P] [US4] Créer `backend/tests/integration/test_audit_performance.py` avec : (a) test perf `test_audit_list_p95_under_500ms` qui seed 100 000 lignes pour 1 PME, exécute 50 fois `GET /api/audit/me?page=1&limit=50`, calcule P95, vérifie < 500 ms, (b) test perf avec filtres `entity_type=fund_application&since=...`, (c) test perf overhead par mutation : mesurer le temps d'un `await session.flush()` avec et sans le mixin actif, vérifier overhead < 5 ms.
- [ ] T038 [P] [US4] Créer `backend/tests/integration/test_audit_endpoints_pme_list.py` avec tests pour `GET /api/audit/me` : (a) défaut `page=1, limit=50`, (b) filtre `entity_type`, `entity_id`, `action`, `source_of_change`, `since`, `until`, (c) `order=asc/desc`, (d) `limit > 200` → 400, (e) `limit < 1` → 400, (f) tri par défaut `timestamp DESC`.

### Implémentation US4

- [ ] T039 [US4] Vérifier que les 4 indexes de la migration 021 sont bien utilisés via `EXPLAIN ANALYZE` dans le test perf. Si un plan utilise un Seq Scan, ajuster la requête (utiliser le tuple d'index approprié).
- [ ] T040 [US4] Optimiser le COUNT total dans `list_for_account` : utiliser `func.count().over()` window function ou un COUNT séparé selon le coût. Documenter la décision.

**Checkpoint US4** : tests T037-T038 verts. Performance ≥ exigences SC-006/SC-010. US4 indépendamment testable.

---

## Phase 7 : User Story 5 — Garantie qu'aucune mutation n'échappe au log (Priority: P1)

**Goal** : Tests CI vérifient l'invariant `Auditable` sur tous les modèles métier ; les tools LangChain bypass sont migrés.

**Independent Test** : voir spec.md US5.

### Tests US5 (TDD red)

- [ ] T041 [P] [US5] Créer `backend/tests/integration/test_audit_models_whitelist.py` avec tests : (a) `test_auditable_models_whitelist_complete` qui scanne `app/models/` via introspection (lister toutes les classes héritant de `Base`), filtre les modèles métier (selon une liste partagée avec F02 ou via convention), vérifie que chaque modèle métier est soit dans `AUDITABLE_MODELS` soit dans `EXEMPT_MODELS`, (b) `test_no_orphan_in_auditable_models` : chaque nom dans `AUDITABLE_MODELS` correspond bien à une classe `Auditable` réellement présente dans `app/models/`.
- [ ] T042 [P] [US5] Créer `backend/tests/integration/test_audit_rls_isolation.py` avec test : (a) créer 2 PME (A, B), (b) sous le contexte RLS de A : faire des mutations sur ses entités, (c) sous le contexte RLS de A : `SELECT * FROM audit_log` ne retourne que les événements de A, (d) sous le contexte RLS de B : ne voit que les événements de B, (e) sous le contexte Admin : voit les 2 jeux d'événements.
- [ ] T043 [P] [US5] Créer `backend/tests/integration/test_audit_endpoints_admin.py` avec tests : (a) `GET /api/admin/audit/{account_id}` par Admin → 200 et events du compte, (b) par PME → 403, (c) par non-authentifié → 401, (d) `GET /api/admin/audit?account_id=X&user_id=Y` filtre correctement, (e) un appel admin `GET /api/admin/audit/{account_id}` produit 1 ligne `audit_log` `view_admin` (idempotent par requête).

### Implémentation US5

- [ ] T044 [US5] Étendre `backend/app/modules/audit/service.py` avec : `async list_global(filters)` (admin only, pas de RLS account_id mais filtre query si fourni), `async list_for_account_admin(account_id, filters)` (appelle `record_admin_view` puis `list_for_account`).
- [ ] T045 [US5] Étendre `backend/app/modules/audit/router.py` avec : (a) `GET /api/admin/audit/{account_id}` (Depends `get_current_admin`) → `list_for_account_admin`, (b) `GET /api/admin/audit` → `list_global`. Doit faire passer T043.
- [ ] T046 [US5] Modifier `backend/app/main.py` (ZONE INTERDITE — sérialiser) : registrer le router audit (`/api/audit/*` et `/api/admin/audit/*`).

**Checkpoint US5** : tests T041-T043 verts. Garde-fous CI actifs. US5 indépendamment testable.

---

## Phase 8 : Frontend (intersecte plusieurs US)

**Purpose** : Pages Nuxt PME et Admin, composants Vue, composable et store.

### Tests frontend (TDD red)

- [ ] T047 [P] Créer `frontend/tests/unit/audit/AuditLogEntry.spec.ts` avec tests : (a) rend le libellé `Création / Modification / Suppression / Consultation Admin` selon `action`, (b) rend l'acteur `Vous / Un collaborateur / L'assistant IA / Un admin Mefali` selon `user_id` et `source_of_change`, (c) rend le diff `field : oldValue → newValue` pour `action=update`, (d) horodatage relatif (« il y a X minutes ») via `useTimeAgo` ou helper local, (e) dark mode classes appliquées.
- [ ] T048 [P] Créer `frontend/tests/unit/audit/AuditFilters.spec.ts` avec tests : (a) emit `update:filters` quand un filtre change, (b) sync URL query params via `useRouter().push({ query })`, (c) lecture initiale depuis `useRoute().query`.
- [ ] T049 [P] Créer `frontend/tests/unit/audit/useAuditLog.spec.ts` avec tests : (a) `fetchMe(filters)` appelle `GET /api/audit/me` avec les bons params, (b) `exportCsv(filters)` télécharge un fichier CSV, (c) `exportJson(filters)` télécharge un fichier JSON, (d) `fetchByAccount(accountId, filters)` appelle `GET /api/admin/audit/{account_id}`, (e) `fetchGlobal(filters)` appelle `GET /api/admin/audit`.

### Implémentation frontend

- [ ] T050 [P] Créer `frontend/app/composables/useAuditLog.ts` exposant `fetchMe`, `exportCsv`, `exportJson`, `fetchByAccount`, `fetchGlobal`. Doit faire passer T049.
- [ ] T051 [P] Créer `frontend/app/stores/audit.ts` (Pinia) avec : state `events`, `total`, `filters`, `isLoading`, `error` ; actions `loadPage(page)`, `applyFilters(filters)`, `reset()`.
- [ ] T052 [P] Créer `frontend/app/components/audit/AuditLogEntry.vue` avec layout sémantique (rôle `listitem`), libellés français, dark mode (`bg-white dark:bg-dark-card`, `text-surface-text dark:text-surface-dark-text`), accent admin pour `view_admin` (couleur orange/rouge cohérente F02). Doit faire passer T047.
- [ ] T053 [P] Créer `frontend/app/components/audit/AuditTimeline.vue` qui itère sur les events et rend les `AuditLogEntry` dans une `<ol>` verticale.
- [ ] T054 [P] Créer `frontend/app/components/audit/AuditFilters.vue` avec selects (entity_type, source_of_change, action), date pickers (since/until), input recherche libre. Sync URL query params. Doit faire passer T048.
- [ ] T055 [P] Créer `frontend/app/components/audit/AuditExportButton.vue` (dropdown CSV/JSON) qui appelle `useAuditLog().exportCsv/exportJson` avec les filtres courants.
- [ ] T056 [P] Créer `frontend/app/pages/historique.vue` (route `/historique`, layout `default`) qui compose : `AuditFilters` + `AuditTimeline` + `AuditExportButton` + pagination. Dark mode complet.
- [ ] T057 [P] Créer `frontend/app/pages/admin/audit/index.vue` (layout `admin` de F02) : log global filtrable (filtre `account_id`, `user_id`).
- [ ] T058 [P] Créer `frontend/app/pages/admin/audit/[accountId].vue` (layout `admin`) : log d'un compte PME spécifique. Au montage, appelle `fetchByAccount(accountId)` qui hit `GET /api/admin/audit/{account_id}` (déclenche `view_admin` côté backend).

**Checkpoint Frontend** : tests T047-T049 verts, pages et composants prêts.

---

## Phase 9 : E2E Playwright (intersecte toutes les US)

- [ ] T059 [P] Créer `frontend/tests/e2e/F03-audit-log.spec.ts` avec 4 scénarios :
  - **`pme_edits_profile_creates_manual_audit`** : (a) connexion PME, (b) `goto('/profile')`, (c) modifier `sector`, (d) sauvegarder, (e) `goto('/historique')`, (f) attendre l'entrée `audit_log` correspondante (libellé `Modification`, source `Manuel`, diff `sector : agriculture → energie`).
  - **`llm_creates_application_creates_llm_audit`** : (a) connexion PME, (b) `goto('/chat')`, (c) saisir un prompt qui déclenche le tool `create_fund_application`, (d) attendre la fin du flow LLM, (e) `goto('/historique')`, (f) vérifier l'entrée `Création` avec source `LLM` et `actor_metadata.tool_name = "create_fund_application"`.
  - **`admin_views_pme_account_creates_view_admin_audit`** : (a) connexion Admin, (b) `goto('/admin/audit/<pme_account_id>')`, (c) attendre chargement, (d) déconnexion, (e) connexion PME, (f) `goto('/historique')`, (g) vérifier l'entrée `Consultation Admin` avec source `Admin` et `actor_metadata.endpoint`.
  - **`pme_exports_audit_log_csv_with_french_accents`** : (a) seed quelques events avec accents (« Modification : sector → énergie renouvelable »), (b) connexion PME, (c) `goto('/historique')`, (d) cliquer sur Export → CSV, (e) attendre le téléchargement, (f) lire le fichier (`fs.readFileSync`), (g) vérifier qu'il commence par BOM UTF-8 (`\xef\xbb\xbf`), (h) parser avec `csv-parse`, (i) vérifier que les accents sont intacts (`é`, `è`, `ç`).

**Checkpoint E2E** : test Playwright vert (4 scénarios passing).

---

## Phase 10 : Documentation et Polish

- [ ] T060 Créer `docs/audit-log.md` avec sections : (a) Modèle de menaces (tableau menace/vecteur/mitigation depuis data-model.md §9), (b) Schéma `audit_log` complet, (c) Requêtes SQL communes (« Reconstituer l'historique d'une candidature » via `WHERE entity_type='fund_application' AND entity_id=...`, « Tous les events d'un user »), (d) Format export CSV/JSON, (e) Limites MVP (RGPD vs append-only, pas de Merkle, pas de PDF signé, pas de partitionnement, pas de rôle DB séparé), (f) Procédure pour rendre auditable un nouveau modèle (ajouter `Auditable` à la classe + ajouter le nom à `AUDITABLE_MODELS`), (g) Liste des tools LangChain migrés (de la T025).
- [ ] T061 Étendre `CLAUDE.md` (ZONE INTERDITE — sérialiser avec orchestrateur) : ajouter section "Active Technologies" et "Recent Changes" pour F03 (cf. plan.md §1.4 "Agent file update").
- [ ] T062 Vérifier la couverture de tests : `cd backend && pytest tests/ --cov=app.core.auditable --cov=app.core.audit_context --cov=app.modules.audit --cov=app.models.audit_log --cov-report=term-missing` ≥ 85 %. `cd frontend && npm run test -- --coverage app/components/audit app/composables/useAuditLog app/stores/audit` ≥ 85 %.
- [ ] T063 Compilation Python : `cd backend && python -m py_compile $(find app -name '*.py')` doit passer sans erreur.
- [ ] T064 Type-check frontend : `cd frontend && npx nuxt typecheck` (ou `npm run build`) doit passer sans erreur.

---

## Phase 11 : Validation finale (orchestrateur)

- [ ] T065 Lancer la migration full cycle : `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → tout passe sans erreur.
- [ ] T066 Lancer la suite complète : `cd backend && pytest tests/ -v --cov=app --cov-report=term-missing` → couverture ≥ 85 % sur le périmètre F03, aucune régression sur les tests existants.
- [ ] T067 Lancer Vitest frontend : `cd frontend && npm run test -- --coverage` → couverture ≥ 85 % sur le périmètre F03.
- [ ] T068 Lancer Playwright E2E : `cd frontend && npx playwright test tests/e2e/F03-audit-log.spec.ts` → 4 scénarios verts.
- [ ] T069 Vérification finale spec quality (checklist `specs/021-audit-log/checklists/requirements.md` complète à 100 %).

---

## Récapitulatif des dépendances

- Phase 1 (Setup) : libre (parallèle).
- Phase 2 (Foundational) : dépend de Phase 1. **Bloquante** pour toutes les User Stories.
- Phase 3 (US1 — reconstitution historique) : dépend de Phase 2.
- Phase 4 (US2 — transparence admin) : dépend de Phase 2 et Phase 3 (réutilise le mixin et le service).
- Phase 5 (US3 — export) : dépend de Phase 2 et Phase 3.
- Phase 6 (US4 — perf) : dépend de Phase 2, Phase 3 et Phase 5 (utilise les endpoints).
- Phase 7 (US5 — garantie) : dépend de Phase 2, Phase 3 et Phase 4.
- Phase 8 (Frontend) : dépend des Phases 5 et 7 (endpoints disponibles).
- Phase 9 (E2E) : dépend de Phases 3, 4, 5, 7, 8.
- Phase 10 (Documentation et Polish) : dépend de toutes les phases précédentes.
- Phase 11 (Validation finale) : dépend de Phase 10.

## Estimation effort

| Phase | Effort indicatif (h) |
|---|---|
| 1 — Setup | 2 |
| 2 — Foundational | 8 |
| 3 — US1 | 8 |
| 4 — US2 | 4 |
| 5 — US3 | 4 |
| 6 — US4 | 3 |
| 7 — US5 | 4 |
| 8 — Frontend | 10 |
| 9 — E2E | 4 |
| 10 — Doc & Polish | 3 |
| 11 — Validation | 2 |
| **Total** | **52 h ≈ 1.5 sprints** |
