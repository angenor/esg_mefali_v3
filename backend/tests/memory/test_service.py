"""Tests F12 du service mémoire : masquage, chunking, embed.

Couvre les contrats ``contracts/memory_service.md`` (mask_secrets, chunk_text,
embed_message). Les tests d'embedding utilisent un mock de
``OpenAIEmbeddings.aembed_documents`` pour rester déterministes.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.message_chunk import MessageChunk
from app.modules.memory.service import (
    BANK_MARKER,
    CARD_MARKER,
    EMAIL_MARKER,
    REDACTED_PLACEHOLDER,
    TOKEN_MARKER,
    chunk_text,
    embed_message,
    mask_secrets,
)


# ─── mask_secrets ────────────────────────────────────────────────────


def test_mask_email() -> None:
    assert mask_secrets("écris à user@example.com") == f"écris à {EMAIL_MARKER}"


def test_mask_iban() -> None:
    assert (
        mask_secrets("IBAN FR76 1234 5678 9012 3456 78")
        == f"IBAN {BANK_MARKER}"
    )


def test_mask_card_luhn_valid() -> None:
    # 4111 1111 1111 1111 → Luhn valide (carte test Visa)
    assert mask_secrets("ma carte 4111 1111 1111 1111") == f"ma carte {CARD_MARKER}"


def test_mask_card_luhn_invalid() -> None:
    # 1234 5678 9012 3456 → Luhn invalide → non masqué
    assert (
        mask_secrets("numéro 1234 5678 9012 3456")
        == "numéro 1234 5678 9012 3456"
    )


def test_mask_token_bearer() -> None:
    assert (
        mask_secrets("Authorization: Bearer abc123def456ghi789jklmnop")
        == f"{TOKEN_MARKER}"
    )


def test_mask_token_api_key() -> None:
    assert (
        mask_secrets("api_key=sk_live_abc123def456ghi789jklm")
        == f"{TOKEN_MARKER}"
    )


def test_mask_combined() -> None:
    text_in = "envoie à user@x.com IBAN FR76 1234 5678 9012 3456 78 carte 4111 1111 1111 1111"
    expected = f"envoie à {EMAIL_MARKER} IBAN {BANK_MARKER} carte {CARD_MARKER}"
    assert mask_secrets(text_in) == expected


def test_mask_idempotent() -> None:
    text_in = "user@x.com et 4111 1111 1111 1111"
    once = mask_secrets(text_in)
    twice = mask_secrets(once)
    assert once == twice


def test_mask_empty_string() -> None:
    assert mask_secrets("") == ""


def test_mask_no_secret() -> None:
    """Un texte sans secret reste inchangé."""
    text_in = "Bonjour, je suis Sarah, dirigeante d'une PME agroalimentaire."
    assert mask_secrets(text_in) == text_in


# ─── chunk_text ──────────────────────────────────────────────────────


def test_chunk_text_short() -> None:
    assert chunk_text("court") == ["court"]


def test_chunk_text_just_under_limit() -> None:
    text_value = "a" * 6000
    assert chunk_text(text_value) == [text_value]


def test_chunk_text_long_paragraphs() -> None:
    """Un texte de 4 paragraphes ~2 600 c → ≥ 2 chunks ≤ 6 200 c."""
    para = "Lorem ipsum dolor sit amet. " * 100  # ~2 800 c
    text_value = "\n\n".join([para] * 4)  # ~11 200 c
    chunks = chunk_text(text_value, max_chars=6000, overlap=200)
    assert len(chunks) >= 2
    assert all(len(c) <= 6200 for c in chunks)


def test_chunk_text_empty_returns_redacted() -> None:
    assert chunk_text("") == [REDACTED_PLACEHOLDER]


def test_chunk_text_overlap_present() -> None:
    """Sur un texte très long, deux chunks consécutifs partagent l'overlap."""
    text_value = "a" * 12000
    chunks = chunk_text(text_value, max_chars=6000, overlap=200)
    assert len(chunks) >= 2
    # Au moins une paire de chunks consécutifs doit partager au minimum
    # quelques caractères communs (overlap appliqué).
    found_overlap = False
    for i in range(len(chunks) - 1):
        if chunks[i][-100:] in chunks[i + 1][:600]:
            found_overlap = True
            break
    assert found_overlap, "Aucun overlap détecté entre chunks consécutifs"


# ─── embed_message ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_message_success(monkeypatch, db_session) -> None:
    """Un message simple est embeddé et inséré sans erreur (1 chunk)."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    # Setup minimal : account + user + conversation + message
    account = await make_account(db_session, name="EmbedTest")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id,
        account_id=account.id,
        title="Test conv",
    )
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="user",
        content="Bonjour, je veux faire mon bilan ESG.",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    # Mock embedding
    fake_embed = AsyncMock(return_value=[[0.1] * 1536])
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: SimpleNamespace(aembed_documents=fake_embed),
    )

    await embed_message(
        message_id=msg.id,
        account_id=account.id,
        conversation_id=conv.id,
        role="user",
        content=msg.content,
        session=db_session,
    )

    # Vérifier qu'un chunk a été inséré
    result = await db_session.execute(
        select(MessageChunk).where(MessageChunk.message_id == msg.id)
    )
    chunks = list(result.scalars().all())
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].account_id == account.id
    assert chunks[0].role == "user"
    # Sur SQLite, embedding est stocké comme Text (la sérialisation peut varier)


@pytest.mark.asyncio
async def test_embed_message_api_failure(monkeypatch, db_session) -> None:
    """Si l'API d'embedding échoue, les chunks sont insérés sans embedding."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="EmbedFail")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="Fail conv",
    )
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="user",
        content="Texte court de test",
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    fake_embed = AsyncMock(side_effect=TimeoutError("API timeout"))
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: SimpleNamespace(aembed_documents=fake_embed),
    )

    # Ne doit PAS lever
    await embed_message(
        message_id=msg.id,
        account_id=account.id,
        conversation_id=conv.id,
        role="user",
        content=msg.content,
        session=db_session,
    )

    # Le chunk doit exister, embedding NULL
    result = await db_session.execute(
        select(MessageChunk).where(MessageChunk.message_id == msg.id)
    )
    chunks = list(result.scalars().all())
    assert len(chunks) == 1
    assert chunks[0].embedding is None


