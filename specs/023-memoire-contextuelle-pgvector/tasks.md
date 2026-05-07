---

description: "Task list F12 - Mémoire Contextuelle Conforme (15 messages bruts + pgvector + recall_history)"
---

# Tasks: F12 — Mémoire Contextuelle Conforme

**Input**: Design documents from `/specs/023-memoire-contextuelle-pgvector/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: TDD strict obligatoire (Constitution principe IV) — tests pytest et E2E Playwright écrits AVANT implémentation, couverture ≥ 80 %.
**Organization**: Tâches groupées par user story pour permettre l'implémentation et le test indépendants.

## Format

`- [ ] [TaskID] [P?] [Story?] Description avec chemin de fichier absolu`

- **[P]** : Peut s'exécuter en parallèle (fichier différent, pas de dépendance bloquante)
- **[USX]** : Lié à une user story (US1..US6)
- Les chemins sont relatifs à la racine du projet `/Users/mac/Documents/projets/2025/esg_mefali_v3/`.

---

## Phase 1 : Setup (Shared Infrastructure)

**Purpose** : Préparation de l'environnement et création des squelettes.

- [ ] T001 Vérifier le venv Python actif et `pgvector` extension installée : `cd backend && source venv/bin/activate && python -c "import pgvector; print(pgvector.__version__)"` ; au besoin, ajouter `pgvector>=0.3.0` à `backend/requirements.txt`.
- [ ] T002 Vérifier la disponibilité du extra LangGraph PostgreSQL : `python -c "from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver"` ; au besoin, ajouter `langgraph[postgres]>=0.2.0` à `backend/requirements.txt`.
- [ ] T003 [P] Créer la structure du module `backend/app/modules/memory/` avec un fichier vide `__init__.py`.
- [ ] T004 [P] Créer le dossier de tests `backend/tests/memory/` avec `__init__.py` vide.
- [ ] T005 [P] Créer le dossier `specs/023-memoire-contextuelle-pgvector/contracts/` (déjà fait par /speckit.plan, vérifier la présence des deux fichiers `memory_tools.md` et `memory_service.md`).

---

## Phase 2 : Foundational (Blocking Prerequisites)

**Purpose** : Migration BDD, modèle SQLAlchemy, refactor du checkpointer LangGraph. **Aucune** user story ne peut commencer avant la fin de cette phase.

**CRITIQUE** : Une seule migration Alembic en flight max (cf. `.cc-orchestrator.md` zone interdite). Sérialiser si conflit.

### Modèle & Migration

- [ ] T006 Créer le modèle SQLAlchemy `MessageChunk` dans `backend/app/models/message_chunk.py` selon le contrat `data-model.md` (UUIDMixin, account_id FK accounts, conversation_id FK conversations CASCADE, message_id FK messages CASCADE, chunk_index Integer default 0, role VARCHAR(20), chunk_text Text, embedding Vector(1536) nullable, created_at server_default now(), 2 CHECK constraints, index composite et index HNSW conditionnel pgvector).
- [ ] T007 Importer `MessageChunk` dans `backend/app/models/__init__.py` (si fichier d'import central) ou depuis `backend/app/db/base.py` pour qu'Alembic le voit.
- [ ] T008 Créer la migration Alembic `backend/alembic/versions/023_create_message_chunks.py` (revision='023_create_message_chunks', down_revision='022_money_and_versioning') : CREATE TABLE message_chunks + 3 indexes (composite, pending_embedding partial, HNSW) + RLS ENABLE+FORCE + 2 policies (admin_full_access, pme_access_own_account). Copier le pattern de `019_multitenant_and_roles.py` pour les policies RLS et de `163318558259_add_documents_tables.py` pour l'index HNSW. Downgrade : drop_index x3 + drop_table message_chunks.
- [ ] T009 Vérifier la migration : `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` ; vérifier qu'aucune erreur n'est levée et que la table apparaît dans `\d message_chunks`.

### Checkpointer LangGraph

- [ ] T010 Refactorer `backend/app/graph/checkpointer.py` : `create_checkpointer()` doit retourner un async context manager utilisable via `async with`, et exposer une fonction utilitaire `get_checkpointer_connection_string()` (déjà présente). Documenter le besoin d'`__aexit__` propre.
- [ ] T011 Modifier `backend/app/main.py` lifespan : remplacer l'initialisation MemorySaver implicite (dans `graph.py`) par une init unique `AsyncPostgresSaver` au startup, stockée dans `app.state.checkpointer` ; recompiler le graphe avec ce checkpointer ; `__aexit__` propre au teardown. Préserver la compatibilité avec les tests qui ne passent pas par lifespan (override via `Depends`).
- [ ] T012 Modifier `backend/app/graph/graph.py` : `create_compiled_graph(checkpointer=None)` accepte un checkpointer en argument ; si `None`, fallback sur `MemorySaver` (uniquement pour les contextes hors lifespan, ex. scripts CLI). Supprimer l'import `from langgraph.checkpoint.memory import MemorySaver` du chemin de production.

### Service mémoire — squelette

- [ ] T013 [P] Créer `backend/app/modules/memory/service.py` (squelette vide avec signatures `mask_secrets`, `chunk_text`, `embed_message`, `search_history`, `purge_account_chunks` documentées par docstrings).
- [ ] T014 [P] Créer `backend/app/modules/memory/hooks.py` (squelette : import de `event` et de `Message` ; un `set` module-level `_BACKGROUND_TASKS` pour conserver les références).

**Checkpoint** : Migration appliquée + reverse-up OK ; checkpointer AsyncPostgresSaver opérationnel ; squelettes du module memory en place.

---

## Phase 3 : User Story 1 — Reprise de conversation après redémarrage serveur (Priority: P1) MVP

**Goal** : Une conversation en cours survit à un redémarrage du backend (uvicorn restart, crash, scale).

**Independent Test** : Démarrer une conversation, envoyer 3 messages, redémarrer le processus uvicorn, envoyer un 4e message, vérifier que l'assistant connaît le contexte des messages 1-3.

### Tests pour User Story 1 (TDD obligatoire — écrire et faire échouer avant implémentation)

- [ ] T015 [P] [US1] Écrire `backend/tests/memory/test_checkpointer_persistence.py` :
  - `test_checkpoint_survives_session_close` : (a) crée un checkpoint via AsyncPostgresSaver `aput`, (b) ferme la session/connexion, (c) rouvre une nouvelle instance AsyncPostgresSaver, (d) `aget` le checkpoint et vérifie qu'il est intact.
  - `test_checkpoint_with_pending_interactive_question_restored` (couvre US1 AC3) : (a) crée un state ConversationState contenant une référence à une `InteractiveQuestion` en `pending`, (b) put-checkpoint, (c) close/reopen, (d) get → vérifier que le state restauré contient bien la même référence et que la résolution de la question fonctionne.
- [ ] T016 [P] [US1] Écrire `frontend/tests/e2e/F12-memoire-contextuelle-pgvector.spec.ts` scénario 1 (`test('US1 — conversation persists across backend restart')`) : utilise un mock de redémarrage backend (helper Playwright qui kill/restart le process uvicorn local OU stratégie alternative documentée si l'environnement CI ne le permet pas, ex. recréer les WS).
- [ ] T017 [US1] Lancer `pytest backend/tests/memory/test_checkpointer_persistence.py -v` et vérifier que le test ÉCHOUE (lifespan pas encore branché correctement).

### Implementation pour User Story 1

- [ ] T018 [US1] Implémenter le lifespan FastAPI dans `backend/app/main.py` : `async with create_checkpointer() as cp: ...` ; `app.state.checkpointer = cp` ; recompiler `app.state.compiled_graph = build_graph().compile(checkpointer=cp)` ; teardown propre.
- [ ] T019 [US1] Modifier `backend/app/api/chat.py` (et tout autre point d'entrée du graphe) pour utiliser `app.state.compiled_graph` au lieu d'instancier le graphe à chaque tour. Conserver `config={"configurable": {"thread_id": str(conversation_id)}}` pour que LangGraph indexe correctement.
- [ ] T020 [US1] Ré-exécuter `pytest backend/tests/memory/test_checkpointer_persistence.py -v` ; doit passer.

**Checkpoint** : US1 fonctionnel et testable indépendamment. Une conversation en cours résiste à un redémarrage.

---

## Phase 4 : User Story 2 — 15 derniers messages bruts en contexte (Priority: P1)

**Goal** : Le LLM reçoit les 15 derniers messages bruts de la conversation courante (en plus des 3 résumés déjà chargés), avec horodatages relatifs en français.

**Independent Test** : Conversation avec 17 messages → le 18e message est traité par le LLM avec un contexte contenant exactement les messages 3 à 17 inclus, formatés avec timestamps relatifs.

### Tests pour User Story 2 (TDD)

- [ ] T021 [P] [US2] Écrire `backend/tests/memory/test_chat_context_loader.py::test_loads_last_15_messages` : créer 17 messages en base, appeler `_load_context_memory`, vérifier qu'on récupère 15 messages (du 3e au 17e).
- [ ] T022 [P] [US2] Étendre `test_chat_context_loader.py::test_loads_all_messages_when_under_15` : créer 5 messages, vérifier que les 5 sont retournés (pas de padding artificiel).
- [ ] T023 [P] [US2] Étendre `test_chat_context_loader.py::test_format_relative_time` : tester `format_relative_time(now - 30 sec) == "à l'instant"`, `(now - 5 min) == "il y a 5 minutes"`, `(now - 3 h) == "il y a 3 heures"`, `(now - 30 h) == "hier"`, `(now - 5 j) == "il y a 5 jours"`, `(now - 35 j) == "le DD/MM/YYYY"`.
- [ ] T024 [P] [US2] Étendre `test_chat_context_loader.py::test_loads_3_summaries_first` : vérifier l'ordre du contexte chargé (3 résumés en tête, 15 messages bruts en queue).
- [ ] T025 [US2] Lancer `pytest backend/tests/memory/test_chat_context_loader.py -v` ; vérifier que les tests ÉCHOUENT (fonctions non implémentées).

### Implementation pour User Story 2

- [ ] T026 [US2] Ajouter le helper `format_relative_time(dt: datetime, now: datetime | None = None) -> str` dans `backend/app/api/chat.py` (ou un nouveau `backend/app/utils/time_format.py` si réutilisable ailleurs). Couvre les 6 cas (instant, min, h, hier, jours, date absolue).
- [ ] T027 [US2] Modifier `_load_context_memory(db, user_id, conversation_id)` dans `backend/app/api/chat.py` : ajouter le SELECT des 15 derniers messages de la conversation courante (`WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 15`, puis reverse), formater chaque message comme `[<relative_time>, <role>] <content>` et concaténer avec les 3 résumés (résumés en tête, messages en queue). Adapter la signature : `_load_context_memory` doit recevoir `conversation_id` (passé par le caller).
- [ ] T028 [US2] Mettre à jour les appelants de `_load_context_memory` dans `backend/app/api/chat.py` pour passer le `conversation_id` courant.
- [ ] T029 [US2] Ré-exécuter `pytest backend/tests/memory/test_chat_context_loader.py -v` ; doit passer.

**Checkpoint** : US2 fonctionnel et testable indépendamment. Le LLM voit les 15 derniers messages bruts + 3 résumés.

---

## Phase 5 : User Story 3 — Recherche d'historique via tool `recall_history` (Priority: P1)

**Goal** : Le LLM peut invoquer un tool LangChain `recall_history(query, max_results, since, include_current_conversation)` pour retrouver des passages anciens via recherche sémantique pgvector + HNSW.

**Independent Test** : Insérer 50 chunks indexés (mots clés « panneaux solaires » + fond « Green Climate Fund »), demander à l'assistant « tu te souviens du fonds pour mes panneaux solaires ? », vérifier que `recall_history` est invoqué et que le bon chunk remonte.

### Tests pour User Story 3 (TDD)

- [ ] T030 [P] [US3] Écrire `backend/tests/memory/test_service.py::test_chunk_text_short` : `chunk_text("court")` retourne `["court"]`.
- [ ] T031 [P] [US3] Étendre `test_service.py::test_chunk_text_just_under_limit` : 6 000 caractères → 1 chunk.
- [ ] T032 [P] [US3] Étendre `test_service.py::test_chunk_text_long_paragraphs` : 4 paragraphes × 2 600 c → 2+ chunks ≤ 6 200 c.
- [ ] T033 [P] [US3] Étendre `test_service.py::test_chunk_text_overlap` : 12 000 c → vérifier que les 200 derniers caractères du chunk 0 == les 200 premiers du chunk 1.
- [ ] T034 [P] [US3] Étendre `test_service.py::test_embed_message_success` : mock `OpenAIEmbeddings.aembed_documents` → vérifier 1 row insérée dans `message_chunks` avec embedding non nul.
- [ ] T035 [P] [US3] Étendre `test_service.py::test_embed_message_api_failure` : mock embedding qui lève `TimeoutError` → message indexé avec `embedding IS NULL` (pas d'exception remontée).
- [ ] T036 [P] [US3] Écrire `backend/tests/memory/test_hooks.py::test_after_insert_dispatches_task` : insérer un Message via SQLAlchemy → vérifier qu'`asyncio.create_task` a été appelée (mock `asyncio.create_task`).
- [ ] T037 [P] [US3] Écrire `test_hooks.py::test_no_loop_no_op` : appeler le hook hors event loop → no-op silencieux + log debug.
- [ ] T038 [P] [US3] Écrire `backend/tests/memory/test_recall_history_tool.py::test_recall_history_basic_success` : insérer 5 chunks (mockant l'embedding pour avoir des vecteurs déterministes), invoquer le tool avec une query proche → ≥ 1 résultat avec similarity > 0.6.
- [ ] T039 [P] [US3] Étendre `test_recall_history_tool.py::test_recall_history_threshold_filter` : query non pertinente → résultats vides.
- [ ] T040 [P] [US3] Étendre `test_recall_history_tool.py::test_recall_history_since_filter` : chunks anciens vs récents → seuls les récents (≥ since) remontent.
- [ ] T041 [P] [US3] Étendre `test_recall_history_tool.py::test_recall_history_include_current_conversation_flag` : 30 chunks dans conv_courante. Sans flag → 0 résultat de cette conv. Avec flag `true` → résultats incluent la conv courante.
- [ ] T042 [US3] Lancer `pytest backend/tests/memory/test_service.py backend/tests/memory/test_hooks.py backend/tests/memory/test_recall_history_tool.py -v` ; vérifier que les tests ÉCHOUENT.

### Implementation pour User Story 3

- [ ] T043 [US3] Implémenter `chunk_text(text, max_chars=6000, overlap=200)` dans `backend/app/modules/memory/service.py` selon le contrat `memory_service.md` : découpe par `\n\n`, fallback `. ! ?`, fallback mots ; recouvrement 200 c.
- [ ] T044 [US3] Implémenter `embed_message(message_id, account_id, conversation_id, role, content)` async dans `service.py` : ouvre session DB indépendante via `async_sessionmaker`, positionne RLS, applique `mask_secrets` (impl. T066 livrée en parallèle ou avant — si US5 pas encore terminée, livrer l'impl. minimale de `mask_secrets` ici en passthrough avec TODO), `chunk_text`, embed via `OpenAIEmbeddings(model="text-embedding-3-small")`, INSERT N rows ; try/except pour ne pas remonter d'exception. **Important** : pour respecter FR-012 (« masquage obligatoire »), la fonction `mask_secrets` doit être au moins définie avec une impl. minimale dès la livraison de US3 — `mask_secrets` complet est testé en US5 (T057-T065) et impl. en T066. Acceptable de stub `mask_secrets` à `text` (passthrough) **uniquement** si US3 est livré seul puis re-déployé après US5 ; en stratégie incrémentale recommandée, livrer US3 + US5 dans le même cycle.
- [ ] T045 [US3] Implémenter le hook `event.listens_for(Message, 'after_insert')` dans `backend/app/modules/memory/hooks.py` : récupérer event loop, dispatch `asyncio.create_task(embed_message(...))`, conserver référence dans `_BACKGROUND_TASKS` set, callback `discard` au done.
- [ ] T046 [US3] Importer `hooks.py` dans `backend/app/main.py` (au startup) pour activer les listeners SQLAlchemy.
- [ ] T047 [US3] Implémenter `search_history(...)` async dans `service.py` selon le contrat : embed la query, exécuter SQL avec `mc.embedding <=> :query_embedding`, filtres applicatifs `account_id`, `since`, `include_current_conversation`, `threshold > 0.6`, ORDER BY distance ASC LIMIT max_results. Retourne liste de `MessageRecallResult` (dataclass frozen).
- [ ] T048 [US3] Créer le tool LangChain `recall_history` dans `backend/app/graph/tools/memory_tools.py` : Pydantic v2 `RecallHistoryArgs` (query 2-500c, max_results 1-10 défaut 5, since datetime|None, include_current_conversation bool défaut False), `@tool(args_schema=RecallHistoryArgs)` async ; lit `account_id` et `current_conversation_id` depuis `state` (InjectedState) ; appelle `search_history` ; sérialise en list[dict] avec champ `relative_time` formaté.
- [ ] T049 [US3] Exporter `MEMORY_TOOLS = [recall_history]` depuis `backend/app/graph/tools/memory_tools.py` et ajouter l'import dans `backend/app/graph/tools/__init__.py`.
- [ ] T050 [US3] Modifier `backend/app/graph/tool_selector_config.py` :
  - Ajouter `"recall_history"` à `GLOBAL_WHITELIST`.
  - Porter `MAX_TOOLS_PER_TURN` de 13 à 14.
  - Mettre à jour le commentaire d'entête (« 10 métiers + 4 globaux = 14 »).
  - Re-exécuter `_validate_config()` (déjà appelé au load).
- [ ] T051 [US3] Modifier `backend/app/graph/graph.py` `build_graph()` : injecter `MEMORY_TOOLS` dans tous les `create_tool_loop` (chat, esg_scoring, carbon, financing, application, credit, action_plan).
- [ ] T052 [US3] Ré-exécuter les tests T030-T041 ; tous doivent passer.

**Checkpoint** : US3 fonctionnel. Le LLM peut invoquer `recall_history` et retrouver des passages anciens.

---

## Phase 6 : User Story 4 — Isolation stricte multi-tenant (Priority: P1)

**Goal** : Aucun chunk d'un account A ne remonte dans une recherche initiée par un utilisateur d'un account B, garantie par RLS PostgreSQL ET par filtre applicatif (défense en profondeur).

**Independent Test** : Insérer 100 chunks dans account A et 100 dans account B avec contenu identique « panneaux solaires ». Recall depuis A → 0 résultat de B (vérification SQL directe avec `SET app.current_account_id`).

### Tests pour User Story 4 (TDD)

- [ ] T053 [P] [US4] Écrire `backend/tests/memory/test_recall_history_tool.py::test_recall_history_rls_isolation_account_a_vs_b` : (a) créer 2 accounts A et B ; (b) insérer 50 chunks identiques dans A et 50 dans B ; (c) positionner `set_rls_context(session, A.id, role='PME', user_id=...)` ; (d) appeler `search_history(query, account_id=A.id)` ; (e) vérifier que tous les résultats ont `account_id == A.id`.
- [ ] T054 [P] [US4] Étendre le test précédent avec `test_recall_history_rls_postgres_level` : exécuter une requête SQL DIRECTE (sans WHERE applicatif) `SELECT COUNT(*) FROM message_chunks WHERE chunk_text LIKE '%panneaux%'` après `SET app.current_role = 'PME'; SET app.current_account_id = '<UUID_A>';` ; doit retourner uniquement les 50 chunks de A. Confirme que la RLS est active.
- [ ] T055 [US4] Lancer `pytest backend/tests/memory/test_recall_history_tool.py::test_recall_history_rls_isolation_account_a_vs_b -v` ; doit passer (les RLS policies de la migration T008 + le filtre applicatif T047 le couvrent déjà). Si échec, debug RLS + WHERE clause.

### Implementation pour User Story 4

> Implémentation déjà couverte par : RLS policies (T008), filtre applicatif `account_id` dans `search_history` (T047), helper `set_rls_context` (F02 pré-existant). Aucune nouvelle ligne de code requise — uniquement validation par tests.

- [ ] T056 [US4] Documenter dans `docs/memory-architecture.md` (section « Multi-tenant ») le principe de défense en profondeur : RLS PostgreSQL + filtre applicatif dans le service. Citer FR-022, FR-023, FR-024.

**Checkpoint** : US4 validé. Multi-tenant strict garanti à 2 niveaux.

---

## Phase 7 : User Story 5 — Masquage des secrets avant indexation (Priority: P2)

**Goal** : Les motifs sensibles (email, IBAN, carte bancaire valide Luhn, token Bearer) sont masqués dans le `chunk_text` indexé. Le message original (`messages.content`) reste intact.

**Independent Test** : Envoyer un message contenant les 4 motifs ; vérifier dans `message_chunks.chunk_text` que les marqueurs `[EMAIL]`, `[BANK]`, `[CARD]`, `[TOKEN]` remplacent les valeurs ; vérifier que `messages.content` est intact.

### Tests pour User Story 5 (TDD)

- [ ] T057 [P] [US5] Écrire `backend/tests/memory/test_service.py::test_mask_email` : `mask_secrets("écris à user@example.com") == "écris à [EMAIL]"`.
- [ ] T058 [P] [US5] Étendre `test_mask_iban` : IBAN FR76 ... → `[BANK]`.
- [ ] T059 [P] [US5] Étendre `test_mask_card_luhn_valid` : 4111 1111 1111 1111 (Luhn valide) → `[CARD]`.
- [ ] T060 [P] [US5] Étendre `test_mask_card_luhn_invalid` : 1234 5678 9012 3456 (Luhn invalide) → non masqué.
- [ ] T061 [P] [US5] Étendre `test_mask_token_bearer` : `Bearer abc123def456ghi789jklmnop` → `[TOKEN]`.
- [ ] T062 [P] [US5] Étendre `test_mask_combined` : message avec 4 motifs combinés → tous remplacés correctement.
- [ ] T063 [P] [US5] Étendre `test_mask_idempotent` : `mask_secrets(mask_secrets(t)) == mask_secrets(t)`.
- [ ] T064 [P] [US5] Étendre `test_mask_empty_after_redaction` : message ne contenant qu'un secret → après masquage, chunk_text vide → service stocke `'[redacted]'` (invariant data-model).
- [ ] T065 [US5] Lancer `pytest backend/tests/memory/test_service.py::test_mask_* -v` ; vérifier ÉCHEC (fonction non implémentée).

### Implementation pour User Story 5

- [ ] T066 [US5] Implémenter `mask_secrets(text: str) -> str` dans `backend/app/modules/memory/service.py` selon le contrat `memory_service.md` :
  - 4 regex compilées au load (constantes module-level pour perf).
  - Ordre d'application : tokens Bearer/API → email → IBAN → cartes Luhn (validation Luhn implémentée séparément).
  - Helper `_is_luhn_valid(digits: str) -> bool` interne.
  - Idempotence : les marqueurs `[TOKEN]`, `[EMAIL]`, `[BANK]`, `[CARD]` ne re-matchent aucune regex.
- [ ] T067 [US5] Brancher `mask_secrets` dans `embed_message` (modifie T044) : juste avant `chunk_text(masked)`.
- [ ] T068 [US5] Gérer le cas `mask_secrets(content) == ''` : remplacer par `'[redacted]'` avant chunking, conformément à l'invariant data-model.
- [ ] T069 [US5] Ré-exécuter les tests T057-T064 ; tous doivent passer.

**Checkpoint** : US5 fonctionnel. Aucun secret reconnu ne se retrouve indexé.

---

## Phase 8 : User Story 6 — Suppression cascade RGPD (Priority: P2)

**Goal** : `purge_account_chunks(account_id)` supprime tous les artefacts conversationnels d'un account : `message_chunks`, `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`. Aucune fuite résiduelle.

**Independent Test** : Créer un account A avec 50 chunks et 1 checkpoint LangGraph ; appeler `purge_account_chunks(A.id)` ; vérifier `count(message_chunks WHERE account_id=A) == 0` et `aget(checkpoint(thread_id=conv_a)) is None`.

### Tests pour User Story 6 (TDD)

- [ ] T070 [P] [US6] Écrire `backend/tests/memory/test_purge.py::test_purge_cascade_chunks` : 2 accounts (A 50 chunks, B 30 chunks) → `purge_account_chunks(A.id)` → `count_chunks(A) == 0` et `count_chunks(B) == 30`.
- [ ] T071 [P] [US6] Écrire `test_purge.py::test_purge_checkpoints_langgraph` : créer un conv_id, écrire un checkpoint via AsyncPostgresSaver `aput`, lier à un account A, `purge_account_chunks(A.id)` → `aget(thread_id=conv_id) is None`.
- [ ] T072 [P] [US6] Écrire `test_purge.py::test_purge_other_account_unaffected` : 2 accounts avec chunks et checkpoints → purge A → B intact.
- [ ] T072b [P] [US6] Écrire `test_purge.py::test_user_delete_does_not_purge_account_chunks` (couvre FR-027) : créer un account A avec 2 utilisateurs U1 et U2 et 50 chunks rattachés à des conversations de U1 et U2 ; supprimer U1 (`DELETE FROM users WHERE id = U1.id`) → vérifier que les chunks de l'account A restent intacts (count_chunks(A) == 50, conversations partagées préservées).
- [ ] T073 [US6] Lancer `pytest backend/tests/memory/test_purge.py -v` ; vérifier ÉCHEC.

### Implementation pour User Story 6

- [ ] T074 [US6] Implémenter `purge_account_chunks(account_id: uuid.UUID) -> None` async dans `backend/app/modules/memory/service.py` selon contrat `memory_service.md` : (a) ouvre session ; (b) positionne `set_rls_context` avec role='ADMIN' (la purge contourne PME) ; (c) récupère les `thread_id` (= conversation_id::text) des conversations de cet account via la jonction `users` ; (d) DELETE message_chunks WHERE account_id ; (e) DELETE checkpoint_blobs WHERE thread_id = ANY(:ids) ; (f) idem checkpoint_writes ; (g) idem checkpoints ; (h) commit.
- [ ] T075 [US6] Exporter `purge_account_chunks` depuis `backend/app/modules/memory/__init__.py` pour usage par F05 ultérieur.
- [ ] T076 [US6] Ré-exécuter `pytest backend/tests/memory/test_purge.py -v` ; tous doivent passer.

**Checkpoint** : US6 fonctionnel. Conformité RGPD effaçant les artefacts conversationnels en cascade.

---

## Phase 9 : E2E Playwright (4 scénarios = 4 user stories P1)

**Purpose** : Tests E2E exécutables couvrant les 4 user stories P1. Doivent tourner contre un backend + frontend lancés en local (cf. quickstart.md).

- [ ] T077 [P] Étendre `frontend/tests/e2e/F12-memoire-contextuelle-pgvector.spec.ts` (déjà créé en T016 pour US1) avec scénario US2 (`test('US2 — last 15 messages loaded in context')`) : login, créer une conversation, envoyer 17 messages, envoyer un 18e qui référence un détail du 7e → assistant répond correctement.
- [ ] T078 [P] Étendre la spec avec scénario US3 (`test('US3 — recall_history retrieves old messages')`) : (a) seed 30 chunks anciens contenant « panneaux solaires Green Climate Fund » via API helper ; (b) démarrer une nouvelle conversation ; (c) envoyer « tu te souviens du fonds pour mes panneaux solaires ? » ; (d) intercepter les events SSE et vérifier qu'`tool_call_start` avec `tool_name = 'recall_history'` est émis ; (e) vérifier que la réponse contient « Green Climate Fund ».
- [ ] T079 [P] Étendre la spec avec scénario US4 (`test('US4 — multi-tenant isolation in recall_history')`) : (a) seed 50 chunks similaires dans accountA et accountB ; (b) login en tant qu'utilisateur de A ; (c) déclencher recall_history ; (d) vérifier qu'aucun message_id de B n'apparaît dans les résultats (interception réseau ou seed-based check).
- [ ] T080 Lancer la suite E2E : `cd frontend && npx playwright test tests/e2e/F12-memoire-contextuelle-pgvector.spec.ts --reporter=html` ; les 4 scénarios doivent être verts (avec retries quarantaine x2 max).

---

## Phase 10 : Frontend mineur (indicateur visuel `recall_history`)

- [ ] T081 [P] Étendre `frontend/app/components/ToolCallIndicator.vue` : ajouter une case `recall_history` dans le mapping `toolName → label`, libellé français « Recherche dans l'historique de conversation… ». Conserver le dark mode (`dark:bg-...`, `dark:text-...`) en s'alignant sur les variantes existantes.
- [ ] T082 [P] Écrire un test Vitest `frontend/tests/components/ToolCallIndicator.spec.ts` (ou étendre l'existant) : monter le composant avec `tool_name = 'recall_history'` → vérifier que le texte attendu est rendu, et que les classes dark mode sont présentes.
- [ ] T083 Lancer `cd frontend && npm run test -- --coverage` ; vérifier que le test passe.

---

## Phase 11 : Polish & Cross-Cutting Concerns

### Observabilité (FR-028, FR-029, SC-007, SC-010)

- [ ] T083a [P] Ajouter dans `backend/app/graph/tools/memory_tools.py` un log structuré (JSON, niveau INFO) à chaque invocation de `recall_history` : `{"event": "recall_history_invoked", "account_id": ..., "conversation_id": ..., "user_id": ..., "max_results": ..., "results_count": ..., "duration_ms": ...}`. Le log est consommé par le pipeline d'observabilité standard du projet (FR-028).
- [ ] T083b [P] Ajouter dans `backend/app/modules/memory/service.py::embed_message` un log structuré à chaque embedding : `{"event": "message_embedded", "message_id": ..., "account_id": ..., "chunk_count": ..., "embedding_status": "success|failed|null", "duration_ms": ...}` (FR-029, SC-007).
- [ ] T083c [P] Écrire `backend/tests/memory/test_observability.py` : 2 tests vérifiant que les logs structurés sont émis avec les champs attendus (capture via `caplog` pytest fixture).

### Documentation et conformité

- [ ] T084 [P] Créer `docs/memory-architecture.md` : (a) decision tree (15 derniers / 3 résumés / recall_history) avec mermaid ; (b) schéma de flux du hook after_insert → embedding async ; (c) section « Multi-tenant » (cf. T056) ; (d) section « Masquage des secrets » (regex et ordre) ; (e) section « Suppression cascade RGPD » ; (f) section « Observabilité » (formats des logs T083a/b, métriques cibles SC-006/007/010) ; (g) liens vers les FR du spec.
- [ ] T085 [P] Mettre à jour `CLAUDE.md` section « Active Technologies » : ajouter une ligne pour 023-memoire-contextuelle-pgvector (déjà fait par T084 du script update-agent-context, vérifier). Section « Recent Changes » : ajouter un bloc concis F12.
- [ ] T086 Coverage backend complet : `cd backend && source venv/bin/activate && pytest tests/ -v --cov=app --cov-report=term-missing` ; viser ≥ 80 % global et ≥ 80 % spécifiquement sur `app/modules/memory/`, `app/graph/tools/memory_tools.py`, `app/graph/checkpointer.py`. Identifier et combler les trous éventuels par tests supplémentaires.
- [ ] T087 [P] Lint Python : `cd backend && source venv/bin/activate && python -m py_compile $(find app -name '*.py')` ; aucun warning.
- [ ] T088 Vérifier qu'aucun secret n'est hardcodé : `grep -rE '(api_key|secret|password|token)\s*=\s*["\047][A-Za-z0-9]' backend/ frontend/ | grep -v test | grep -v node_modules` ; ne doit rien retourner de neuf.
- [ ] T089 Vérifier la conformité aux invariants `.cc-orchestrator.md` :
  - Aucun nouveau chiffre/score/seuil non sourcé (F01) → aucun ajout métier ici, OK.
  - Toute nouvelle table métier `account_id` FK + RLS (F02) → message_chunks conforme.
  - Pas de mutation directe en chat → recall_history est lecture seule, OK.
  - Pas de secret hardcodé → vérifié T088.
- [ ] T090 Validation finale `quickstart.md` : exécuter manuellement la section 4 (US1), 5 (US2), 6 (US3), 7 (US4 manuel SQL) et 8 (tests automatisés). Cocher la checklist finale.
- [ ] T091 Tester la migration alembic up/down/up : `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` ; aucune erreur.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : démarrage immédiat.
- **Foundational (Phase 2)** : dépend de Setup. **Bloque toutes les user stories.** Une seule migration Alembic en flight (zone interdite).
- **User Stories (Phases 3-8)** : dépendent de Foundational.
  - US1 indépendant.
  - US2 indépendant (charge contexte ; aucun lien fonctionnel avec US1 même si elles vivent dans le même fichier `chat.py` — séparer les commits).
  - US3 dépend implicitement de la table `message_chunks` (Foundational T006-T009) ; **ne dépend PAS** des autres user stories.
  - US4 dépend de US3 (le tool `recall_history` doit exister) ET des RLS policies (Foundational T008).
  - US5 dépend de US3 (`mask_secrets` est branché dans `embed_message`).
  - US6 dépend de US3 (chunks à supprimer) et de Foundational (table créée).
- **E2E (Phase 9)** : dépend de US1, US2, US3, US4.
- **Frontend mineur (Phase 10)** : dépend de US3 (le tool est appelé en backend).
- **Polish (Phase 11)** : dépend de toutes les phases précédentes.

### User Story Dependencies (récap)

```text
Foundational
   ├── US1 (independant)
   ├── US2 (independant)
   ├── US3 (independant)
   │     ├── US4 (validation RLS via US3)
   │     ├── US5 (masquage branché dans US3)
   │     └── US6 (purge des chunks créés en US3)
