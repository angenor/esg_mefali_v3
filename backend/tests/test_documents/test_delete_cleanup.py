"""049 (FR-014, SC-005) — Nettoyage des références checklist à la suppression.

Un document rattaché à plusieurs items / dossiers du compte, supprimé via
``delete_document``, fait repasser TOUS les items concernés à « missing » sans
casser la checklist (statut dérivé de la présence d'un document valide).
"""

import uuid

import pytest

from app.models.application import ApplicationStatus, FundApplication, TargetType
from app.models.document import Document, DocumentStatus
from app.models.financing import AccessType, Fund, FundStatus, FundType
from tests.conftest import make_account, make_pme_user


async def _make_fund(db_session) -> Fund:
    fund = Fund(
        name="GCF Test",
        organization="GCF",
        fund_type=FundType.multilateral,
        description="Fonds test",
        eligibility_criteria={},
        sectors_eligible=["agriculture"],
        required_documents=[],
        esg_requirements={},
        status=FundStatus.active,
        access_type=AccessType.direct,
        application_process=[],
    )
    db_session.add(fund)
    await db_session.flush()
    return fund


async def _make_document(db_session, *, user, account) -> Document:
    doc = Document(
        user_id=user.id,
        account_id=account.id,
        filename=f"stored_{uuid.uuid4().hex[:8]}.pdf",
        original_filename="partage.pdf",
        mime_type="application/pdf",
        file_size=2048,
        storage_path=f"uploads/{uuid.uuid4().hex}.pdf",
        status=DocumentStatus.uploaded,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


def _provided_item(key: str, name: str, document_id: uuid.UUID) -> dict:
    return {
        "key": key,
        "name": name,
        "status": "provided",
        "document_id": str(document_id),
        "required_by": "fund_direct",
    }


@pytest.mark.asyncio
async def test_delete_document_clears_references_in_two_applications(db_session):
    """Un document rattaché à 2 items / 2 dossiers → les 2 repassent missing."""
    from app.modules.documents.service import delete_document

    account = await make_account(db_session, name="Tenant A")
    user = await make_pme_user(db_session, account=account)
    fund = await _make_fund(db_session)
    doc = await _make_document(db_session, user=user, account=account)

    app1 = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=account.id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=[_provided_item("company_registration", "RCCM", doc.id)],
    )
    app2 = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=account.id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=[_provided_item("esg_report", "Rapport ESG", doc.id)],
    )
    db_session.add_all([app1, app2])
    await db_session.commit()

    await delete_document(db_session, doc)
    await db_session.commit()

    await db_session.refresh(app1)
    await db_session.refresh(app2)

    item1 = app1.checklist[0]
    item2 = app2.checklist[0]
    assert item1["status"] == "missing"
    assert item1["document_id"] is None
    assert item2["status"] == "missing"
    assert item2["document_id"] is None
    # Le document est bien supprimé.
    assert await db_session.get(Document, doc.id) is None


@pytest.mark.asyncio
async def test_delete_document_clears_multiple_items_same_application(db_session):
    """Même document sur 2 items du MÊME dossier → les 2 repassent missing,
    progression recalculée à 0."""
    from app.modules.applications.schemas import compute_checklist_progress
    from app.modules.documents.service import delete_document

    account = await make_account(db_session, name="Tenant A")
    user = await make_pme_user(db_session, account=account)
    fund = await _make_fund(db_session)
    doc = await _make_document(db_session, user=user, account=account)

    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=account.id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=[
            _provided_item("company_registration", "RCCM", doc.id),
            _provided_item("esg_report", "Rapport ESG", doc.id),
        ],
    )
    db_session.add(app)
    await db_session.commit()

    await delete_document(db_session, doc)
    await db_session.commit()
    await db_session.refresh(app)

    assert all(it["status"] == "missing" for it in app.checklist)
    progress = compute_checklist_progress(list(app.checklist))
    assert progress.provided == 0
    assert progress.total == 2
