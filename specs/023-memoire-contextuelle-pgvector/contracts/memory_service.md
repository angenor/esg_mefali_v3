# Contract : Service interne `app.modules.memory.service`

Module : `backend/app/modules/memory/service.py`

Service de bas niveau pour l'embedding, la recherche, le masquage et la purge de chunks d'historique conversationnel. Utilisé par le hook SQLAlchemy (`hooks.py`) et par le tool LangChain (`memory_tools.py`).

---

## Fonction `mask_secrets(text: str) -> str`

Applique 4 regex dans l'ordre déterministe (cf. research.md R3) :

1. Tokens Bearer / API key → `[TOKEN]`
2. Email → `[EMAIL]`
3. IBAN → `[BANK]`
4. Numéro de carte bancaire (validé Luhn) → `[CARD]`

### Garanties

- **Idempotence** : `mask_secrets(mask_secrets(t)) == mask_secrets(t)`. Les marqueurs `[TOKEN]`, `[EMAIL]`, `[BANK]`, `[CARD]` ne re-matchent aucune regex.
- **Préservation structure** : le texte autour du motif masqué est intact ; seuls les caractères du motif sont remplacés.
- **Pas de modification si vide** : `mask_secrets('') == ''`.
- **Validation Luhn** : un numéro de 16 chiffres ne validant pas Luhn n'est PAS masqué (réduit les faux positifs).

### Tests

Référence : `backend/tests/memory/test_service.py::test_mask_secrets_*`.

```python
def test_mask_email():
    assert mask_secrets("écris à user@example.com") == "écris à [EMAIL]"

def test_mask_iban():
    assert mask_secrets("IBAN FR76 1234 5678 9012 3456 78") == "IBAN [BANK]"

def test_mask_card_luhn_valid():
    # 4111 1111 1111 1111 valide Luhn
    assert mask_secrets("ma carte 4111 1111 1111 1111") == "ma carte [CARD]"

def test_mask_card_luhn_invalid():
    # 1234 5678 9012 3456 ne valide pas Luhn
    assert mask_secrets("numéro 1234 5678 9012 3456") == "numéro 1234 5678 9012 3456"

def test_mask_token_bearer():
    assert mask_secrets("Authorization: Bearer abc123def456ghi789jklmnop") == "Authorization: [TOKEN]"

def test_mask_combined():
    text = "envoie à user@x.com IBAN FR76 1234 5678 9012 3456 78 carte 4111 1111 1111 1111"
    expected = "envoie à [EMAIL] IBAN [BANK] carte [CARD]"
    assert mask_secrets(text) == expected

def test_mask_idempotent():
    text = "user@x.com et 4111 1111 1111 1111"
    assert mask_secrets(mask_secrets(text)) == mask_secrets(text)
```

---

## Fonction `chunk_text(text: str, max_chars: int = 6000, overlap: int = 200) -> list[str]`

Découpe un texte en chunks selon la stratégie de la clarification Q2.

### Comportement

| Cas | Résultat |
|---|---|
| `len(text) == 0` | `['[redacted]']` (un chunk minimal, voir invariant data-model). |
| `len(text) <= max_chars` | `[text]` (un seul chunk identique). |
| `len(text) > max_chars` | Découpe par paragraphes (`\n\n`), puis par phrases (`. ! ?`), puis par mots si nécessaire. Recouvrement de 200 caractères entre chunks consécutifs. Aucun chunk ne dépasse `max_chars + overlap`. |

### Garanties

