# Implementation Plan: F12 — Mémoire Contextuelle Conforme (15 messages bruts + pgvector + recall_history)

**Branch**: `feat/F12-memoire-contextuelle-pgvector` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/023-memoire-contextuelle-pgvector/spec.md`

## Summary

F12 corrige trois lacunes critiques du module conversationnel :

1. **Persistance** — le checkpointer LangGraph passe de `MemorySaver` (RAM volatile) à `AsyncPostgresSaver` (PostgreSQL durable). Tout redémarrage du backend préserve désormais les conversations en cours.
2. **Contexte récent** — `_load_context_memory` injecte les 15 derniers messages bruts (en plus des 3 résumés actuels), avec horodatages relatifs en français.
3. **Recherche sémantique** — nouvelle table `message_chunks` (pgvector + HNSW) indexe chaque message au fil de l'eau via un hook SQLAlchemy `after_insert` exécuté en `asyncio.create_task` détaché. Le tool LangChain `recall_history(query, max_results, since, include_current_conversation)` permet au LLM de retrouver des passages anciens. Filtrage RLS strict par `account_id` (F02) + masquage server-side des secrets (email, IBAN, cartes bancaires Luhn, tokens) avant indexation.

Approche technique : réutilisation maximale du pattern existant `document_chunks` (modèle `pgvector.Vector`, index HNSW `vector_cosine_ops`, RLS), du checkpointer déjà préparé dans `app/graph/checkpointer.py`, et du stack d'embedding (`text-embedding-3-small` via `langchain-openai`). Aucune nouvelle dépendance majeure — `langgraph[postgres]` extras déjà installés au regard de `checkpointer.py`.

## Technical Context

**Language/Version**: Python 3.12 (backend) ; TypeScript 5.x strict (frontend)
**Primary Dependencies**:
- Backend : FastAPI, SQLAlchemy 2.x async (asyncpg), Alembic, langchain-core ≥ 0.3, langchain-openai ≥ 0.3, langgraph ≥ 0.2 + extras `postgres` (psycopg async), pgvector (sqlalchemy bindings), pydantic v2
- Frontend : Nuxt 4, Vue Composition API, Pinia, TailwindCSS 4
- E2E : Playwright (`@playwright/test`)
- Tests backend : pytest, pytest-asyncio, pytest-cov

**Storage**: PostgreSQL 16 + extension pgvector. Nouvelle table `message_chunks` ; tables `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` créées par `AsyncPostgresSaver.setup()` (cf. README LangGraph). RLS PostgreSQL active (helper F02 `set_rls_context`).

**Testing**:
- Backend : pytest (suite `backend/tests/memory/` + ajouts ciblés dans `backend/tests/integration/`)
- Frontend : Vitest pour composables et composants
- E2E : Playwright `frontend/tests/e2e/F12-memoire-contextuelle-pgvector.spec.ts`

**Target Platform**: Linux server (Docker Compose en dev, Linux x86_64 en production). Pas de support mobile spécifique au backend.

**Project Type**: Web application (backend FastAPI + frontend Nuxt 4 + PostgreSQL).

**Performance Goals**:
- Overhead F12 sur le tour de chat principal : p99 < 100 ms (mesuré en backend, hors latence LLM).
- Embedding async : best-effort (timeouts tolérés, retry délégué à F19) ; ne bloque pas l'envoi de la réponse.
- `recall_history` : recherche HNSW sur ~3 M chunks attendus à 1 an → temps p95 < 50 ms (validé par le pattern `document_chunks` existant).
- AsyncPostgresSaver : write checkpoint p95 < 30 ms (psycopg async + 1 connexion pool dédiée).

**Constraints**:
- Aucun secret hardcodé (chaîne de connexion via `settings.database_url`, clé d'embedding via `settings.openrouter_api_key` déjà existante).
- RLS PostgreSQL forcée via `set_rls_context` (héritage F02). Aucune écriture/lecture directe `message_chunks` hors d'un contexte RLS positionné.
- Conformité RGPD : suppression cascade obligatoire au niveau base de données (`ON DELETE CASCADE` sur `message_id` ; suppression manuelle des checkpoints LangGraph via `purge_account_chunks` qui appelle aussi le helper de purge LangGraph).
- Masquage des secrets server-side, idempotent.

**Scale/Scope**:
- Cible MVP : 1 000 PME × 10 messages / jour × 365 jours ≈ 3,65 M chunks / an → bien dans les capacités HNSW (validé < 10 M rows).
- Conversations actives simultanées : ~50 attendues au pic MVP.
- Taille typique d'un message : 100–500 caractères (1 chunk) ; messages très longs (collage de document) : jusqu'à 50 chunks chacun, fréquence rare.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Conformité F12 | Justification |
|---|---|---|
| **I. Francophone-First & Contextualisation Africaine** | PASS | Format des horodatages en français (« il y a N minutes », « hier », « le DD/MM/YYYY »). Docstring `recall_history` rédigée en français. Documentation `docs/memory-architecture.md` en français. Aucun impact sur taxonomies UEMOA/BCEAO. |
| **II. Architecture Modulaire** | PASS | Nouveau module isolé `app/modules/memory/` (service, hooks, models). Tools LangChain dans `app/graph/tools/memory_tools.py`. Couplage faible : seul le hook SQLAlchemy `Message.after_insert` réagit à l'extérieur du module. |
| **III. Conversation-Driven UX** | PASS | F12 améliore explicitement la mémoire contextuelle, principe central de cette ligne directrice. La persistance des conversations entre sessions est désormais garantie. |
| **IV. Test-First (NON-NEGOTIABLE)** | PASS | Tests pytest unitaires + intégration + E2E Playwright écrits avant implémentation (TDD strict). Couverture cible >= 80 % sur le module mémoire (validé par SC-009). |
| **V. Sécurité & Protection des Données** | PASS | Aucun secret hardcodé. Validation Pydantic v2 sur `RecallHistoryArgs`. Requêtes paramétrées SQLAlchemy. RLS PostgreSQL strict. Masquage server-side des secrets avant embedding (FR-012). Suppression cascade RGPD. |
| **VI. Inclusivité & Accessibilité** | PASS | Pas d'impact UI nouveau (sauf indicateur facultatif texte « Recherche dans l'historique... » en français, dark mode, ARIA conservés). Performance préservée (p99 < 100 ms d'overhead). |
| **VII. Simplicité & YAGNI** | PASS | Réutilise les patterns existants (`document_chunks`, `pgvector.Vector`, `Index HNSW`, helper RLS F02). Pas de Celery au MVP : `asyncio.create_task` suffit. Pas de cache court terme `recall_history` (déféré tant que SC-010 n'alerte pas). Pas de scheduler intégré : F19 prendra la purge nocturne. |

**Résultat** : Tous les gates passent. Aucune justification de violation requise.

## Project Structure

### Documentation (this feature)

```text
specs/023-memoire-contextuelle-pgvector/
├── plan.md              # Ce fichier
├── spec.md              # Spécification fonctionnelle (déjà écrite)
├── research.md          # Phase 0 (généré ci-dessous)
├── data-model.md        # Phase 1 (généré ci-dessous)
├── quickstart.md        # Phase 1 (généré ci-dessous)
├── contracts/
│   ├── memory_tools.md          # Contrat LangChain @tool recall_history
│   └── memory_service.md        # Contrat service interne (embed, search, purge)
├── checklists/
│   └── requirements.md          # Quality checklist (déjà écrit)
└── tasks.md             # Phase 2 (généré par /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
│       └── 023_create_message_chunks.py        # NEW (migration F12)
├── app/
│   ├── api/
│   │   └── chat.py                             # MODIF (_load_context_memory + format_relative_time)
│   ├── core/
│   │   └── config.py                           # MODIF mineure (ajout MEMORY_EMBEDDING_TIMEOUT_SECONDS si requis)
│   ├── graph/
│   │   ├── checkpointer.py                     # MODIF (helper async context manager + close)
│   │   ├── graph.py                            # MODIF (utilisation AsyncPostgresSaver, injection MEMORY_TOOLS)
│   │   └── tool_selector_config.py             # MODIF (ajout recall_history à GLOBAL_WHITELIST + relèvement borne)
│   ├── graph/tools/
│   │   ├── __init__.py                         # MODIF (export MEMORY_TOOLS)
│   │   └── memory_tools.py                     # NEW (@tool recall_history + RecallHistoryArgs)
│   ├── main.py                                 # MODIF (lifespan : init/teardown checkpointer)
│   ├── models/
│   │   └── message_chunk.py                    # NEW (modèle SQLAlchemy MessageChunk)
│   └── modules/
│       └── memory/
│           ├── __init__.py                     # NEW
│           ├── service.py                      # NEW (embed_message, search_history, mask_secrets, chunk_text, purge_account_chunks)
│           └── hooks.py                        # NEW (event.listens_for(Message, 'after_insert'))
├── tests/
│   └── memory/                                 # NEW
│       ├── __init__.py
│       ├── test_service.py                     # NEW (mask_secrets, chunk_text, embed_message)
│       ├── test_hooks.py                       # NEW (after_insert dispatch)
│       ├── test_recall_history_tool.py         # NEW (tool LangChain + RLS)
│       ├── test_chat_context_loader.py         # NEW (_load_context_memory : 15 msg + 3 résumés)
│       ├── test_purge.py                       # NEW (cascade message_chunks + checkpoint LangGraph)
│       └── test_checkpointer_persistence.py    # NEW (smoke restart-like : checkpoint persiste à travers reload)

