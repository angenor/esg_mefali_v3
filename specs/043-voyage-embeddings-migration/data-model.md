# Phase 1 — Data Model: F25 Voyage AI Embeddings Migration

**Branch**: `043-voyage-embeddings-migration` | **Date**: 2026-05-08 | **Prerequisite**: `research.md` complete

Ce document décrit les changements de modèle de données introduits par F25 — colonnes pgvector, configuration applicative, et entités logiques nouvelles.

---

## 1. Schéma physique (PostgreSQL + pgvector)

### 1.1 Tables concernées par la migration 043

| Table | Colonne | Avant 043 | Après 043 | Index HNSW associé |
|-------|---------|-----------|-----------|---------------------|
| `message_chunks` | `embedding` | `vector(1536)` NULL | `vector(1024)` NULL | `ix_message_chunks_embedding_hnsw` (recréé) ; `idx_message_chunks_pending_embedding` partial sur `created_at WHERE embedding IS NULL` (recréé) |
| `document_chunks` | `embedding` | `vector(1536)` NULL | `vector(1024)` NULL | `ix_document_chunks_embedding_hnsw` (recréé) |
| `financing_chunks` | `embedding` | **`text`** NULL (bug mig. 008) | `vector(1024)` NULL | `ix_financing_chunks_embedding_hnsw` (**créé**, n'existait pas en prod) |

### 1.2 Tables exclues (non concernées par la migration)

| Table | Colonne d'embedding | Raison de l'exclusion |
|-------|---------------------|------------------------|
| `sources` | `embedding` (`JSONType`) | Stockage JSON, pas pgvector. Hors scope F25 — F01 a déjà acté ce choix de stockage. |
| `documents` | _(aucune)_ | Le modèle `Document` n'a pas de colonne `embedding`. Confusion dans la spec initiale. |
| `funds` | _(aucune)_ | Le modèle `Fund` n'a pas de colonne `embedding`. La recherche sémantique passe par `financing_chunks` avec `source_type='fund'`. |

### 1.3 Index HNSW — paramètres uniformes

Tous les index HNSW créés / recréés par 043 utilisent les paramètres suivants (cohérent avec le pattern existant des migrations 023 et 163318558259) :

```sql
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
```

Distance d'opérateur : cosine (`<=>`). Choix justifié par la nature normalisée des embeddings voyage-3.5.

### 1.4 RLS multi-tenant (F02) — invariant

Les politiques RLS existantes sur `message_chunks` (mig. 023) sont **automatiquement préservées** par `ALTER COLUMN ... TYPE vector(1024)`. PostgreSQL conserve les policies indépendamment des modifications de type colonne.

À vérifier post-migration en `tests/migrations/test_043_embeddings_voyage_dim.py` :
- `SELECT polname FROM pg_policies WHERE tablename = 'message_chunks'` retourne 2 lignes (`admin_full_access`, `pme_access_own_account`).
- Idem pour `document_chunks` et `financing_chunks` si des policies y existent.

### 1.5 Audit log (F03) — invariant

Aucun des 3 modèles (`MessageChunk`, `DocumentChunk`, `FinancingChunk`) n'est dans `AUDITABLE_MODELS`. Aucune ligne `audit_log` n'est générée par la migration ni par le ré-embedding lazy. ✅

---

## 2. Modèles SQLAlchemy

### 2.1 Modifications par fichier

#### `backend/app/models/message_chunk.py`

```python
# AVANT
embedding = mapped_column(
    Vector(1536) if Vector is not None else Text,
    nullable=True,
)

# APRÈS
embedding = mapped_column(
    Vector(1024) if Vector is not None else Text,
    nullable=True,
)
```

#### `backend/app/models/document.py` (classe `DocumentChunk`)

```python
# Même pattern, ligne ~140 : 1536 → 1024
```

#### `backend/app/models/financing.py` (classe `FinancingChunk`)

```python
# Même pattern, ligne ~508 : 1536 → 1024
```

### 2.2 Branche SQLite

Le pattern `Vector(N) if Vector is not None else Text` reste préservé. Sur SQLite (tests in-memory) la colonne reste `Text` quel que soit le N — la dim Voyage n'a pas d'impact sur les tests qui ne touchent pas réellement à pgvector.

### 2.3 État de validation invariants

- Tous les modèles continuent d'hériter de `Base`, `UUIDMixin`, `TimestampMixin` selon leur déclaration existante.
- Aucun changement de FK, ondelete, ou contrainte CHECK.
- Type Python côté ORM reste `list[float] | None`.

---

## 3. Configuration applicative (`backend/app/core/config.py`)

### 3.1 Champs à ajouter

```python
from typing import Literal

class Settings(BaseSettings):
    # ... champs existants ...

    # ── Voyage AI Embeddings (F25) ──────────────────────────────
    voyage_api_key: str = ""
    voyage_model: Literal["voyage-3.5", "voyage-3-large", "voyage-multilingual-2"] = "voyage-3.5"
    voyage_embedding_dim: Literal[1024] = 1024
    # voyage-3.5 → 1024 dims natif ; les autres modèles autorisés ne sont pas
    # utilisés par MVP mais leur Literal permet une extension future contrôlée.
```

### 3.2 Champs à retirer

```python
# ── Embeddings (OpenAI text-embedding-3-small) — F12 ──── À SUPPRIMER
# openai_api_key: str = ""
```

Justification : ce champ était utilisé exclusivement par les 4 instantiations `OpenAIEmbeddings` qui disparaissent. ChatOpenAI utilise `openrouter_api_key`. Aucun call site résiduel.

### 3.3 model_post_init — invariant

Le bloc `model_post_init` qui mappe `LLM_*` → `openrouter_*` reste **strictement inchangé** (FR-014).

### 3.4 Tableau récapitulatif des variables d'environnement

| Variable | Avant | Après | Rôle |
|----------|-------|-------|------|
| `OPENROUTER_API_KEY` / `LLM_API_KEY` | utilisé par ChatOpenAI | inchangé | LLM principal (texte génératif) |
| `OPENROUTER_BASE_URL` / `LLM_BASE_URL` | inchangé | inchangé | Endpoint LLM |
| `OPENROUTER_MODEL` / `LLM_MODEL` | inchangé | inchangé | Modèle LLM (claude-sonnet-4-x) |
| `OPENAI_API_KEY` | utilisé par OpenAIEmbeddings | **retiré** | (orphelin après F25) |
| `VOYAGE_API_KEY` | (présent en `.env` mais inutilisé) | **utilisé** | Embeddings (memory, financing, documents) |

---

## 4. Entité logique : `EmbeddingsClient` (contrat helper)

### 4.1 Définition (helper centralisé `app/lib/embeddings.py`)

```python
"""Helper centralisé pour la construction du client d'embeddings F25.

Conformité : FR-001 (fournisseur unique), FR-006 (mode dégradé), FR-007c (timeout/retry).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_embeddings_client() -> Optional["VoyageAIEmbeddings"]:
    """Retourne un client VoyageAIEmbeddings configure, ou None si VOYAGE_API_KEY absent.

    Convention : un retour None signale au caller qu'il doit basculer en mode
    degrade (skip de l'indexation, log deja emis ici). Aucune exception n'est
    propagee pour la cle manquante (cas routinier en dev/CI sans secret).
    """
    from app.core.config import settings

    if not settings.voyage_api_key:
        logger.warning(
            "Aucune cle d'embedding configuree. Definir VOYAGE_API_KEY dans .env."
        )
        return None

    try:
        from langchain_voyageai import VoyageAIEmbeddings
    except ImportError:
        logger.error(
            "Module langchain_voyageai indisponible. "
            "Reinstaller backend/requirements.txt."
        )
        return None

    return VoyageAIEmbeddings(
        voyage_api_key=settings.voyage_api_key,
        model=settings.voyage_model,
        request_timeout=10,
        max_retries=1,
        batch_size=72,
    )
```

### 4.2 Sémantique d'utilisation

- **memory** : remplace le contenu de `memory/service.py::_embeddings_model()` par un appel à `get_embeddings_client()`. Conserve le nom `_embeddings_model` (signature externe inchangée pour les tests qui le mockent).
- **financing/service** : `embeddings_model = get_embeddings_client()` avant l'appel. Si `None` → `return []`.
- **financing/seed** : idem.
- **documents/service** : `_get_embeddings()` délègue à `get_embeddings_client()`.

### 4.3 Tests contractuels

`tests/memory/test_embeddings_client.py` :

```python
import os
import pytest

@pytest.mark.embeddings
def test_returns_none_without_key(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    # Re-import settings pour rafraichir la valeur
    from app.lib.embeddings import get_embeddings_client
    assert get_embeddings_client() is None


@pytest.mark.embeddings
@pytest.mark.skipif(not os.environ.get("VOYAGE_API_KEY"), reason="No Voyage key in CI")
def test_returns_voyage_client_with_key():
    from app.lib.embeddings import get_embeddings_client
    from langchain_voyageai import VoyageAIEmbeddings
    client = get_embeddings_client()
    assert isinstance(client, VoyageAIEmbeddings)
    assert client.model == "voyage-3.5"
```

---

## 5. Entité logique : `ReembedAllScript` (contrat CLI)

### 5.1 Description

Script administratif opt-in pour ré-embedder les lignes `embedding IS NULL` des 3 tables vectorielles.

### 5.2 CLI

```
python -m app.scripts.reembed_all [OPTIONS]

Options:
  --table {messages,documents,financing,all}   Table cible (def: all)
  --limit N                                    Limite le nb de lignes traitees par table (def: aucune)
  --batch-size B                               Taille de batch SDK Voyage (def: 72, max voyage-3.5)
  --dry-run                                    Simule sans ecrire en BDD
  --help                                       Affiche cette aide
```

### 5.3 Comportement

- Pour chaque table cible, `SELECT id, <text_column> WHERE embedding IS NULL ORDER BY created_at LIMIT N`.
- Mapping `<text_column>` :
  - `message_chunks` → `chunk_text`
  - `document_chunks` → `content`
  - `financing_chunks` → `content`
- Batche les contenus par `batch_size`, appelle `aembed_documents(batch)`, persiste via `UPDATE ... SET embedding = :v WHERE id = :id`.
- Si `get_embeddings_client()` retourne `None` → exit code 1, message clair.
- Logs : compteur `{succes}/{candidats}` par table, total fin de run.
- `--dry-run` : tout sauf le `UPDATE` final + log `[DRY-RUN]` préfixé.

### 5.4 Codes de sortie

| Code | Signification |
|------|---------------|
| 0 | Tout traité (même partiellement avec quelques échecs Voyage) |
| 1 | Erreur fatale : clé Voyage absente, BDD indisponible, table inconnue |
| 2 | Argument invalide |

### 5.5 Tests

`tests/test_tools/test_reembed_script.py` :
- Test `--dry-run` : ne fait pas de UPDATE, retourne 0.
- Test `--table messages` avec mock du client : ne touche que `message_chunks`.
- Test échec clé absente : retourne 1, message stderr conforme.
- Test `--limit 5` : ne traite que 5 lignes même si la table en contient plus.

---

## 6. Validation post-migration (queries de smoke)

Ces queries SQL sont à exécuter (manuellement ou via `tests/migrations/test_043_embeddings_voyage_dim.py`) après `alembic upgrade head` :

```sql
-- 1. Dimensions des colonnes (3 tables)
SELECT
  c.relname AS table_name,
  a.attname AS column_name,
  a.atttypmod AS dim
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
WHERE c.relname IN ('message_chunks', 'document_chunks', 'financing_chunks')
  AND a.attname = 'embedding'
  AND NOT a.attisdropped
ORDER BY c.relname;
-- attendu : 3 lignes, dim = 1024 partout

-- 2. Indexes HNSW présents
SELECT
  schemaname, tablename, indexname
FROM pg_indexes
WHERE indexname IN (
  'ix_message_chunks_embedding_hnsw',
  'idx_message_chunks_pending_embedding',
  'ix_document_chunks_embedding_hnsw',
  'ix_financing_chunks_embedding_hnsw'
)
ORDER BY tablename, indexname;
-- attendu : 4 lignes (les 4 indexes presents)

-- 3. RLS toujours actif sur message_chunks
SELECT polname FROM pg_policies WHERE tablename = 'message_chunks' ORDER BY polname;
-- attendu : 2 lignes (admin_full_access, pme_access_own_account)

-- 4. Toutes les valeurs embedding sont NULL post-migration (TRUNCATE applique)
SELECT 'message_chunks' AS t, COUNT(*) AS n_non_null FROM message_chunks WHERE embedding IS NOT NULL
UNION ALL
SELECT 'document_chunks', COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL
UNION ALL
SELECT 'financing_chunks', COUNT(*) FROM financing_chunks WHERE embedding IS NOT NULL;
-- attendu : 3 lignes, n_non_null = 0 partout

-- 5. Lignes preservees (cf. SC-007)
SELECT 'message_chunks' AS t, COUNT(*) AS total FROM message_chunks
UNION ALL
SELECT 'document_chunks', COUNT(*) FROM document_chunks
UNION ALL
SELECT 'financing_chunks', COUNT(*) FROM financing_chunks;
-- attendu : meme COUNT(*) qu'avant la migration
```

---

## 7. Récapitulatif des artefacts du schéma

| Type | Avant | Après | Delta |
|------|-------|-------|-------|
| Tables | 3 vectorielles + 1 JSONType | 3 vectorielles (dim 1024) + 1 JSONType | aucune table créée/supprimée |
| Lignes métier | _N_ | _N_ (préservées) | 0 (FR-009, SC-007) |
| Valeurs embedding | Mix `NULL` + `vector(1536)` + `text` | Toutes `NULL` post-migration → repeuplées paresseusement par lazy + `reembed_all` opt-in | TRUNCATE de la colonne |
| Index HNSW | 2 (message_chunks, document_chunks) | 3 (+ financing_chunks) | +1 (correction bug) |
| Index partiels `pending_embedding` | 1 (message_chunks) | 1 (recréé) | 0 |
| Policies RLS | inchangées | inchangées | 0 |
| Triggers audit | non applicable | non applicable | 0 |

**Tout est cohérent avec FR-008 à FR-011 et SC-001/SC-007.**