```

### Within Each User Story (TDD obligatoire)

1. Écrire les tests (state RED) → vérifier qu'ils ÉCHOUENT.
2. Implémenter le minimum pour passer (state GREEN).
3. Refactor (state IMPROVE).
4. Vérifier coverage ≥ 80 %.

### Parallel Opportunities

- **Phase 1** : T003, T004, T005 en parallèle.
- **Phase 2** : T006, T010, T013, T014 en parallèle ; T007, T008 séquentiel après T006 ; T009 après T008.
- **US1** : T015, T016 en parallèle.
- **US2** : T021, T022, T023, T024 en parallèle (mêmes fichier mais tests indépendants → marqués [P]).
- **US3** : T030-T041 tous en parallèle (tests).
- **US4** : T053, T054 en parallèle.
- **US5** : T057-T064 tous en parallèle.
- **US6** : T070, T071, T072 en parallèle.
- **Phase 9** : T077, T078, T079 en parallèle (mais ajoutent dans le même fichier — sérialiser l'écriture si conflit).
- **Phase 10** : T081, T082 en parallèle.
- **Phase 11** : T084, T085, T087 en parallèle ; T086 séquentiel après tous les tests.

---

## Parallel Example : User Story 3 (TDD)

```bash
# Lancer tous les tests US3 en parallèle (TDD red phase) :
pytest backend/tests/memory/test_service.py::test_chunk_text_short \
       backend/tests/memory/test_service.py::test_chunk_text_just_under_limit \
       backend/tests/memory/test_service.py::test_chunk_text_long_paragraphs \
       backend/tests/memory/test_service.py::test_chunk_text_overlap \
       backend/tests/memory/test_service.py::test_embed_message_success \
       backend/tests/memory/test_service.py::test_embed_message_api_failure \
       backend/tests/memory/test_hooks.py \
       backend/tests/memory/test_recall_history_tool.py \
       -v

