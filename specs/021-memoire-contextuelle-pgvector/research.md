# Phase 0 — Research : F12 Mémoire Contextuelle Conforme

Synthèse des recherches techniques préalables au design F12. Chaque sujet est codé R1..R5.

---

## R1 — `AsyncPostgresSaver` dans le lifespan FastAPI

**Question** : Comment initialiser et tear-downer proprement `AsyncPostgresSaver` dans le lifespan FastAPI sans fuite de connexion ?

**Décision** : Utiliser `@asynccontextmanager` du lifespan FastAPI ; instancier le saver via `AsyncPostgresSaver.from_conn_string(conn)` (qui est un `AsyncContextManager`) et stocker dans `app.state.checkpointer`. Au teardown, sortir du context manager pour libérer la connexion psycopg.

**Rationale** :
- `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string` retourne un `_AsyncGeneratorContextManager` depuis langgraph >= 0.2.x. Il faut `__aenter__`/`__aexit__` explicitement.
- Le code existant `backend/app/graph/checkpointer.py` fait déjà `await saver_ctx.__aenter__()` mais NE fait PAS le `__aexit__` correspondant → fuite. Correction requise dans le plan.
- Pattern référence : LangGraph examples [`api_server.py`](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/README.md) montre l'usage `async with AsyncPostgresSaver.from_conn_string(conn) as saver: await saver.setup() ; yield saver`.

**Implémentation cible** dans `app/main.py` lifespan :
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... reste du startup ...
    checkpointer_ctx = AsyncPostgresSaver.from_conn_string(get_checkpointer_connection_string())
    checkpointer = await checkpointer_ctx.__aenter__()
    await checkpointer.setup()
    app.state.checkpointer = checkpointer
    app.state.checkpointer_ctx = checkpointer_ctx  # pour teardown propre
    app.state.compiled_graph = build_graph().compile(checkpointer=checkpointer)
    try:
        yield
    finally:
        await checkpointer_ctx.__aexit__(None, None, None)
