# Phase 1 — Data Model : F12 Mémoire Contextuelle Conforme

## Vue d'ensemble

F12 introduit une seule nouvelle table métier : `message_chunks`. Trois tables système (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) sont créées automatiquement par `AsyncPostgresSaver.setup()` au premier démarrage du backend (gérées par LangGraph, pas par Alembic).

---

## Table `message_chunks`

### Description

Représente un fragment d'un message conversationnel, indexé pour la recherche sémantique via embedding pgvector. Un message court (≤ 6 000 caractères) produit exactement un chunk (`chunk_index = 0`). Un message long est découpé en N chunks avec recouvrement de 200 caractères entre chunks consécutifs.

### Schéma SQL (équivalent migration Alembic 023)

> **Note** : `id` reçoit son default soit par `gen_random_uuid()` côté serveur (DDL Postgres), soit par `default=uuid.uuid4` côté Python (UUIDMixin). Les deux sources cohabitent sans conflit — l'ORM fournit la valeur via Python avant l'INSERT, le DDL serveur sert de filet de sécurité pour les inserts SQL directs (scripts, fixtures).

```sql
CREATE TABLE message_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    role VARCHAR(20) NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1536),                 -- nullable (rattrapage possible si embed échoue)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT message_chunks_role_chk CHECK (role IN ('user', 'assistant', 'system')),
    CONSTRAINT message_chunks_chunk_index_chk CHECK (chunk_index >= 0)
);

-- Index principal pour le rattrapage F19 + suppression cascade par account
CREATE INDEX idx_message_chunks_account_conv_created
    ON message_chunks (account_id, conversation_id, created_at DESC);

-- Index dédié au filtre rattrapage des chunks non encore embeddés
CREATE INDEX idx_message_chunks_pending_embedding
    ON message_chunks (created_at)
    WHERE embedding IS NULL;

-- Index HNSW pour la recherche sémantique (cosine similarity)
CREATE INDEX ix_message_chunks_embedding_hnsw
    ON message_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- RLS PostgreSQL (F02 multi-tenant strict)
ALTER TABLE message_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_chunks FORCE ROW LEVEL SECURITY;

CREATE POLICY admin_full_access ON message_chunks
    FOR ALL
    USING (current_setting('app.current_role', true) = 'ADMIN')
    WITH CHECK (current_setting('app.current_role', true) = 'ADMIN');

CREATE POLICY pme_access_own_account ON message_chunks
    FOR ALL
    USING (
        current_setting('app.current_role', true) = 'PME'
        AND account_id = current_setting('app.current_account_id', true)::uuid
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'PME'
        AND account_id = current_setting('app.current_account_id', true)::uuid
    );
```

### Mapping SQLAlchemy (`app/models/message_chunk.py`)

```python
"""Modèle SQLAlchemy MessageChunk (F12 - mémoire contextuelle pgvector)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # SQLite (tests) — Vector indisponible, on bascule sur Text
    Vector = None


class MessageChunk(UUIDMixin, Base):
    """Fragment d'un message conversationnel indexé pour la recherche sémantique."""

    __tablename__ = "message_chunks"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(
        Vector(1536) if Vector is not None else Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="message_chunks_role_chk",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="message_chunks_chunk_index_chk",
        ),
        Index(
            "idx_message_chunks_account_conv_created",
            "account_id",
            "conversation_id",
            "created_at",
        ),
    )


# Index HNSW (PostgreSQL only)
if Vector is not None:
    Index(
        "ix_message_chunks_embedding_hnsw",
        MessageChunk.embedding,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
```

### Champs

| Champ | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | Identifiant unique. |
| `account_id` | UUID FK accounts.id | NO | — | Tenant propriétaire (F02). RLS active sur ce champ. |
| `conversation_id` | UUID FK conversations.id | NO | — | Conversation d'origine. Cascade delete. |
| `message_id` | UUID FK messages.id | NO | — | Message d'origine. Cascade delete. |
| `chunk_index` | INTEGER | NO | 0 | Position du chunk dans le message (0 = premier, ou unique pour message court). |
| `role` | VARCHAR(20) | NO | — | Rôle du message d'origine : `user` / `assistant` / `system`. |
| `chunk_text` | TEXT | NO | — | Texte du chunk APRÈS masquage des secrets (longueur ≤ 6 200 caractères). |
| `embedding` | VECTOR(1536) | OUI | NULL | Embedding `text-embedding-3-small`. NULL si embedding échoué (rattrapage F19). |
| `created_at` | TIMESTAMPTZ | NO | `now()` | Horodatage UTC de création du chunk. |

### Invariants

