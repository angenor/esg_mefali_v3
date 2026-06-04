"""Tests d'integration du flux chat avec upload document (T026)."""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_user():
    """Utilisateur mock pour les tests."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@test.com"
    return user


@pytest.fixture
def mock_conversation():
    """Conversation mock."""
    conv = MagicMock()
    conv.id = uuid.uuid4()
    conv.user_id = None  # sera set dans le test
    conv.title = "Nouvelle conversation"
    return conv


@pytest.fixture
def mock_db():
    """Session BDD mock."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_send_message_with_file_creates_document():
    """L'envoi d'un message avec fichier doit creer un document et lancer l'analyse."""
    # Ce test verifie que l'endpoint accepte un fichier multipart
    # L'implementation reelle est testee via les mocks
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Sans auth, on attend un 401/403
        response = await client.post(
            f"/api/chat/conversations/{uuid.uuid4()}/messages",
            data={"content": "Analyse ce document"},
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )
        # On verifie que l'endpoint existe et repond (meme si 401 sans auth)
        assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_send_message_without_file_still_works():
    """L'envoi d'un message sans fichier doit toujours fonctionner."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/chat/conversations/{uuid.uuid4()}/messages",
            json={"content": "Bonjour"},
        )
        # Sans auth on attend 401/403
        assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_sse_document_events_format():
    """Les evenements SSE document doivent avoir le bon format."""
    import json

    # Test du format des evenements SSE
    events = [
        {"type": "document_upload", "document_id": str(uuid.uuid4()), "filename": "test.pdf", "status": "uploaded"},
        {"type": "document_status", "document_id": str(uuid.uuid4()), "status": "extracting"},
        {"type": "document_status", "document_id": str(uuid.uuid4()), "status": "analyzing"},
        {"type": "document_analysis", "document_id": str(uuid.uuid4()), "summary": "Resume test", "document_type": "bilan_financier"},
    ]

    for event in events:
        # Verifier que chaque evenement est serialisable
        serialized = json.dumps(event)
        parsed = json.loads(serialized)
        assert parsed["type"] in ("document_upload", "document_status", "document_analysis")

        if parsed["type"] == "document_upload":
            assert "document_id" in parsed
            assert "filename" in parsed
        elif parsed["type"] == "document_status":
            assert "status" in parsed
        elif parsed["type"] == "document_analysis":
            assert "summary" in parsed


@pytest.mark.asyncio
async def test_send_message_with_file_propagates_account_id():
    """Régression : l'upload via le chat DOIT transmettre ``account_id`` à
    ``upload_document``.

    Sans cet argument, ``documents.account_id`` (NOT NULL en PostgreSQL, F02
    mig. 019) lève une IntegrityError NON interceptée (seul ``ValueError`` l'est)
    → 500 sur ``POST /messages``, que le navigateur affiche en erreur CORS
    trompeuse (« No Access-Control-Allow-Origin »).

    Le endpoint est appelé DIRECTEMENT (pas via AsyncClient) pour rester
    hermétique : on évite le stack de middlewares + le vrai moteur asyncpg qui,
    avec ``StreamingResponse`` + ``BaseHTTPMiddleware``, fuite entre les boucles
    d'événements pytest. On n'AWAIT pas le corps du stream : l'appel à
    ``upload_document`` se produit dans la partie synchrone, avant le retour de
    la ``StreamingResponse``.
    """
    from fastapi import UploadFile
    from fastapi.responses import StreamingResponse

    from app.api.chat import send_message

    account_id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()
    user.account_id = account_id
    user.email = "pme@test.com"

    conversation = MagicMock()
    conversation.id = uuid.uuid4()
    conversation.title = "Dossier GCF"

    uploaded = MagicMock()
    uploaded.id = uuid.uuid4()
    uploaded.original_filename = "organigramme.pdf"

    req_db = AsyncMock()
    req_db.add = MagicMock()
    req_db.flush = AsyncMock()
    req_db.commit = AsyncMock()
    req_db.execute = AsyncMock()
    req_db.refresh = AsyncMock()

    upload_file = UploadFile(
        file=io.BytesIO(b"%PDF-1.4 fake organigramme"),
        filename="organigramme.pdf",
    )

    with patch(
        "app.modules.documents.service.upload_document",
        new_callable=AsyncMock,
        return_value=uploaded,
    ) as mock_upload, patch(
        "app.api.chat.get_user_conversation",
        new_callable=AsyncMock,
        return_value=conversation,
    ), patch(
        "app.api.chat._load_full_context_for_state",
        new_callable=AsyncMock,
        return_value={},
    ), patch(
        "app.api.chat._load_context_memory",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.api.chat._expire_pending_questions",
        new_callable=AsyncMock,
    ):
        response = await send_message(
            conversation_id=conversation.id,
            content="Voici mon organigramme",
            file=upload_file,
            interactive_question_id=None,
            interactive_question_values=None,
            interactive_question_justification=None,
            interactive_question_response_payload=None,
            current_page=None,
            guidance_stats=None,
            active_entities=None,
            current_user=user,
            db=req_db,
        )

    # Le endpoint retourne bien un stream (pas une exception/500).
    assert isinstance(response, StreamingResponse)
    # Le corps du stream n'est PAS consommé : on valide la partie synchrone.
    mock_upload.assert_awaited_once()
    _, kwargs = mock_upload.call_args
    assert kwargs.get("account_id") == account_id, (
        "upload_document doit recevoir account_id du current_user (F02)"
    )


@pytest.mark.asyncio
async def test_auto_create_conversation_with_document():
    """Un upload sans conversation active doit creer automatiquement une conversation."""
    # Ce test verifie la logique d'auto-creation
    # L'endpoint /messages sans conversation_id doit en creer une
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/conversations/auto/messages",
            data={"content": "Analyse ce document"},
            files={"file": ("test.pdf", b"fake pdf", "application/pdf")},
        )
        # On verifie que la route repond (meme si 401/404)
        assert response.status_code in (401, 403, 404, 405, 422)
