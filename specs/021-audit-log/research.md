# Research — F03 Audit Log Append-Only

## 1. SQLAlchemy event listener strategy

### Décision retenue : `event.listens_for(Session, 'before_flush')` global avec filtrage `isinstance(obj, Auditable)`

**Pourquoi** :
- Un seul listener centralisé, importé au démarrage de l'app (dans `app/main.py` ou `app/core/auditable.py`).
- L'event `before_flush` est le seul qui donne accès simultané à `session.new`, `session.dirty`, `session.deleted` ET à l'API `inspect(obj).attrs[<field>].history` (qui retourne `(added, unchanged, deleted)` pour chaque attribut, permettant de détecter les champs effectivement mutés).
- Compatible avec SQLAlchemy 2.x async (le listener s'enregistre sur `Session` synchrone sous-jacente accessible via `AsyncSession.sync_session`).
- L'insertion de `AuditLog` dans la même session garantit l'atomicité ACID : si la transaction métier rollback, l'audit_log rollback aussi.

**Alternatives rejetées** :
- **Décorateurs `@auditable_method` sur services** : trop intrusif (chaque service à décorer), facilement contournable (un dev qui ajoute un service oublie le décorateur), ne capte pas les mutations directes via session.
- **Events `before_insert` / `before_update` / `before_delete` sur Mapper** : déclenchent une fois par opération SQL et par instance, mais ne donnent pas une vue groupée de la transaction. La capture du `delete` perd accès à la valeur courante (l'objet est déjà détaché). Mauvais ergonomie pour un diff multi-attributs.
- **AOP via `__setattr__` override** : trop fragile, casse les performances ORM.
- **Triggers PostgreSQL `AFTER INSERT/UPDATE/DELETE` sur les 9 tables** : capturent au niveau DB mais perdent le contexte applicatif (qui = `user_id`, source = `manual`/`llm`, métadonnées). PostgreSQL a accès uniquement aux variables de session SET LOCAL — ContextVars Python invisibles. Solution mixte (trigger DB + service Python pour métadonnées) est complexe à maintenir.

**Sources** :
- [SQLAlchemy 2.0 docs — Session Events](https://docs.sqlalchemy.org/en/20/orm/session_events.html#before-flush)
- [SQLAlchemy AttributeState.history](https://docs.sqlalchemy.org/en/20/orm/internals.html#sqlalchemy.orm.AttributeState.history)

### 1.1 Détail implémentation listener

```text
@event.listens_for(Session, "before_flush")
def _capture_audit_log(session: Session, flush_context, instances) -> None:
    rows: list[dict[str, Any]] = []
    actor_id = _get_current_user_id_from_pg_context(session)  # via SET LOCAL F02
    source = current_source_of_change.get()  # ContextVar Python F03

    for obj in session.new:
        if isinstance(obj, AuditLog):
            continue
        if isinstance(obj, Auditable):
            rows.append(_make_create_row(obj, actor_id, source))

    for obj in session.dirty:
        if isinstance(obj, AuditLog):
            continue
        if isinstance(obj, Auditable):
            rows.extend(_make_update_rows(obj, actor_id, source))

    for obj in session.deleted:
        if isinstance(obj, AuditLog):
            continue
        if isinstance(obj, Auditable):
            rows.append(_make_delete_row(obj, actor_id, source))

    if rows:
        session.execute(insert(AuditLog), rows)
```

`_make_update_rows` itère sur `inspect(obj).attrs`, filtre les champs dont `history.has_changes()` est `True`, et produit une ligne par champ.

## 2. PostgreSQL triggers append-only

### Décision : trigger PL/pgSQL `BEFORE UPDATE OR DELETE` qui `RAISE EXCEPTION`

**Pourquoi** :
- Native PostgreSQL, pas de dépendance externe.
- `RAISE EXCEPTION` arrête la transaction proprement (rollback), avec un message lisible côté client.
- Trigger BEFORE = exécuté avant tout effet de bord, même par superuser (sauf si le superuser désactive le trigger, ce qui est explicite et auditable).

**Alternatives rejetées** :
- **CHECK constraint** : ne peut pas vérifier des conditions cross-row ni interdire UPDATE/DELETE (CHECK ne s'applique qu'aux INSERT/UPDATE et vérifie une expression sur la nouvelle ligne).
- **Vue avec `WITH CHECK OPTION`** : insuffisant car les vues n'interdisent pas les opérations sur la table sous-jacente.
- **Foreign Data Wrapper read-only** : trop lourd, complique la maintenance.

**Sources** :
- [PostgreSQL Trigger Procedures (PL/pgSQL)](https://www.postgresql.org/docs/16/plpgsql-trigger.html)
- Pattern courant : [Append-only audit table on PostgreSQL](https://supabase.com/blog/postgres-audit) (adapté à notre contexte).

## 3. REVOKE UPDATE, DELETE — limites

### Décision : tenter le REVOKE en migration ; journaliser un warning si rôle superuser/owner

**Pourquoi** :
- Le rôle applicatif utilisé par `database_url` est typiquement le owner du schéma (créé par les migrations Alembic). Owner conserve toujours les droits sur ses propres tables, REVOKE est no-op.
- En MVP, F02 a explicitement décidé de ne PAS introduire un rôle séparé `application_user`. Cohérence avec F03.
- Le trigger reste la défense effective dans ce cas. Le REVOKE devient barrière supplémentaire dès qu'un rôle séparé est introduit (post-MVP, documenté).

**Sources** :
- [PostgreSQL Privileges](https://www.postgresql.org/docs/16/ddl-priv.html) — `the owner of an object retains all privileges`.

### 3.1 Note migration

La migration journalise via `op.execute(...)` un `RAISE NOTICE` PostgreSQL si le `REVOKE` est tenté sur le owner :

```sql
DO $$
BEGIN
    BEGIN
        REVOKE UPDATE, DELETE ON audit_log FROM CURRENT_USER;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'REVOKE UPDATE, DELETE failed (rôle superuser/owner) : %. Trigger remains effective.', SQLERRM;
    END;
END $$;
```

## 4. ContextVar Python 3.12 + asyncio + LangGraph

### Décision : `contextvars.ContextVar` avec helper `source_of_change_scope` (context manager)

**Pourquoi** :
- Module stdlib Python 3.7+, supporté nativement par asyncio (chaque task asyncio capture/restaure son `Context`).
- FastAPI propage les ContextVars à travers les coroutines (validé en production sur de nombreux projets, notamment OpenTelemetry tracing).
- LangGraph utilise asyncio sous le capot — la ContextVar reste visible dans tous les nœuds tant que le `set` est dans le même `Context`.

**Validation** :
- Test unit `test_audit_context.py` : ouvrir 2 tasks asyncio en parallèle, chacune set une valeur différente, vérifier que les valeurs sont isolées par task (pas de fuite croisée).
- Test intégration : appel REST PME (`source=manual`) en parallèle d'un appel chat LLM (`source=llm`), vérifier que les audit_log respectifs ont la bonne `source_of_change`.

**Alternatives rejetées** :
- **`threading.local()`** : ne fonctionne pas en async (les coroutines partagent le même thread).
- **Argument explicite `source: str` passé à chaque service** : trop intrusif, casse la signature de tous les services métier existants. Goes against YAGNI/Simplicity.
- **Inspection de la stack frame** : fragile, contre-idiomatique (`sys._getframe`).

**Sources** :
- [PEP 567 — Context Variables](https://peps.python.org/pep-0567/)
- [contextvars — Python 3.12 docs](https://docs.python.org/3.12/library/contextvars.html)

## 5. Format CSV streaming UTF-8 BOM

### Décision : `StreamingResponse` FastAPI + générateur Python + `csv.writer` sur buffer + BOM en première ligne

**Pourquoi** :
- 100k lignes × ~500 octets/ligne = 50 MB ; le streaming évite de charger en mémoire.
- BOM UTF-8 (`﻿` en début de fichier) déclenche la détection automatique d'encodage par Microsoft Excel et préserve les accents français.
- `csv.writer` gère correctement les escape (virgules dans les valeurs, retours ligne, guillemets) — pas besoin d'écrire un CSV manuel.

**Pattern** :
```text
def _stream_csv(events: AsyncIterator[AuditEvent]) -> AsyncIterator[bytes]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    # BOM
    yield "﻿".encode("utf-8")
    # Header
    writer.writerow(["id", "timestamp", "user_email", "user_id", "account_id",
                     "entity_type", "entity_id", "action", "field",
                     "old_value", "new_value", "source_of_change", "actor_metadata"])
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0); buffer.truncate(0)
    # Rows
    async for event in events:
        writer.writerow([...])
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0); buffer.truncate(0)


@router.get("/me/export")
async def export_me(...):
    return StreamingResponse(
        _stream_csv(events),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=audit-log-{...}.csv"},
    )
```

**Validation** :
- Test unit : générer 1000 événements avec accents français, exporter, parser le CSV avec `csv.reader`, vérifier que les valeurs sont restituées intactes (`é`, `è`, `ç`).
- Test E2E Playwright : télécharger le CSV, ouvrir avec `fs.readFileSync` (Node.js), parser avec `csv-parse`, vérifier les accents.

**Sources** :
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [Python csv module](https://docs.python.org/3.12/library/csv.html)

## 6. Audit des tools LangChain qui font `db.commit()` direct

### Recensement initial

```bash
grep -rn "db.commit()\|session.commit()\|self.db.commit()" backend/app/graph/tools/
```

D'après l'audit code en cours, les tools qui font potentiellement `db.commit()` direct (à confirmer en Phase 2 d'implémentation) :

- `backend/app/graph/tools/profiling_tools.py` : `update_company_profile` — historiquement appelait `await db.commit()` après mise à jour ; à migrer vers `CompanyService.update`.
- `backend/app/graph/tools/esg_tools.py` : `save_esg_score`, `batch_save_esg_criteria` — à valider qu'ils passent par `ESGService`.
- `backend/app/graph/tools/application_tools.py` : `create_fund_application` — à valider.
- Autres tools (carbon_tools, credit_tools, action_plan_tools, financing_tools) : audit similaire.

### Décision : audit complet en Phase 2 (tasks.md), migration en deux temps

1. **Étape 1** : recensement précis (grep + analyse manuelle) → liste consignée.
2. **Étape 2** : migration tool par tool — chaque tool appelle désormais le service métier correspondant qui passe par la Session (et donc le mixin `Auditable`).
3. **Garde-fou test** : un test pytest qui simule l'invocation d'un tool LangChain et vérifie qu'au moins une ligne `audit_log` avec `source_of_change=llm` est créée.

## 7. Performance et indexes

### Benchmark cible

| Scénario | Cible P95 | Mesure |
|---|---|---|
| Insertion d'une mutation `update` sur 1 champ | overhead < 5 ms par mutation | benchmark CI |
| `GET /api/audit/me?page=1&limit=50` sur compte 100k lignes | < 500 ms P95 | benchmark CI |
| `GET /api/audit/me?entity_type=fund_application&since=...` | < 500 ms P95 | benchmark CI |
| Export CSV 100k lignes en streaming | First byte < 1 s, débit > 1 MB/s | benchmark CI |

### Indexes (rappel FR-004)

1. `(account_id, timestamp DESC)` : scrolling chronologique principal.
2. `(account_id, entity_type, entity_id)` : reconstituer historique d'une entité.
3. `(user_id, timestamp DESC)` : audit par acteur.
4. `(source_of_change, timestamp DESC)` : métriques admin.

Note : pas de `GIN` sur `actor_metadata` JSONB en MVP (overhead écriture). Si le besoin de filtrer par `actor_metadata.tool_name` apparaît à grande échelle, ajouter post-MVP un index `GIN (actor_metadata jsonb_path_ops)`.

## 8. Idempotence `view_admin`

### Décision : cache `request.state.audit_view_recorded: dict[UUID, bool]`

**Pourquoi** :
- FastAPI fournit `Request.state` comme namespace par-requête (réinitialisé à chaque requête entrante).
- Plusieurs sous-handlers (Depends, middleware) peuvent appeler `record_admin_view` pour le même `account_id` durant le traitement d'une seule requête ; on n'écrit qu'une trace.
- Pas besoin de Redis ni de cache externe — le cache est local à la requête.

**Pattern** :
```text
async def record_admin_view(
    admin_user: User,
    target_account_id: UUID,
    request: Request,
    db: AsyncSession,
) -> None:
    if not hasattr(request.state, "audit_view_recorded"):
        request.state.audit_view_recorded = {}
    if request.state.audit_view_recorded.get(target_account_id):
        return  # déjà tracé pour cette requête
    request.state.audit_view_recorded[target_account_id] = True

    audit = AuditLog(
        user_id=admin_user.id,
        account_id=target_account_id,
        entity_type="account",
        entity_id=target_account_id,
        action=AuditAction.view_admin,
        source_of_change=AuditSourceOfChange.admin,
        actor_metadata={
            "endpoint": str(request.url.path),
            "request_id": getattr(request.state, "request_id", None),
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    db.add(audit)
    await db.flush()
```

## 9. Compatibilité tests SQLite

### Décision : tests unitaires en SQLite (rapides) + tests d'intégration en PostgreSQL (pour triggers)

- **SQLite (`pytest tests/unit/`)** : pour le mixin, le ContextVar, les helpers de troncature, les schémas Pydantic, les services pure-Python. Très rapide.
- **PostgreSQL (`pytest tests/integration/`)** : pour les triggers `BEFORE UPDATE/DELETE`, RLS, et endpoints HTTP réels. Démarrage Docker Compose `postgres` requis (déjà présent dans le projet).

Le `conftest.py` projet bascule entre SQLite et PostgreSQL selon la variable d'env `TEST_DB=sqlite|postgres`. F03 préserve cette convention.

**Marquage pytest** :
```text
@pytest.mark.postgres
def test_audit_log_append_only_via_trigger(pg_session):
    ...

@pytest.mark.unit
def test_truncate_value_over_10kb():
    ...
```

## 10. Évolutions post-MVP documentées (hors-scope F03)

- **Hashing chaîné Merkle** : preuve d'intégrité forte (chaque ligne contient le hash de la précédente). Renforce la défense contre une migration future qui retirerait les triggers.
- **PDF signé Ed25519** : F08 fournira la signature ; F03 peut être référencé dans les rapports PDF (sourçage de l'intégrité du score).
- **Diff visuel side-by-side** dans l'UI : remplace l'affichage `old → new` textuel.
- **Webhooks change events** : intégration tierce (notification Slack/Email aux Admin lors d'événements critiques).
- **Partitionnement audit_log par mois** : si volumétrie > 1M lignes/compte, split table pour préserver la perf.
- **Mécanisme DPO (RGPD Art. 17)** : tombstone qui anonymise les valeurs personnelles tout en conservant l'événement et un hash.
- **Rôle PostgreSQL séparé `application_user`** : isolation réelle des privilèges, REVOKE effectif (pas no-op).