# Tous doivent ÉCHOUER avant implémentation (T030-T042).
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 + Phase 2 (Foundational : migration + checkpointer).
2. Phase 3 (US1 : reboot persistence).
3. **STOP & VALIDATE** : un reboot ne perd plus les conversations. Demo possible.

### Incremental Delivery

1. MVP (US1) → demo persistance.
2. + US2 (15 messages bruts) → demo qualité conversationnelle.
3. + US3 (recall_history) → demo recherche sémantique.
4. + US4 (validation multi-tenant) → demo sécurité.
5. + US5 (masquage secrets) → demo conformité RGPD.
6. + US6 (purge cascade) → demo droit à l'oubli complet.

### Parallel Team Strategy

Avec 3 développeurs après Foundational :
- Dev A : US1 + US2 (chat.py central).
- Dev B : US3 + US4 (service mémoire + tool LangChain + RLS).
- Dev C : US5 + US6 + Frontend (mask_secrets + purge + ToolCallIndicator).

Synchronisation finale Polish.

---

## Notes

- `[P]` = fichiers différents OU tests indépendants même fichier.
- `[USX]` mappe la tâche à une user story pour la traçabilité spec ↔ code.
- TDD strict : tous les tests doivent ÉCHOUER avant implémentation.
- Commits conventionnels : `feat(F12): <description>` ou `test(F12): <description>`.
- Validation finale : `quickstart.md` doit être 100 % vert.
- Aucune mutation `MAX_TOOL_CALLS_PER_TURN > 14` sans justification (cf. invariant `.cc-orchestrator.md`).