frontend/
├── app/
│   └── components/
│       └── ToolCallIndicator.vue               # MODIF (libellé « Recherche dans l'historique... » si tool name === 'recall_history')
└── tests/
    └── e2e/
        └── F12-memoire-contextuelle-pgvector.spec.ts   # NEW (4 scénarios)

docs/
└── memory-architecture.md                      # NEW (decision tree + schéma flux)
```

**Structure Decision** : Web application (option 2). Le backend FastAPI accueille la quasi-totalité du code F12 ; le frontend reçoit une amélioration mineure (texte indicateur d'outil + dark mode). Les tests E2E Playwright sont colocalisés avec le frontend selon la convention projet.

## Phase 0 — Outline & Research

Voir `research.md` (généré ci-dessous).

Décisions résolues lors de la phase de clarification (toutes intégrées au spec) :
- **Q1** Mécanisme d'indexation async → `asyncio.create_task` détachée
- **Q2** Stratégie de chunking → ≤ 6 000 c → 1 chunk ; > 6 000 c → 6 000 c avec overlap 200 c, par paragraphe
- **Q3** `recall_history` exclut la conversation courante par défaut → paramètre `include_current_conversation: bool = False`
- **Q4** Format horodatage → français court (« il y a N min/h/j », « hier », « le DD/MM/YYYY »)
- **Q5** Cache court terme `recall_history` → déféré post-MVP (couvert par MAX_TOOL_CALLS_PER_TURN)

Sujets de recherche restants :
- **R1** Pattern d'init/teardown `AsyncPostgresSaver` dans le lifespan FastAPI (compat asyncio + LangGraph 0.2.x).
- **R2** Hook SQLAlchemy `after_insert` async-safe : éviter le « detached lazy load » et garantir que `asyncio.create_task` ne référence pas une session fermée.
- **R3** Stratégie de masquage : ordre d'application des regex (cartes Luhn → IBAN → email → token) pour éviter les chevauchements.
- **R4** Comportement HNSW vs index composite `(account_id, conversation_id, created_at DESC)` : ordre de création, impact sur le coût d'écriture.
- **R5** Suppression cascade des checkpoints LangGraph : API officielle d'`AsyncPostgresSaver` ou requête SQL directe filtrée par `thread_id` ?

## Phase 1 — Design & Contracts

Voir `data-model.md`, `contracts/memory_tools.md`, `contracts/memory_service.md`, `quickstart.md`.

Étapes :
1. Modèle SQLAlchemy `MessageChunk` aligné sur `DocumentChunk` (Vector(1536), index HNSW).
2. Migration Alembic 023 avec down_revision = `'022_money_and_versioning'`.
3. Service `app/modules/memory/service.py` :
   - `mask_secrets(text: str) -> str` : applique 4 regex (cartes Luhn → IBAN → email → token Bearer) dans cet ordre.
   - `chunk_text(text: str, max_chars: int = 6000, overlap: int = 200) -> list[str]` : découpe par paragraphes, fallback phrase, fallback mot.
   - `embed_message(message_id, account_id, conversation_id, role, content) -> None` : appelle `OpenAIEmbeddings.aembed_query` (batch si plusieurs chunks via `aembed_documents`), insert dans `message_chunks` ; gère erreurs sans propagation.
   - `search_history(query, account_id, since, include_current_conversation, current_conversation_id, max_results) -> list[MessageRecallResult]` : embed query, COSINE search, filtre RLS, threshold 0.6.
   - `purge_account_chunks(account_id: UUID) -> None` : DELETE message_chunks WHERE account_id ; DELETE checkpoints filtrés par thread_id (résolus via la jonction `conversations.user_id ∈ users WHERE account_id = ?`).
4. Hooks `app/modules/memory/hooks.py` :
   - `event.listens_for(Message, 'after_insert')` : récupère asyncio loop via `asyncio.get_running_loop()` (sécurité : skip si pas dans event loop, ex. tests sync) ; détache via `asyncio.create_task(embed_message(...))` ; conserve référence dans un set faible pour éviter GC.
5. Tool LangChain `recall_history` : `@tool(args_schema=RecallHistoryArgs)` async, lit `account_id` + `current_conversation_id` depuis le state LangGraph (via `RunnableConfig.configurable`), appelle `search_history`.
6. `RecallHistoryArgs` Pydantic v2 : `query: str (min_length=2, max_length=500)`, `max_results: int = Field(default=5, ge=1, le=10)`, `since: datetime | None = None`, `include_current_conversation: bool = False`.
7. Modification `_load_context_memory` :
   - SELECT 15 derniers messages de la conversation courante (`Message.conversation_id == current_conversation_id`, ORDER BY created_at DESC LIMIT 15, puis reverse).
   - Format chaque message : `[il y a 3 minutes, utilisateur] contenu...`.
   - Concatène avec les 3 résumés existants (résumés en tête, messages bruts en queue).
8. Modification `tool_selector_config.py` : `recall_history` ajouté à `GLOBAL_WHITELIST`. Calcul : page « chat_global » a 8 tools métier + 5 globaux = 13 → ajout `recall_history` ferait 14, donc relèvement de `MAX_TOOLS_PER_TURN` à 14. Mise à jour `_validate_config()`.
9. Modification `graph.py` :
   - `from app.graph.checkpointer import create_checkpointer` (déjà présent).
   - `create_compiled_graph()` accepte un `checkpointer` injecté en paramètre (testabilité). Lifespan FastAPI passe le checkpointer initialisé une fois.
   - Injection `MEMORY_TOOLS` (recall_history) dans tous les `create_tool_loop` (chat, esg_scoring, carbon, financing, application, credit, action_plan).
10. Modification `main.py` lifespan :
   - `async with create_checkpointer() as cp:` → stocke `app.state.checkpointer = cp` ; rebuild compiled_graph avec ce checkpointer ; teardown propre.
11. Frontend : `ToolCallIndicator.vue` reçoit déjà `tool_name` ; ajout d'une case `recall_history` → texte « Recherche dans l'historique de conversation... » (dark mode déjà présent).
12. Tests :
   - `test_service.py` : 6 tests masquage (4 motifs + combinés + idempotence), 4 tests chunking (court, long, paragraphes, overlap), 3 tests embed (succès, échec API, sans crash).
   - `test_hooks.py` : 2 tests (création message → task scheduled, exception dans embed → message reste en base).
   - `test_recall_history_tool.py` : 5 tests (base success, threshold filter, since filter, RLS isolation A vs B, include_current_conversation flag).
   - `test_chat_context_loader.py` : 4 tests (15 messages chargés, conversation courte < 15, format horodatage, 3 résumés en tête).
   - `test_purge.py` : 3 tests (delete account → cascade chunks, checkpoints supprimés, autre account non impacté).
   - `test_checkpointer_persistence.py` : 1 test smoke (write/read checkpoint persiste à travers fermeture/réouverture de la session DB).

## Re-évaluation Constitution Check post-design

| Principe | Conformité après design | Notes |
|---|---|---|
| I. Francophone-First | PASS | Aucune régression. |
| II. Modulaire | PASS | `app/modules/memory/` est isolé ; le hook a une dépendance unilatérale sur `Message`. |
| III. Conversation-Driven | PASS | Renforcement direct. |
| IV. Test-First | PASS | 7 fichiers de tests au plan, >= 25 cas test prévus. |
| V. Sécurité | PASS | Pas de mutations LLM (recall = lecture seule). RLS strict. Masquage en amont du stockage. |
| VI. Inclusivité | PASS | Pas de régression UX. Indicateur visuel optionnel. |
| VII. Simplicité | PASS | Réutilisation maximale (DocumentChunk, OpenAIEmbeddings, helper RLS, checkpointer existant). Pas de nouvelle dépendance. |

**Résultat** : tous les gates restent verts post-design.

## Complexity Tracking

> Aucune violation. Tableau vide.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(N/A)_ | _(N/A)_ | _(N/A)_ |

## Risques résiduels & mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| AsyncPostgresSaver non testé en production | Moyenne | Élevé | Test smoke `test_checkpointer_persistence.py` + benchmark p95 latency manuel post-merge. |
| Hook `after_insert` schedule task sur loop fermée (tests sync) | Faible | Faible | Détecter `asyncio.get_running_loop()` ; skip silencieux + log debug si absente. |
| Embedding API timeout / rate limit | Moyenne | Faible | Try/except autour de l'appel ; message reste indexable plus tard via `embedding IS NULL` (rattrapage F19). |
| RLS context manquant lors d'une requête `recall_history` | Très faible | Critique | Code applicatif filtre EXPLICITEMENT par `account_id` en plus de la RLS (défense en profondeur — pattern F01). |
| Index HNSW long à construire en migration | Moyenne | Faible (table vide au déploiement) | Création de l'index dans la migration ; les chunks sont insérés post-migration au fil de l'eau. |
| Chevauchement regex masquage | Moyenne | Moyen | Ordre fixe testé : cartes Luhn → IBAN → email → token. Tests dédiés aux combinaisons. |
| `MAX_TOOLS_PER_TURN` borne 13 → 14 dépasse capacité LLM | Très faible | Faible | Validé : Claude/Sonnet supporte >= 32 tools. Borne reste largement en deçà. |
| Suppression cascade des checkpoints LangGraph non gérée par défaut | Élevée | Moyen | `purge_account_chunks` exécute explicitement DELETE FROM checkpoints WHERE thread_id IN (sub-query conversation_id). Test `test_purge.py` couvre. |

## Stratégie de migration progressive

Compatibilité avec l'existant :
- À chaud : la migration 021 ajoute la table `message_chunks` (vide) ; aucune donnée legacy à transformer.
- Le passage `MemorySaver → AsyncPostgresSaver` invalide les conversations en cours en RAM au moment du déploiement (effet de bord acceptable : les conversations volatiles l'étaient déjà au moindre redémarrage).
- Les messages historiques antérieurs au déploiement F12 NE sont PAS indexés rétroactivement (cf. Assumptions). Une commande CLI `python -m app.scripts.backfill_message_chunks` est PRÉVUE comme post-MVP optionnel — pas dans le scope F12.

Rollback :
- `alembic downgrade -1` supprime la table `message_chunks` et son index HNSW (les checkpoints LangGraph nécessitent un nettoyage manuel post-rollback : `DROP TABLE checkpoints, checkpoint_writes, checkpoint_blobs`).
- Reverter le changement `MemorySaver → AsyncPostgresSaver` redonne l'état antérieur sans corruption (les conversations en cours seront perdues mais l'application reste fonctionnelle).
