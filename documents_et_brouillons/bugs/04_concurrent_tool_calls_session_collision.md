# Bug 04 — Collision de session SQLAlchemy quand le LLM invoque plusieurs tools en parallèle

## Symptôme

Lorsque le LLM (Claude Sonnet 4.6 via OpenRouter) invoque **plusieurs tools dans le même tour** (parallel tool calls — comportement natif de Claude 3.5+/4.x), un ou plusieurs tools échouent avec :

```
{"ok": false, "error": "This session is provisioning a new connection; concurrent operations are not permitted (Background on this error at: https://sqlalche.me/e/20/isce)"}
```

Reproduction dans cette session : un message envoyé sur `current_page=/profile/projects` a déclenché simultanément `get_user_dashboard_summary` et `list_projects`. Le second a échoué avec l'erreur ci-dessus, le premier a réussi. Le LLM a alors halluciné une réponse partielle (« la liste des projets est temporairement indisponible »).

Conséquence : tout flow agentique multi-tool devient **non déterministe** — un tool sur deux échoue selon l'ordre d'arrivée des coroutines sur la même `AsyncSession`.

## Cause racine (hypothèse à valider)

Tous les tools partagent la **même `AsyncSession`** (probablement injectée via `RunnableConfig` ou un singleton de scope conversation, cf. `backend/app/api/chat.py:1010-1028` qui passe une seule `sse_db` au graph). SQLAlchemy `AsyncSession` n'est **pas thread/coroutine-safe** : deux `await session.execute(...)` concurrents sur la même session lèvent `InvalidRequestError: This session is provisioning a new connection; concurrent operations are not permitted`.

Or LangGraph + ToolNode dispatchent les tool_calls de l'`AIMessage` **en parallèle via `asyncio.gather`** par défaut. Quand deux tools accèdent à la BDD, ils entrent en collision sur la session unique.

## Fichiers concernés

À **auditer** :

- `backend/app/api/chat.py:927-1100` — création/passage de la session SSE au graph
- `backend/app/graph/graph.py` — comment la session est injectée dans `RunnableConfig.configurable`
- `backend/app/graph/tools/*.py` — chaque tool : comment il récupère sa session DB (param injecté ? ouverture locale via `async_session_factory()` ?)
- `backend/app/graph/nodes.py:984, 1200, 1293, 1365, 1517, 1577, 1715, 1806, 1859, 1916, 2036` — sites `bind_tools` (vérifier si un `ToolNode` est utilisé avec parallélisme)
- LangGraph version installée (`backend/requirements.txt`) — vérifier l'option `parallel_tool_calls` du `ChatOpenAI` ou du `ToolNode`

## Solutions possibles

### Option A — Session par tool (recommandée)

Chaque tool ouvre sa propre `async_session_factory()` au début et la ferme à la fin. La session du graph (`sse_db`) ne sert qu'aux nodes (router, chat_node) et à la persistance des messages. Cela isole complètement la concurrence.

**Pour** : robuste, pattern standard ; aligné avec ce que `embed_message` fait déjà (`service.py:340`).
**Contre** : demande de modifier ~30 tools (mais souvent juste un wrapper `async with async_session_factory() as db:` autour du corps existant). Lourd côté diff.

### Option B — Désactiver le parallélisme côté LLM

Forcer `parallel_tool_calls=False` au binding :

```python
llm.bind_tools(tools, parallel_tool_calls=False)
```

OU au niveau ToolNode : passer un `ToolNode(..., handle_tool_errors=...)` configuré sequential.

**Pour** : 1-ligne, immédiat.
**Contre** : pénalise la latence (chaque tool attend le précédent), même quand ils sont indépendants. Régression UX par rapport au comportement natif Claude.

### Option C — Lock async sur la session

Wrapper la session dans un `asyncio.Lock` au niveau du `RunnableConfig` injecté. Chaque tool prend le lock avant `await session.execute(...)`.

**Contre** : équivaut à sérialiser → mêmes inconvénients que B mais avec plus de complexité. **À éviter**.

→ **Recommandé : Option A**. Si trop coûteux à court terme, **Option B comme mitigation tactique** en attendant.

## Tâche

1. **Reproduire le bug de façon déterministe** :
   - Créer un test `backend/tests/graph/test_parallel_tools.py` qui force le LLM à appeler 2 tools de lecture simultanément (ex: `get_user_dashboard_summary` + `list_projects`).
   - Le test doit échouer en l'état actuel sur l'erreur "concurrent operations are not permitted".

2. **Auditer la stratégie d'injection de session** :
   - Lister les tools qui prennent la session via `RunnableConfig.configurable["db"]` vs ceux qui ouvrent `async_session_factory()` localement.
   - Produire un tableau récapitulatif (tool | source de session | actions BDD).

3. **Implémenter l'Option A** (recommandée) :
   - Helper `async def _with_db(fn): async with async_session_factory() as db: return await fn(db)` à utiliser dans chaque tool.
   - Migrer les ~30 tools un par un, en gardant le même contrat d'API.
   - Conserver `RunnableConfig.configurable` pour `account_id`, `user_id`, `conversation_id` (pas pour la session).

4. **OU mitigation tactique Option B** (si l'option A est trop large) :
   - Modifier `get_llm()` dans `backend/app/graph/nodes.py:493` pour passer `parallel_tool_calls=False` au binding partout où `bind_tools` est appelé.
   - Documenter explicitement la régression de latence et ouvrir un ticket A pour la suite.

5. **Tests de non-régression** :
   - Créer 2-3 scénarios multi-tool dans `tests/graph/` qui valident que les tools ne se court-circuitent plus.
   - Round-trip `pytest backend/tests/ -v`.

## Critères d'acceptation

- [ ] Test de reproduction RED → GREEN après fix.
- [ ] Aucun message d'erreur "concurrent operations are not permitted" dans les logs uvicorn après une session de chat de 5+ messages avec tools.
- [ ] Si Option A : chaque tool ouvre/ferme proprement sa session (vérifier via le compteur de connexions BDD `pg_stat_activity` qu'il n'y a pas de fuite).
- [ ] Si Option B : tool calls toujours fonctionnels, juste séquentiels — vérifier via SSE qu'on voit bien `tool_call_start` → `tool_call_end` un par un.
- [ ] Pas de régression sur les tests F12, F23, F11 existants.
- [ ] RLS continue de fonctionner (la session ouverte dans chaque tool doit appeler `set_rls_context`).

## Notes

- Bug indépendant des bugs 01-03 mais découvert dans la même session de tests post-fix.
- Le bug n'est pas spécifique à Claude Sonnet 4.6 : tout LLM avec parallel tool calling natif (GPT-4o, Sonnet 3.5+) déclenchera le même symptôme. Minimax ne le déclenchait pas car il ne fait pas de tool calling natif (cf. session de tests précédente, `.env:18`).
- Vérifier en passant si `set_rls_context` est appelé sur la nouvelle session ouverte par les tools — sans ça, RLS bloquera silencieusement les SELECT.
- Lien doc SQLAlchemy : https://sqlalche.me/e/20/isce
