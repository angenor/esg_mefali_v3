# Implementation Plan: F25 — Migration des Embeddings vers Voyage AI

**Branch**: `043-voyage-embeddings-migration` | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/043-voyage-embeddings-migration/spec.md`

## Summary

Migration du pipeline d'embeddings de `langchain-openai.OpenAIEmbeddings` (modèle `text-embedding-3-small`, 1536 dim) vers `langchain-voyageai.VoyageAIEmbeddings` (modèle `voyage-3.5`, 1024 dim, multilingue).

> **⚠️ Correction de scope par rapport à la spec initiale** (cf. `research.md` R1 et clarifications spec.md) : le schéma réel comporte **3 tables vectorielles** (`message_chunks`, `document_chunks`, `financing_chunks`), pas 4. Les références initiales à `documents.embedding` et `funds.embedding` étaient incorrectes ; elles correspondaient en réalité à `document_chunks` et `financing_chunks`. Bonus : F25 corrige opportunément un bug de la migration 008 où `financing_chunks.embedding` avait été créée en `TEXT` au lieu de `vector` (créant un index HNSW manquant).

**Approche technique** : opération chirurgicale en deux PR indépendants. **(1)** PR migration Alembic `043_embeddings_voyage_dim.py` qui : (a) DROP les index HNSW + partial existants ; (b) `UPDATE ... SET embedding = NULL` sur les 3 tables ; (c) `ALTER COLUMN embedding TYPE vector(1024)` (avec `USING NULL` pour la conversion `TEXT→vector` côté `financing_chunks`) ; (d) CREATE les index HNSW (incluant nouveau `ix_financing_chunks_embedding_hnsw`) + partial `idx_*_pending_embedding`. **(2)** PR code applicatif qui : (a) remplace 4 imports `OpenAIEmbeddings` par un helper centralisé `app/lib/embeddings.py::get_embeddings_client()` retournant `Optional[VoyageAIEmbeddings]` ; (b) ajoute 3 champs `voyage_*` à la config Pydantic (et retire `openai_api_key` orphelin) ; (c) met à jour les 3 modèles SQLAlchemy (`Vector(1536) → Vector(1024)`) ; (d) corrige le check de dimension dans `memory/service.py:456` (1536 → 1024) ; (e) livre le script admin opt-in `python -m app.scripts.reembed_all` ; (f) ajoute la doc `docs/embeddings-voyage.md` (politique fournisseur, posture vie privée, procédure re-embedding, baseline 10 requêtes FR). Mode dégradé conservé (clé manquante → log + chat continue ; erreur API → embedding `NULL` + lazy retry, retry SDK 1× + timeout 10 s, pas de circuit breaker).

## Technical Context

**Language/Version** : Python 3.12 (backend) — pas d'impact frontend (Nuxt 4) sur cette feature.
**Primary Dependencies** :
- **Nouveau** : `langchain-voyageai>=0.1.4` (ajouté à `backend/requirements.txt`).
- **Conservé** : `langchain-openai>=0.3.0` (utilisé par `ChatOpenAI` pour OpenRouter LLM — FR-014, ne PAS retirer).
- Existants utilisés : `langchain-core`, `langchain-text-splitters`, `pgvector`, `SQLAlchemy 2.x async`, `Alembic`, `Pydantic v2`, `tiktoken`.

**Storage** : PostgreSQL 16 + extension pgvector (HNSW cosinus). **3 colonnes** à promouvoir vers `vector(1024)` :

| Table.Colonne | État avant | État après |
|---------------|-----------|------------|
| `message_chunks.embedding` | `vector(1536)` + idx HNSW + idx partiel `pending_embedding` | `vector(1024)` + idx HNSW(1024) + idx partiel |
| `document_chunks.embedding` | `vector(1536)` + idx HNSW | `vector(1024)` + idx HNSW(1024) |
| `financing_chunks.embedding` | **`TEXT`** (bug mig. 008) — pas d'idx HNSW | `vector(1024)` + idx HNSW(1024) (NOUVEAU) |

Hors scope :
- `sources.embedding` : stocké en `JSONType` (cf. `app/models/source.py:109`), pas pgvector — pas concerné par la migration.
- `documents.embedding` et `funds.embedding` : ces colonnes **n'existent pas** dans le schéma (références incorrectes dans la description initiale ; `Document` et `Fund` n'ont pas de colonne embedding).

**Testing** : pytest (backend uniquement). Tests existants à jour : `backend/tests/memory/test_service.py`, `backend/tests/memory/test_recall_history_tool.py`, `backend/tests/test_financing_*.py` (fichiers plats, pas un dossier), `backend/tests/test_document_embeddings.py`, etc. SQLite in-memory branch préservée via `Vector(...) if Vector is not None else Text` dans les modèles.

**Target Platform** : Linux server (FastAPI). Pas d'impact frontend / mobile / extension Chrome.

**Project Type** : web-service (backend FastAPI monolithique modulaire — alignement constitution principe VII Simplicité).

**Performance Goals** :
- Embedding par message ≤ 10 s P99 (timeout strict, FR-007c).
- Migration `up`/`down`/`up` ≤ 30 s sur ~100 lignes par table vectorielle (SC-004).
- Indexation messages non-bloquante via `asyncio.create_task` (pattern F12 existant — FR-004).

**Constraints** :
- Pas de circuit breaker, pas de worker background, pas de cron périodique (Q3, principe VII KISS).
- RLS multi-tenant F02 préservée (les colonnes ALTER héritent automatiquement des policies existantes).
- Audit log F03 : tables vectorielles déjà dans `EXEMPT_MODELS` ou pas dans `AUDITABLE_MODELS` (à vérifier en research) → migration techniquement transparente côté audit.
- Branche tests SQLite : `Text` au lieu de `Vector` côté in-memory ; migration Alembic skip-able si dialect != PostgreSQL.
- Sécurité : `VOYAGE_API_KEY` en env uniquement (jamais en code), masquage F12 inchangé sur messages, fonds/documents non masqués (posture documentée — Q1).

**Scale/Scope** :
- 1 nouveau fichier Python : `backend/app/lib/embeddings.py` (helper centralisé `get_embeddings_client()`).
- 4 fichiers Python modifiés (call-site refactor) : `app/modules/memory/service.py` (incl. dim check 1536→1024 line 456), `app/modules/financing/service.py`, `app/modules/financing/seed.py`, `app/modules/documents/service.py`.
- 1 fichier `app/core/config.py` modifié (ajout `voyage_*`, retrait `openai_api_key` orphelin).
- 3 modèles SQLAlchemy modifiés (1 ligne chacun : `Vector(1536) → Vector(1024)`) : `app/models/message_chunk.py`, `app/models/document.py` (DocumentChunk), `app/models/financing.py` (FinancingChunk).
- 1 nouvelle migration Alembic `043_embeddings_voyage_dim.py`.
- 1 nouveau script `backend/app/scripts/reembed_all.py`.
- 1 nouveau document `docs/embeddings-voyage.md`.
- 2 fichiers de doc env (`.env.example` racine + backend) modifiés.
- 1 fichier `CLAUDE.md` modifié (Stack > Backend > LLM, F12 ledger, nouvelle entrée F25).
- 1 fichier `backend/requirements.txt` modifié (ajout `langchain-voyageai>=0.1.4` ; conserver `langchain-openai>=0.3.0` pour ChatOpenAI/OpenRouter).
- Tests : ~7 tests `tests/memory/` à patcher (mocks vecteurs 1024d) + 1 nouveau test contractuel `tests/memory/test_embeddings_client.py` + 1 nouveau test migration `tests/migrations/test_043_embeddings_voyage_dim.py` + 1 nouveau test script `tests/test_tools/test_reembed_script.py`. Marker `@pytest.mark.embeddings` apposé sur tous les tests F25 (commande gating SC-006 : `pytest -m embeddings -v`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Justification |
|----------|--------|---------------|
| I. Francophone-First & Contextualisation Africaine | ✅ PASS | Le choix de `voyage-3.5` est explicitement motivé par sa qualité multilingue francophone supérieure (cf. spec contexte métier, SC-002 baseline française). Aucun élément UI affecté. |
| II. Architecture Modulaire | ✅ PASS | Modifications limitées aux modules existants (memory, financing, documents) sans franchir leurs frontières. Nouveau script isolé dans `app/scripts/`. Aucune dépendance inter-modules introduite. |
| III. Conversation-Driven UX | ✅ STRENGTHEN | Restaure F12 mémoire contextuelle qui est le pilier conversationnel ; aujourd'hui silencieusement cassé. Aligne directement sur ce principe. |
| IV. Test-First (NON-NEGOTIABLE) | ✅ PASS | TDD strict : tests adaptés en RED (vecteurs 1024d, mock `VoyageAIEmbeddings`) → implémentation → GREEN. SC-006 couvre la suite. Test contractuel nouveau pour `_embeddings_model()`. Couverture cible 80 %+ préservée. |
| V. Sécurité & Protection des Données | ✅ PASS | `VOYAGE_API_KEY` exclusivement en env, jamais en code. Masquage F12 préservé sur messages. Posture vie privée documentée (Q1). RLS F02 inchangée (les colonnes ALTER héritent des policies). Audit log F03 inchangé. Validation Pydantic v2 strict pour `voyage_model: Literal[...]` et `voyage_embedding_dim: Literal[1024]`. |
| VI. Inclusivité & Accessibilité | ✅ PASS | Pas d'impact UI direct. Le multilinguisme natif voyage-3.5 améliore implicitement l'inclusion (français + langues africaines secondaires comme le wolof si présent dans le contenu). |
| VII. Simplicité & YAGNI | ✅ PASS | Aucune nouvelle infrastructure (pas de queue, pas de worker, pas de cron, pas de circuit breaker — décisions Q2/Q3). Réutilisation maximale du pattern F12 existant. Le script `reembed_all` est un one-shot opt-in, pas un service permanent. Pas de fallback multi-fournisseurs (KISS). |

**Verdict pré-Phase 0** : tous les gates passent. Aucune dérogation à justifier. Phase 0 démarre.

### Re-évaluation post-Phase 1 (2026-05-08)

Après production de `research.md`, `data-model.md`, `contracts/voyage-embeddings-client.md` et `quickstart.md`, re-vérification des 7 principes :

| Principe | Statut post-design | Vérification |
|----------|---------------------|--------------|
| I. Francophone-First | ✅ MAINTENU | Baseline SC-002 = 10 requêtes FR ciblant UEMOA/CEDEAO ; documentation `docs/embeddings-voyage.md` en français. |
| II. Architecture Modulaire | ✅ MAINTENU | Helper `app/lib/embeddings.py` ajouté à un dossier existant (`app/lib/` contient déjà `eval_matching.py`, `date_fr.py`). Aucun nouveau module créé ; pas de couplage inter-modules introduit. |
| III. Conversation-Driven UX | ✅ STRENGTHEN | Le helper restaure F12 ; `recall_history` redevient fonctionnel (US1). |
| IV. Test-First | ✅ MAINTENU | data-model.md liste les tests à écrire AVANT l'implémentation : `test_embeddings_client.py`, `test_043_embeddings_voyage_dim.py`, `test_reembed_script.py`. Marker `@pytest.mark.embeddings` défini. |
| V. Sécurité & Données | ✅ MAINTENU | Contracts spécifie : `VOYAGE_API_KEY` jamais loggée, helper retourne `None` plutôt que de propager la clé en exception, RLS F02 préservée par `ALTER COLUMN TYPE` (validé en data-model.md §1.4). |
| VI. Inclusivité | ✅ MAINTENU | `voyage-3.5` multilingue retenu pour la qualité française. |
| VII. Simplicité & YAGNI | ✅ MAINTENU | Aucun ajout d'infrastructure post-design. Helper en remplacement direct. Script `reembed_all` est un one-shot CLI. Le bug de schéma `financing_chunks` corrigé est inclus dans la même migration (pas de PR séparé) car son périmètre est minimal et indispensable à US2. |

**Verdict post-design** : tous les gates passent. Pas de complexité ajoutée nécessitant justification. Phase 2 (`/speckit.tasks`) peut démarrer.

## Project Structure

### Documentation (this feature)

```text
specs/043-voyage-embeddings-migration/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # /speckit.specify output (with /speckit.clarify additions)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── voyage-embeddings-client.md  # Interface contract for the embeddings provider abstraction
├── checklists/
│   └── requirements.md  # Already created during /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created here)
```

### Source Code (repository root — concrete impacted paths)

```text
backend/
├── app/
│   ├── core/
│   │   └── config.py                    # MODIFY: add voyage_api_key/voyage_model/voyage_embedding_dim Pydantic fields ; remove orphan openai_api_key
│   ├── lib/
│   │   └── embeddings.py                # NEW: helper get_embeddings_client() -> Optional[VoyageAIEmbeddings] (centralized point per FR-001)
│   ├── modules/
│   │   ├── memory/
│   │   │   └── service.py               # MODIFY: _embeddings_model() delegates to lib.embeddings ; line 456 dim check 1536 → 1024
│   │   ├── financing/
│   │   │   ├── service.py               # MODIFY: line ~161-170 OpenAIEmbeddings → get_embeddings_client()
│   │   │   └── seed.py                  # MODIFY: line ~840-851 same swap
│   │   └── documents/
│   │       └── service.py               # MODIFY: _get_embeddings() → get_embeddings_client() (line ~495-499)
│   ├── models/
│   │   ├── document.py                  # MODIFY: DocumentChunk.embedding Vector(1536) → Vector(1024) (line ~140)
│   │   ├── financing.py                 # MODIFY: FinancingChunk.embedding Vector(1536) → Vector(1024) (line ~508)
│   │   └── message_chunk.py             # MODIFY: MessageChunk.embedding Vector(1536) → Vector(1024) (line ~72)
│   └── scripts/
│       └── reembed_all.py               # NEW: admin opt-in batch backfill `python -m app.scripts.reembed_all [--table {messages|documents|financing|all}] [--limit N] [--dry-run] [--batch-size B]`
├── alembic/
│   └── versions/
│       └── 043_embeddings_voyage_dim.py # NEW: 3-table migration — message_chunks/document_chunks ALTER 1536→1024 ; financing_chunks promoted TEXT→vector(1024) (corrects mig. 008 bug) ; recreate/create HNSW indexes ; symmetric downgrade
├── tests/
│   ├── memory/
│   │   ├── test_service.py              # MODIFY: ~7 tests — mocks return 1024d vectors ; @pytest.mark.embeddings
│   │   ├── test_recall_history_tool.py  # MODIFY: 1024d mocks ; @pytest.mark.embeddings
│   │   └── test_embeddings_client.py    # NEW: contractual test asserting get_embeddings_client() returns VoyageAIEmbeddings | None per env
│   ├── test_financing_node.py           # VERIFY (likely just re-run with 1024d if mocked) ; @pytest.mark.embeddings
│   ├── test_document_embeddings.py      # MODIFY: 1024d mocks ; @pytest.mark.embeddings
│   ├── test_tools/
│   │   ├── test_financing_tools.py      # @pytest.mark.embeddings (no behavioral change expected)
│   │   ├── test_document_tools.py       # @pytest.mark.embeddings (no behavioral change expected)
│   │   └── test_reembed_script.py       # NEW: contractual test for `python -m app.scripts.reembed_all` (dry-run + per-table) ; @pytest.mark.embeddings
│   └── migrations/
│       └── test_043_embeddings_voyage_dim.py  # NEW: alembic round-trip up/down/up on PostgreSQL test container (SC-004) ; @pytest.mark.embeddings
└── requirements.txt                     # MODIFY: add `langchain-voyageai>=0.1.4` ; KEEP `langchain-openai>=0.3.0` (used by ChatOpenAI for OpenRouter LLM — FR-014)

docs/
└── embeddings-voyage.md                 # NEW: provider policy, dimension, re-embed procedure, cost estimate, privacy posture (Q1), 10-query French baseline (SC-002)

.env.example                             # MODIFY: doc VOYAGE_API_KEY=, deprecate OPENAI_API_KEY comment (or keep as still-supported for legacy LLM path? — verified by research — section R5)
backend/.env.example                     # MODIFY: same as above
CLAUDE.md                                # MODIFY: Stack > Backend > LLM (replace text-embedding-3-small mention with voyage-3.5 1024d) ; F12 entry mentions new dim ; new F25 ledger entry under Module 1
```

**Structure Decision** : monolithe modulaire (Constitution VII Simplicité). Pas de découpage en microservices. La feature touche 3 modules existants sans franchir leurs frontières et n'introduit qu'un seul nouveau script utilitaire isolé. Pas de nouveau module.

## Complexity Tracking

> **Cette feature ne présente aucune violation de la constitution.** Aucune justification de complexité ajoutée n'est requise.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _N/A_     | _N/A_      | _N/A_                                |
