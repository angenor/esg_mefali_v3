"""T006 (F048 US1) — Le tool chat ``export_application`` génère un fichier réel.

Réf. contracts/application-creation.md T6 (D3).

Avant ce correctif, ``_export_application`` retournait un chemin factice sans
écrire de fichier. Désormais le tool DOIT :
- appeler le vrai moteur ``app.modules.applications.export.export_application`` ;
- écrire les bytes sous ``uploads/applications/{id}.{fmt}`` ;
- enregistrer un ``Document`` utilisateur (visible dans /documents) ;
- retourner une URL réelle.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.application_tools import export_application

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_config():
    """RunnableConfig minimal (db AsyncMock + user/account/conversation)."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return {
        "configurable": {
            "db": db,
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "account_id": uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
            "conversation_id": uuid.uuid4(),
        }
    }


def _make_application() -> MagicMock:
    app = MagicMock()
    app.id = uuid.uuid4()
    app.user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    app.account_id = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
    app.project_id = None  # pas de gating sans projet/offre
    app.offer_id = None
    fund = MagicMock()
    fund.name = "GCF"
    app.fund = fund
    app.sections = {"company_presentation": {"title": "Présentation", "content": "<p>X</p>"}}
    return app


async def test_export_writes_real_file_and_registers_document(
    tmp_path: Path, mock_config,
):
    """Le tool écrit un fichier réel et enregistre un Document."""
    application = _make_application()
    fake_uploads = tmp_path / "uploads"

    registered = MagicMock()
    registered.id = uuid.uuid4()

    with (
        patch(
            "app.modules.applications.service.get_application_by_id",
            new_callable=AsyncMock,
            return_value=application,
        ),
        patch(
            "app.modules.applications.export.export_application",
            new_callable=AsyncMock,
            return_value=(b"DOCX-BYTES-CONTENT", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "dossier_gcf.docx"),
        ) as mock_real_export,
        patch(
            "app.modules.documents.service.register_generated_document",
            new_callable=AsyncMock,
            return_value=registered,
        ) as mock_register,
        patch("app.modules.documents.service.UPLOADS_DIR", fake_uploads),
    ):
        result = await export_application.ainvoke(
            {"application_id": str(application.id), "format": "docx"},
            config=mock_config,
        )

    # 1. Le vrai moteur d'export a été appelé.
    mock_real_export.assert_awaited_once()

    # 2. Un fichier réel a été écrit sous uploads/applications/.
    written = list((fake_uploads / "applications").glob("*.docx"))
    assert written, "aucun fichier .docx écrit sous uploads/applications/"
    assert written[0].read_bytes() == b"DOCX-BYTES-CONTENT"

    # 3. Un Document a été enregistré (visible /documents).
    mock_register.assert_awaited_once()

    # 4. Le tool ne renvoie PAS le chemin factice legacy.
    assert "export" in result.lower() or "docx" in result.lower()


async def test_register_generated_document_inserts_final_row(db_session):
    """register_generated_document insère une ligne Document (statut final)."""
    from sqlalchemy import select

    from app.models.document import Document, DocumentStatus
    from app.modules.documents.service import register_generated_document

    doc = await register_generated_document(
        db_session,
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        storage_path="uploads/applications/abc.docx",
        original_filename="dossier_gcf.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=2048,
    )
    rows = (await db_session.execute(select(Document))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == doc.id
    assert rows[0].status == DocumentStatus.analyzed
    assert rows[0].storage_path == "uploads/applications/abc.docx"


async def test_export_application_not_found_returns_message(mock_config):
    """Dossier introuvable → message d'erreur clair (pas de fichier)."""
    with patch(
        "app.modules.applications.service.get_application_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await export_application.ainvoke(
            {"application_id": str(uuid.uuid4()), "format": "pdf"},
            config=mock_config,
        )
    assert "introuvable" in result.lower() or "erreur" in result.lower()