- Aucune découpe au milieu d'un mot (sauf cas extrême où un seul mot dépasse `max_chars`, alors découpe forcée).
- Concaténation `''.join(chunks)` ≠ texte original (à cause de l'overlap), mais reconstitution possible via algo dédié (hors scope F12).

### Tests

Référence : `backend/tests/memory/test_service.py::test_chunk_text_*`.

```python
def test_chunk_text_short():
    assert chunk_text("court") == ["court"]

def test_chunk_text_just_under_limit():
    text = "a" * 6000
    assert chunk_text(text) == [text]

def test_chunk_text_long_paragraphs():
    para = "Lorem ipsum. " * 200  # ~ 2 600 chars
    text = "\n\n".join([para] * 4)  # ~ 10 600 chars
    chunks = chunk_text(text, max_chars=6000, overlap=200)
    assert len(chunks) >= 2
    assert all(len(c) <= 6200 for c in chunks)

def test_chunk_text_overlap():
    text = "a" * 12000
    chunks = chunk_text(text, max_chars=6000, overlap=200)
    # Overlap : la fin du chunk i et le début du chunk i+1 partagent 200 caractères
    assert chunks[0][-200:] == chunks[1][:200]
```

---

## Fonction `embed_message(message_id, account_id, conversation_id, role, content) -> None`

Pipeline complet pour indexer un message qui vient d'être inséré.

### Signature

```python
async def embed_message(
    message_id: uuid.UUID,
    account_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
) -> None:
    """Pipeline d'indexation : masque secrets → chunk → embed → INSERT message_chunks."""
```

### Comportement

1. Ouvrir une session DB indépendante via `async_sessionmaker` (pas la session du hook).
2. Positionner le contexte RLS via `set_rls_context(session, account_id, role='PME', user_id=None)`.
3. `masked = mask_secrets(content)`.
4. `chunks = chunk_text(masked)`.
5. `embeddings = await OpenAIEmbeddings(model="text-embedding-3-small").aembed_documents(chunks)`.
   - Si exception : log warning, `embeddings = [None] * len(chunks)` (chunks insérés sans embedding, rattrapage F19).
6. INSERT N rows dans `message_chunks` (chunk_index = 0..N-1).
7. Commit.

### Garanties

- **Non-blocking** : appelée via `asyncio.create_task`, ne bloque jamais le hook.
- **Idempotent best-effort** : si le hook est déclenché 2 fois pour le même message (cas pathologique), on insère 2 jeux de chunks. Pas de contrainte UNIQUE — les recherches dédupliquent par `message_id` côté tool.
- **Tolère l'échec API** : embedding NULL toléré, marqueur de rattrapage.
- **Aucune exception ne remonte** : try/except global dans le hook (le message reste en base, l'utilisateur reçoit sa réponse).

### Tests

Référence : `backend/tests/memory/test_service.py::test_embed_message_*`.

```python
@pytest.mark.asyncio
async def test_embed_message_success(monkeypatch, db_session):
    # mock OpenAIEmbeddings.aembed_documents → retourne 1 embedding factice
    mock_embed = AsyncMock(return_value=[[0.1] * 1536])
    monkeypatch.setattr("app.modules.memory.service._embeddings_model", lambda: SimpleNamespace(aembed_documents=mock_embed))
    await embed_message(msg_id, acc_id, conv_id, "user", "test message")
    chunks = await fetch_chunks(db_session, msg_id)
    assert len(chunks) == 1
    assert chunks[0].embedding is not None

@pytest.mark.asyncio
async def test_embed_message_api_failure(monkeypatch, db_session):
    monkeypatch.setattr(..., AsyncMock(side_effect=TimeoutError))
    await embed_message(msg_id, acc_id, conv_id, "user", "test")
    chunks = await fetch_chunks(db_session, msg_id)
    assert len(chunks) == 1
    assert chunks[0].embedding is None  # rattrapage F19
```

---

## Fonction `search_history(...)`

```python
@dataclass(frozen=True)
class MessageRecallResult:
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    conversation_title: str
    role: str
    chunk_text: str
    created_at: datetime
    similarity: float


async def search_history(
    query: str,
    account_id: uuid.UUID,
    *,
    since: datetime | None = None,
    include_current_conversation: bool = False,
    current_conversation_id: uuid.UUID | None = None,
    max_results: int = 5,
    threshold: float = 0.6,
) -> list[MessageRecallResult]:
    """Recherche sémantique HNSW + filtrage RLS."""
```

### Comportement

1. Embedding de la query (`OpenAIEmbeddings.aembed_query`).
2. SELECT SQL :
   ```sql
   SELECT
       mc.message_id,
       mc.conversation_id,
       c.title AS conversation_title,
       mc.role,
       mc.chunk_text,
       mc.created_at,
       1 - (mc.embedding <=> :query_embedding) AS similarity
   FROM message_chunks mc
   JOIN conversations c ON c.id = mc.conversation_id
   WHERE mc.account_id = :account_id  -- défense en profondeur (RLS aussi en place)
     AND mc.embedding IS NOT NULL
     AND (:since IS NULL OR mc.created_at >= :since)
     AND (:include_current OR mc.conversation_id != :current_conv_id)
     AND (1 - (mc.embedding <=> :query_embedding)) > :threshold
   ORDER BY mc.embedding <=> :query_embedding ASC
   LIMIT :max_results
   ```
3. Mapping ORM → liste de `MessageRecallResult`.

### Garanties

- **Filtrage account_id** appliqué en double : WHERE applicatif + policy RLS PostgreSQL (défense en profondeur — invariant projet).
- **Threshold strict** : `> 0.6`, pas `>=`.
- **Ordre déterministe** : par distance cosinus ascendante (similarity descendante).
- **Tolère embedding API down** : exception remonte → caller (`recall_history` tool) catche et retourne `[]`.

### Tests

Référence : `backend/tests/memory/test_recall_history_tool.py` (cf. contract memory_tools.md).

---

## Fonction `purge_account_chunks(account_id: uuid.UUID) -> None`

Supprime tous les artefacts conversationnels d'un account (cf. R5).

### Comportement

```python
async def purge_account_chunks(account_id: uuid.UUID) -> None:
    """Suppression cascade complète des conversations d'un account (RGPD)."""
    async with async_sessionmaker() as session:
        await set_rls_context(session, account_id, role='ADMIN', user_id=None)
        # 1. Récupérer les thread_id (= conversation_id) pour LangGraph
        thread_ids_q = await session.execute(
            select(Conversation.id).join(User).where(User.account_id == account_id)
        )
        thread_ids = [str(row[0]) for row in thread_ids_q.all()]
        # 2. Supprimer message_chunks (cascade naturelle aussi via DELETE conversations, mais on le fait explicitement par sûreté)
        await session.execute(
            delete(MessageChunk).where(MessageChunk.account_id == account_id)
        )
        # 3. Supprimer checkpoints LangGraph (3 tables)
        for table in ('checkpoint_blobs', 'checkpoint_writes', 'checkpoints'):
            if thread_ids:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE thread_id = ANY(:ids)"),
                    {"ids": thread_ids},
                )
        # 4. Commit
        await session.commit()
```

### Garanties

- **Atomicité** : tout dans une seule transaction.
- **Idempotent** : appel répété ne fait rien la 2e fois (pas de rows à supprimer).
- **Pas de conflict avec F05** : F05 (purge RGPD) appelle cette fonction APRÈS avoir supprimé les conversations/messages (cascade SQL native). Cette fonction nettoie spécifiquement ce qui n'est pas couvert par cascade SQL (chunks insérés sans cascade vers account direct ; checkpoints LangGraph sans FK).

### Tests

Référence : `backend/tests/memory/test_purge.py`.

```python
@pytest.mark.asyncio
async def test_purge_cascade_chunks(db_session):
    # Setup : account A avec 50 chunks ; account B avec 30 chunks
    setup_account_with_chunks(db_session, "A", 50)
    setup_account_with_chunks(db_session, "B", 30)
    await purge_account_chunks(account_a.id)
    assert count_chunks_for(db_session, "A") == 0
    assert count_chunks_for(db_session, "B") == 30  # non impacté

@pytest.mark.asyncio
async def test_purge_checkpoints_langgraph(db_session, checkpointer):
    conv_id = uuid.uuid4()
    await checkpointer.aput(config={"configurable": {"thread_id": str(conv_id)}}, ...)
    # créer un account A avec une conversation conv_id
    setup_account_with_conversation(db_session, "A", conv_id)
    await purge_account_chunks(account_a.id)
    state = await checkpointer.aget(config={"configurable": {"thread_id": str(conv_id)}})
    assert state is None  # checkpoint purgé
```
