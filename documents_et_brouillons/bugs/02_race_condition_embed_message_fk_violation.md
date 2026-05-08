# Bug 02 — Race condition `embed_message` : `ForeignKeyViolationError` sur `message_chunks`

## Symptôme

Dans les logs uvicorn, après chaque envoi de message dans le chat :

```
embed_message a échoué pour message <uuid> : (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError)
<class 'asyncpg.exceptions.ForeignKeyViolationError'>: insert or update on table "message_chunks"
violates foreign key constraint "message_chunks_message_id_fkey"
DETAIL:  Key (message_id)=(<uuid>) is not present in table "messages".
```

Le request HTTP retourne quand même 200 OK et le SSE fonctionne (best-effort). Mais **aucun row n'est inséré dans `message_chunks`** → la mémoire contextuelle F12 est doublement cassée (en plus du bug 01).

## Cause racine

Fichier `backend/app/modules/memory/hooks.py` :

```python
@event.listens_for(Message, "after_insert")
def _on_message_after_insert(mapper, connection, target):
    ...
    task = asyncio.create_task(embed_message(...))
```

L'event `after_insert` se déclenche **pendant le flush** de la transaction A (avant le COMMIT). À ce moment :

1. Le `Message` est inséré dans la connexion de la transaction A (visible uniquement à l'intérieur de A).
2. `asyncio.create_task(embed_message(...))` planifie l'exécution de la coroutine.
3. La coroutine `embed_message` ouvre **une nouvelle session** (B) via `async_session_factory()` (cf. `service.py:344-347`).
4. La session B démarre une nouvelle transaction → elle ne voit pas le `Message` non encore committé de A (read committed isolation par défaut).
5. L'INSERT dans `message_chunks` avec `message_id = <uuid>` échoue → `ForeignKeyViolationError`.

C'est une race condition classique entre `after_insert` (pre-commit) et un dispatch async qui ouvre sa propre transaction.

## Fichiers concernés

- `backend/app/modules/memory/hooks.py` — listener SQLAlchemy (à corriger)
- `backend/app/modules/memory/service.py:285-365` — fonction `embed_message`
- `backend/app/api/chat.py:927-933, 1059-1064` — sites de création `Message` (lecture seule)
- Tests : `backend/tests/modules/memory/`

## Solutions possibles

### Option A — Recommandée : `after_commit` au niveau Session

Remplacer le listener `after_insert` sur `Message` par un listener `after_commit` sur la session SQLAlchemy. Au flush, mémoriser les `Message` insérés ; au commit, dispatcher les embeddings.

```python
# hooks.py
from sqlalchemy import event
from sqlalchemy.orm import Session

_PENDING_EMBEDDINGS: ContextVar[list[dict]] = ContextVar("pending_embeddings", default=[])


@event.listens_for(Session, "after_flush")
def _capture_pending(session, flush_context):
    for obj in session.new:
        if isinstance(obj, Message) and obj.account_id is not None:
            _PENDING_EMBEDDINGS.get().append({
                "message_id": obj.id,
                "account_id": obj.account_id,
                "conversation_id": obj.conversation_id,
                "role": obj.role,
                "content": obj.content,
            })


@event.listens_for(Session, "after_commit")
def _dispatch_embeddings(session):
    pending = _PENDING_EMBEDDINGS.get()
    if not pending:
        return
    for payload in pending:
        task = asyncio.create_task(embed_message(**payload))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    _PENDING_EMBEDDINGS.set([])
```

**Avantages** :
- Le `Message` est COMMITTÉ avant que `embed_message` ouvre sa session B → la FK est résoluble.
- Garde le pattern best-effort + asyncio.create_task.
- Pas de modification du schéma BDD.

**Attention** :
- L'event `after_commit` au niveau Session SQLAlchemy peut ne pas être déclenché en mode async (`AsyncSession`). Vérifier que le listener s'attache au `Session` synchrone sous-jacent (`AsyncSession.sync_session` ou listener sur `Session` global).
- Tester avec SQLite in-memory (tests) ET PostgreSQL réel.

### Option B — Pre-loaded fallback dans `embed_message`

Garder `after_insert` mais ajouter un mécanisme de retry avec backoff dans `embed_message` (max 3 tentatives, 100ms entre chaque). Si après retry le `Message` n'est toujours pas visible, abandonner silencieusement.

**Inconvénients** : retry contre la BDD, ajoute de la latence, masque la vraie cause. **À éviter**.

### Option C — Passer la session de l'API à `embed_message`

Modifier le listener pour ne pas ouvrir une nouvelle session : utiliser la session de la transaction courante (via `target._sa_instance_state.session`). Mais asyncio.create_task lance la coroutine en parallèle → la session peut être déjà fermée. Compliqué.

→ **Choisir Option A**.

## Tâche

1. **Implémenter Option A** dans `backend/app/modules/memory/hooks.py` :
   - Remplacer `@event.listens_for(Message, "after_insert")` par 2 listeners sur `Session` (`after_flush` + `after_commit`).
   - Vérifier que le listener fonctionne avec `AsyncSession` (s'attacher à la `sync_session` ou à `Session` global).
   - Conserver le `_BACKGROUND_TASKS` set pour éviter le GC précoce.

2. **Conserver le no-op si aucun event loop** (cas tests sync, scripts batch) — log debug seulement.

3. **Mettre à jour le docstring** de `hooks.py` pour refléter le pattern `after_commit`.

4. **Tests** :
   - `backend/tests/modules/memory/test_hooks.py` (créer si absent) : insérer un `Message` via session async, commit, vérifier qu'un row `message_chunks` est créé (mock `embed_message` ou vérifier en vraie BDD avec OPENAI_API_KEY de test).
   - Reproduire le bug AVANT le fix : test qui prouve le `ForeignKeyViolationError` en mode `after_insert`.
   - Vérifier que les tests existants F12 passent : `pytest backend/tests/modules/memory/ -v`.

## Critères d'acceptation

- [ ] Après envoi d'un message via `/api/chat/conversations/{id}/messages`, **aucun** `ForeignKeyViolationError` dans les logs.
- [ ] Vérifier en BDD : `SELECT count(*) FROM message_chunks WHERE message_id IN (<derniers Messages>)` > 0 pour chaque message inséré (avec OPENAI_API_KEY valide).
- [ ] Si OPENAI_API_KEY vide (bug 01 non corrigé) : chunks insérés avec `embedding=NULL` mais **rows présents** (FK respectée).
- [ ] Tests existants passent.
- [ ] Round-trip `pytest backend/tests/` global vert.
- [ ] Aucun changement de schéma BDD (pas de migration Alembic).

## Notes

- Bug indépendant du bug 01 : peut être corrigé séparément. Mais la combinaison des deux est nécessaire pour que F12 (recall_history) fonctionne réellement.
- Le `try/except` autour du `await sess.commit()` dans `embed_message` (cf. `service.py:362`) absorbe l'exception → le client ne voit rien. C'est pour ça que le chat continue de fonctionner. NE PAS retirer ce try/except — best-effort F12 est intentionnel.
- Vérifier qu'il n'y a pas d'autres endroits qui créent des `Message` (grep `Message(` hors classe) — si oui, le pattern `after_commit` les couvre toutes (contrairement à un fix manuel par site).