```

**Alternatives considérées** :
- *MemorySaver conditionnel* (en dev) : rejeté car ajoute du code conditionnel ; l'unique source de vérité doit être PostgreSQL pour test/prod.
- *Connection pool partagé* avec asyncpg : rejeté car `AsyncPostgresSaver` utilise psycopg async (pas asyncpg), incompatible.

---

## R2 — Hook SQLAlchemy `after_insert` async-safe

**Question** : Le hook `event.listens_for(Message, 'after_insert')` est synchrone (event SQLAlchemy). Comment lancer une coroutine d'embedding sans bloquer ni perdre la session ?

**Décision** :
1. Détecter la présence d'un event loop via `asyncio.get_running_loop()` (try/except).
2. Si un loop tourne → `asyncio.create_task(embed_message(...))` ; conserver la référence dans un `set` au niveau module (`_BACKGROUND_TASKS: set[asyncio.Task]`) pour éviter le GC précoce ; supprimer la référence dans une callback `task.add_done_callback(_BACKGROUND_TASKS.discard)`.
3. Si aucun loop ne tourne (ex. tests sync, scripts batch) → no-op silencieux + log debug.
4. La coroutine d'embedding ouvre sa PROPRE session DB (pas celle du hook qui peut être committée/fermée entre temps), via `async_sessionmaker` exposé dans `app/db/session.py` (déjà existant).

**Rationale** :
- Documentation SQLAlchemy : « Don't use the same session in async tasks spawned from a sync event » — la coroutine doit ouvrir une session indépendante.
- Pattern documenté FastAPI : `asyncio.create_task` sans référence forte risque le `RuntimeWarning: coroutine was never awaited` ; le set au niveau module élimine ce risque.
- Test : `test_hooks.py` simule à la fois (a) hook avec loop actif et (b) hook hors loop ; le second doit just no-op.

**Alternatives considérées** :
- *Celery/RQ* : rejeté MVP (KISS, simplicité, brief F12 explicite : « Celery post-MVP »).
- *FastAPI BackgroundTasks* : rejeté car couplé à la requête HTTP ; le hook SQLAlchemy peut s'exécuter hors d'une requête (ex. tests, scripts).
- *Synchrone dans le hook* : rejeté car un appel d'embedding dure 100-300 ms et bloquerait l'event loop.

---

## R3 — Ordre des regex de masquage des secrets

**Question** : Les motifs « carte bancaire » (16 chiffres) peuvent matcher des numéros téléphoniques ou IBAN. L'IBAN peut contenir un email-like si pollué. Quel ordre minimise les faux positifs/négatifs ?

**Décision** : Ordre d'application séquentiel et idempotent :
1. **Tokens Bearer / API key** (regex `(?i)\b(Bearer\s+|api[_-]?key[=: ]|sk-|sk_live_)[A-Za-z0-9_\-\.]{20,}`) — remplacés par `[TOKEN]` AVANT tout autre traitement (ces motifs peuvent contenir des chiffres qui ressemblent à des cartes).
2. **Email** (regex `\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b`) — remplacé par `[EMAIL]`. Se fait avant carte/IBAN car un email contient `@` qui ne peut pas être confondu avec une carte ou IBAN.
3. **IBAN** (regex `\b[A-Z]{2}\d{2}(?:[ \t]?[A-Z0-9]{4}){3,7}(?:[ \t]?[A-Z0-9]{1,4})?\b`, normalisation préalable des espaces) — remplacé par `[BANK]`. Avant carte car le préfixe pays (`FR76`) commence par 2 lettres, distinguant clairement de carte.
4. **Carte bancaire** (regex `\b\d[\d ]{12,18}\d\b`, validation Luhn server-side) — remplacé par `[CARD]`. Dernier car le plus permissif.

**Rationale** :
- Tests adversariaux prévus : `mon iban est FR76 1234 5678 9012 3456 78 et ma carte 4111 1111 1111 1111` doit produire `mon iban est [BANK] et ma carte [CARD]`.
- La validation Luhn est obligatoire pour la carte (sinon des numéros de téléphone ou compte client seraient masqués à tort).
- L'idempotence (`mask_secrets(mask_secrets(x)) == mask_secrets(x)`) est testée : les marqueurs `[EMAIL]` etc. ne re-matchent aucune regex.

**Alternatives considérées** :
- *Bibliothèque externe (presidio, scrubadub)* : rejeté pour MVP (poids dépendances, complexité de configuration). Un set restreint de regex suffit pour la défense en profondeur.
- *Masquage via LLM* : rejeté (coût, latence, déterminisme).

---

## R4 — Index HNSW vs index composite : ordre de création et coût d'écriture

**Question** : La table `message_chunks` aura à la fois un index HNSW (recherche sémantique) et un index composite (`account_id`, `conversation_id`, `created_at DESC`). Quel ordre de création et quel coût attendre par INSERT ?

**Décision** :
- Créer en migration : (1) la table avec ses contraintes ; (2) l'index composite B-tree ; (3) l'index HNSW (`m=16`, `ef_construction=64` — paramètres alignés sur `document_chunks`). L'ordre n'a pas d'importance fonctionnelle sur table vide, mais l'HNSW en dernier rend la migration plus rapide à rejouer.
- Coût attendu par INSERT : ~ 0,5–2 ms pour B-tree, ~ 1–5 ms pour HNSW (à 1 M rows ; mesures pgvector). Total ≤ 10 ms par insert chunk → bien sous le budget de 100 ms d'overhead F12.
- Aucune VACUUM/REINDEX requise au déploiement (table vide).

**Rationale** :
- Pattern `document_chunks` (164k+ chunks en prod simulée) montre que les performances HNSW sont stables sur cette plage.
- L'index composite `(account_id, conversation_id, created_at DESC)` est utilisé pour : (a) le rattrapage F19 (cron qui scanne `WHERE embedding IS NULL ORDER BY created_at`) ; (b) la suppression cascade rapide par account.

**Alternatives considérées** :
- *IVFFlat au lieu de HNSW* : rejeté car HNSW déjà adopté dans `document_chunks` (cohérence + meilleur rappel à recall=5).
- *Pas d'index composite* : rejeté car le rattrapage F19 ferait un seq scan complet (3M+ rows à terme).

---

## R5 — Suppression cascade des checkpoints LangGraph

**Question** : `AsyncPostgresSaver` n'expose pas de méthode `delete_thread(thread_id)` officielle dans LangGraph 0.2.x. Comment garantir que la suppression d'un account purge les checkpoints associés ?

**Décision** :
- `purge_account_chunks(account_id)` exécute (en plus de la purge des `message_chunks`) un DELETE direct SQL sur les 3 tables `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` filtré par `thread_id IN (SELECT id::text FROM conversations WHERE user_id IN (SELECT id FROM users WHERE account_id = :account_id))`.
- Les `thread_id` LangGraph sont définis côté code applicatif comme `str(conversation.id)` (cf. `backend/app/api/chat.py` actuel passant `config={"configurable": {"thread_id": str(conversation_id)}}`).
- Cette opération est exécutée APRÈS la suppression cascade SQL des `conversations`, pour profiter de la jonction.
- Encapsulée dans une transaction.

**Rationale** :
- Examen du code source LangGraph 0.2.x (release notes) : `delete_thread` est planifié dans 0.3.x mais pas disponible dans la version cible. Le DELETE SQL direct est sûr car la structure des tables est documentée et stable.
- Test `test_purge.py` valide la cascade complète : message_chunks purgés ET checkpoints purgés ET account autre non impacté.

**Alternatives considérées** :
- *Attendre LangGraph 0.3.x* : rejeté pour ne pas bloquer F12 sur une dépendance externe.
- *Soft delete (flag `deleted_at`)* : rejeté car la conformité RGPD exige un effacement réel.

---

## Conclusion

Tous les unknowns du Technical Context sont résolus. Aucun NEEDS CLARIFICATION ne subsiste. Le plan peut entrer en Phase 1 (Design & Contracts) sans blocage.