- `chunk_text` est toujours la version MASQUÉE du contenu (pas le texte brut). Le texte original reste dans `messages.content` non modifié.
- `account_id` correspond à `messages.account_id` (déjà présent depuis F02). Garantit l'isolation RLS au niveau du chunk même si on accède directement à `message_chunks` sans JOIN.
- `embedding` peut être NULL juste après l'INSERT (avant le retour de l'embedding API). Le rattrapage F19 le complète.
- Aucun chunk de longueur 0 : si `mask_secrets` produit une chaîne vide, on insert `'[redacted]'` à la place pour respecter le NOT NULL et garder une trace d'audit.

### Relations

- N:1 vers `messages` (FK `message_id`, ON DELETE CASCADE).
- N:1 vers `conversations` (FK `conversation_id`, ON DELETE CASCADE — redondant avec messages.conversation_id, mais utile pour l'index composite).
- N:1 vers `accounts` (FK `account_id`, ON DELETE RESTRICT — la suppression réelle se fait via `purge_account_chunks` qui supprime les chunks AVANT le account).

### Lifecycle

```text
[Message INSERT]
        |
        v
[Hook after_insert]  --(pas de loop async)-->  [no-op + log debug]
        |
        v
[asyncio.create_task(embed_message)]
        |
        v
[mask_secrets(content)] --> chunk_text masqué
        |
        v
[chunk_text(masked, 6000, 200)] --> liste de N chunks
        |
        v
[OpenAIEmbeddings.aembed_documents(chunks)] --(échec)--> log warning, INSERT chunks avec embedding=NULL
        |
        v (succès)
[INSERT INTO message_chunks (..., embedding=...) for each chunk]
        |
        v
[Disponible pour recall_history search]
```

---

## Tables système gérées par LangGraph (`AsyncPostgresSaver`)

Les trois tables suivantes sont créées par `AsyncPostgresSaver.setup()` (méthode appelée dans le lifespan FastAPI au premier démarrage). Elles ne sont PAS gérées par Alembic.

### `checkpoints`

Stocke un état de conversation (un snapshot du `ConversationState` à un instant donné).

| Champ | Type | Description |
|---|---|---|
| `thread_id` | TEXT | Identifiant logique du thread (`str(conversation.id)`). |
| `checkpoint_ns` | TEXT | Namespace du checkpoint. |
| `checkpoint_id` | TEXT | Identifiant unique du checkpoint. |
| `parent_checkpoint_id` | TEXT | Référence au checkpoint précédent. |
| `type` | TEXT | Type sérialisation. |
| `checkpoint` | JSONB | Données sérialisées du state. |
| `metadata` | JSONB | Métadonnées (writes, source). |

### `checkpoint_writes`

Journal des écritures pendant l'exécution du graphe.

### `checkpoint_blobs`

Stockage volumineux séparé (BLOBs binaires) pour ne pas saturer JSONB.

### Suppression cascade

Lors d'un `purge_account_chunks(account_id)`, on exécute (en plus du DELETE sur `message_chunks`) :

```sql
-- Supprimer les checkpoints liés aux conversations de cet account
DELETE FROM checkpoint_blobs
WHERE thread_id IN (
    SELECT id::text FROM conversations
    WHERE user_id IN (SELECT id FROM users WHERE account_id = :account_id)
);

DELETE FROM checkpoint_writes
WHERE thread_id IN (
    SELECT id::text FROM conversations
    WHERE user_id IN (SELECT id FROM users WHERE account_id = :account_id)
);

DELETE FROM checkpoints
WHERE thread_id IN (
    SELECT id::text FROM conversations
    WHERE user_id IN (SELECT id FROM users WHERE account_id = :account_id)
);
```

> **Note** : la suppression cascade SQL standard n'est pas applicable car les tables LangGraph n'ont pas de FK déclarée vers nos tables. Le DELETE applicatif compense.

---

## Modifications de tables existantes

**Aucune.** F12 ne touche pas aux tables existantes (`messages`, `conversations`, `accounts`, `users`, etc.). Les hooks SQLAlchemy s'attachent au modèle `Message` sans modification du schéma.

---

## Volumes attendus

| Échéance | PME actives | Messages/jour | Chunks/jour | Cumul `message_chunks` |
|---|---|---|---|---|
| MVP (3 mois) | 100 | 1 000 | 1 200 | ~ 110 k |
| MVP+ (6 mois) | 500 | 5 000 | 6 000 | ~ 1,1 M |
| MVP+ (12 mois) | 1 000 | 10 000 | 12 000 | ~ 4,4 M |

> Hypothèse : ratio chunks/messages = 1,2 (la majorité des messages produit 1 chunk, ~ 5 % produisent 2-5 chunks).

À 4,4 M rows, HNSW `m=16` reste largement opérationnel (cas validé en littérature jusqu'à 10 M+). Partitionnement par mois prévu post-MVP si croissance dépasse les attentes.
