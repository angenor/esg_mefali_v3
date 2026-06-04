"""Tests unitaires du text splitting et stockage embeddings (T043)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_split_text_into_chunks():
    """Le text splitter doit decouper le texte en segments avec overlap."""
    from app.modules.documents.service import _split_text

    text = "Premier paragraphe. " * 100 + "\n\n" + "Deuxieme paragraphe. " * 100
    chunks = _split_text(text)

    assert len(chunks) > 1
    # Chaque chunk doit etre non vide
    for chunk in chunks:
        assert len(chunk) > 0
    # Les chunks doivent etre plus petits que le texte original
    assert all(len(c) <= 1200 for c in chunks)  # chunk_size + marge


@pytest.mark.asyncio
async def test_split_short_text():
    """Un texte court ne doit produire qu'un seul chunk."""
    from app.modules.documents.service import _split_text

    text = "Texte court de test."
    chunks = _split_text(text)

    assert len(chunks) == 1
    assert chunks[0] == text


@pytest.mark.asyncio
async def test_store_embeddings_creates_chunks():
    """store_embeddings doit creer des DocumentChunk en BDD."""
    from app.modules.documents.service import store_embeddings

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    document_id = uuid.uuid4()
    text = "Paragraphe de test. " * 100

    # Mock l'API d'embedding
    with patch(
        "app.modules.documents.service._get_embeddings",
        new_callable=AsyncMock,
        return_value=[[0.1] * 1536] * 5,
    ):
        chunks_count = await store_embeddings(mock_db, document_id, text)

    assert chunks_count > 0
    assert mock_db.add.called


class _NestedCtx:
    """Faux context manager pour ``db.begin_nested()`` (SAVEPOINT)."""

    def __init__(self) -> None:
        self.entered = False

    async def __aenter__(self):
        self.entered = True
        return None

    async def __aexit__(self, *exc):
        # Ne supprime pas l'exception : analyze_document doit la capturer lui-même.
        return False


@pytest.mark.asyncio
async def test_analyze_document_embedding_failure_is_isolated_and_non_blocking():
    """Régression : un échec de stockage d'embeddings (ex. dimension de vecteur
    incohérente avec ``document_chunks.embedding`` — 1536 vs vector(1024) post
    mig. 043) NE DOIT PAS se propager hors de ``analyze_document`` NI empoisonner
    la session.

    Il est isolé dans un SAVEPOINT (``db.begin_nested()``) : sans cela, l'échec
    du ``flush()`` met la transaction PostgreSQL en état « aborted » et toute
    opération suivante lève « transaction has been rolled back », cassant la
    réponse chat alors que l'analyse a réussi.
    """
    from app.modules.documents import service as doc_service

    document = MagicMock()
    document.id = uuid.uuid4()
    document.storage_path = "uploads/fake.pdf"
    document.original_filename = "fake.pdf"
    document.mime_type = "application/pdf"
    document.document_type = None

    nested = _NestedCtx()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.begin_nested = MagicMock(return_value=nested)

    analysis_output = MagicMock()
    analysis_output.summary = "Organigramme NÉLO TECH"
    analysis_output.key_findings = ["43% de féminisation"]
    analysis_output.structured_data = {}
    analysis_output.esg_relevant_info = {}  # dict simple → pas de model_dump
    analysis_output.document_type.value = "autre"

    mock_path = MagicMock()
    mock_path.return_value.exists.return_value = True

    with patch.object(doc_service, "Path", mock_path), patch.object(
        doc_service, "extract_text", new_callable=AsyncMock,
        return_value="Texte extrait de l'organigramme NÉLO TECH SARL, 42 employés.",
    ), patch(
        "app.chains.analysis.analyze_document_text",
        new_callable=AsyncMock, return_value=analysis_output,
    ), patch.object(
        doc_service, "store_embeddings", new_callable=AsyncMock,
        side_effect=Exception("expected 1024 dimensions, not 1536"),
    ) as mock_store:
        # NE DOIT PAS lever malgré l'échec du stockage d'embeddings.
        analysis = await doc_service.analyze_document(mock_db, document)

    # L'analyse aboutit quand même.
    assert analysis is not None
    # Le stockage d'embeddings a bien été tenté…
    mock_store.assert_awaited_once()
    # …mais DANS un SAVEPOINT (isolation de la session).
    mock_db.begin_nested.assert_called_once()
    assert nested.entered is True


@pytest.mark.asyncio
async def test_search_similar_chunks():
    """search_similar_chunks doit retourner des resultats."""
    from app.modules.documents.service import search_similar_chunks

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock l'API d'embedding pour la query
    with patch(
        "app.modules.documents.service._get_embeddings",
        new_callable=AsyncMock,
        return_value=[[0.1] * 1536],
    ):
        results = await search_similar_chunks(
            mock_db, uuid.uuid4(), "question test",
        )

    assert isinstance(results, list)