@pytest.mark.asyncio
async def test_embed_message_masks_secrets(monkeypatch, db_session) -> None:
    """L'embedding insère le texte MASQUÉ (pas l'original)."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="MaskEmbed")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="Mask conv",
    )
    db_session.add(conv)
    await db_session.flush()

    secret_content = "Mon email est me@example.com et carte 4111 1111 1111 1111"
    msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="user",
        content=secret_content,
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    fake_embed = AsyncMock(return_value=[[0.2] * 1536])
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: SimpleNamespace(aembed_documents=fake_embed),
    )

    await embed_message(
        message_id=msg.id,
        account_id=account.id,
        conversation_id=conv.id,
        role="user",
        content=secret_content,
        session=db_session,
    )

    result = await db_session.execute(
        select(MessageChunk).where(MessageChunk.message_id == msg.id)
    )
    chunks = list(result.scalars().all())
    assert len(chunks) == 1
    assert "me@example.com" not in chunks[0].chunk_text
    assert "4111 1111 1111 1111" not in chunks[0].chunk_text
    assert EMAIL_MARKER in chunks[0].chunk_text
    assert CARD_MARKER in chunks[0].chunk_text


# ─── search_history (mocks) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_history_query_embedding_failure(monkeypatch) -> None:
    """Si l'embedding de la query échoue, search_history retourne []."""
    from app.modules.memory.service import search_history

    failing_model = SimpleNamespace(
        aembed_query=AsyncMock(side_effect=TimeoutError("API down")),
    )
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: failing_model,
    )
    out = await search_history(
        query="test",
        account_id=uuid.uuid4(),
    )
    assert out == []


@pytest.mark.asyncio
async def test_search_history_invalid_embedding_dimension(monkeypatch) -> None:
    """Si l'embedding retourne une dimension incorrecte, retour []."""
    from app.modules.memory.service import search_history

    bad_model = SimpleNamespace(
        aembed_query=AsyncMock(return_value=[0.1] * 100),  # 100 != 1536
    )
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: bad_model,
    )
    out = await search_history(
        query="test",
        account_id=uuid.uuid4(),
    )
    assert out == []


@pytest.mark.asyncio
async def test_search_history_with_session_handles_sql_error(
    monkeypatch, db_session
) -> None:
    """Si SQL échoue (ex: pas de pgvector en SQLite), retour [] sans crash."""
    from app.modules.memory.service import search_history

    ok_model = SimpleNamespace(
        aembed_query=AsyncMock(return_value=[0.0] * 1536),
    )
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: ok_model,
    )
    # SQLite n'a pas pgvector → SQL `<=>` opérateur va échouer.
    out = await search_history(
        query="test",
        account_id=uuid.uuid4(),
        session=db_session,
    )
    assert out == []


@pytest.mark.asyncio
async def test_purge_account_chunks_runs_with_real_session(monkeypatch, db_session) -> None:
    """purge_account_chunks ouvre une session via async_session_factory réel.

    On override async_session_factory pour pointer vers la session de test.
    """
    from tests.conftest import test_session_factory
    from app.modules.memory.service import purge_account_chunks

    monkeypatch.setattr(
        "app.modules.memory.service.async_session_factory",
        test_session_factory,
    )

    # Pas de chunks ajoutés : la purge doit être un no-op silencieux
    await purge_account_chunks(uuid.uuid4())
    # Aucune exception attendue


@pytest.mark.asyncio
async def test_embed_message_empty_content_creates_redacted_chunk(
    monkeypatch, db_session
) -> None:
    """Un message vide ou intégralement masqué génère un chunk '[redacted]'."""
    from tests.conftest import make_account, make_pme_user
    from app.models.conversation import Conversation
    from app.models.message import Message

    account = await make_account(db_session, name="EmptyContent")
    user = await make_pme_user(db_session, account=account)
    conv = Conversation(
        user_id=user.id, account_id=account.id, title="Empty"
    )
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        account_id=account.id,
        role="user",
        content="",  # vide
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()

    fake_embed = AsyncMock(return_value=[[0.0] * 1536])
    monkeypatch.setattr(
        "app.modules.memory.service._embeddings_model",
        lambda: SimpleNamespace(aembed_documents=fake_embed),
    )

    await embed_message(
        message_id=msg.id,
        account_id=account.id,
        conversation_id=conv.id,
        role="user",
        content="",
        session=db_session,
    )

    chunks = (
        await db_session.execute(
            select(MessageChunk).where(MessageChunk.message_id == msg.id)
        )
    ).scalars().all()
    assert len(chunks) == 1
    assert chunks[0].chunk_text == REDACTED_PLACEHOLDER
