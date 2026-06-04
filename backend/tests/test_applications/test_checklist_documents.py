"""049 — Fourniture des documents de la checklist.

Couvre la sérialisation enrichie (statut effectif + sous-objet document), le
rattachement / détachement atomique par item (verrou de ligne), la sécurité
multi-tenant (403), les erreurs 404/422, l'audit, et la progression (détail +
liste). TDD : ces tests sont écrits AVANT l'implémentation.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.core.audit_context import source_of_change_scope
from app.main import app as fastapi_app
from app.models.application import ApplicationStatus, FundApplication, TargetType
from app.models.audit_log import AuditLog
from app.models.document import Document, DocumentStatus
from app.models.financing import AccessType, Fund, FundStatus, FundType
from tests.conftest import make_account, make_pme_user


# --------------------------------------------------------------------------
# Helpers de construction (entités réelles, SQLite in-memory)
# --------------------------------------------------------------------------


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


async def _make_document(
    db_session,
    *,
    user,
    account,
    filename: str = "rccm_2026.pdf",
    mime: str = "application/pdf",
) -> Document:
    doc = Document(
        user_id=user.id,
        account_id=account.id if account is not None else None,
        filename=f"stored_{uuid.uuid4().hex[:8]}.pdf",
        original_filename=filename,
        mime_type=mime,
        file_size=2048,
        storage_path=f"uploads/{uuid.uuid4().hex}.pdf",
        status=DocumentStatus.uploaded,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


def _default_checklist() -> list[dict]:
    return [
        {
            "key": "company_registration",
            "name": "Registre de commerce (RCCM)",
            "status": "missing",
            "document_id": None,
            "required_by": "fund_direct",
        },
        {
            "key": "esg_report",
            "name": "Rapport d'évaluation ESG",
            "status": "missing",
            "document_id": None,
            "required_by": "fund_direct",
        },
    ]


async def _make_application(
    db_session, *, user, account, fund, checklist: list[dict] | None = None
) -> FundApplication:
    app = FundApplication(
        user_id=user.id,
        fund_id=fund.id,
        account_id=account.id,
        target_type=TargetType.fund_direct,
        status=ApplicationStatus.draft,
        sections={},
        checklist=checklist if checklist is not None else _default_checklist(),
    )
    db_session.add(app)
    await db_session.flush()
    return app


@pytest.fixture
async def env(db_session):
    """Account + user PME + fund + application (2 items « missing ») + document."""
    account = await make_account(db_session, name="Tenant A")
    user = await make_pme_user(db_session, account=account)
    fund = await _make_fund(db_session)
    application = await _make_application(
        db_session, user=user, account=account, fund=fund
    )
    document = await _make_document(db_session, user=user, account=account)
    await db_session.commit()
    return {
        "db": db_session,
        "account": account,
        "user": user,
        "fund": fund,
        "app": application,
        "doc": document,
    }


@pytest.fixture
def auth_client():
    """Fabrique un AsyncClient avec ``get_current_user`` surchargé par un user.

    Usage : ``async with auth_client(user, account) as ac: ...``.
    """

    def _make(user, account):
        mock = MagicMock()
        mock.id = user.id
        mock.account_id = account.id
        mock.is_active = True
        fastapi_app.dependency_overrides[get_current_user] = lambda: mock
        return AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        )

    yield _make
    fastapi_app.dependency_overrides.pop(get_current_user, None)


def _count_audit_checklist_rows(db_session):
    return db_session.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.field == "checklist")
    )


# ==========================================================================
# T005 — Sérialisation enrichie (statut effectif + sous-objet document)
# ==========================================================================


@pytest.mark.asyncio
async def test_serialize_provided_item_exposes_document(env):
    """Item avec document_id valide → status='provided' + document peuplé."""
    from app.modules.applications.service import (
        attach_checklist_document,
        serialize_checklist,
    )

    db, app, doc = env["db"], env["app"], env["doc"]
    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    items = await serialize_checklist(db, app)
    rccm = next(it for it in items if it["key"] == "company_registration")
    assert rccm["status"] == "provided"
    assert rccm["document"] is not None
    assert rccm["document"]["original_filename"] == "rccm_2026.pdf"
    assert rccm["document"]["mime_type"] == "application/pdf"

    esg = next(it for it in items if it["key"] == "esg_report")
    assert esg["status"] == "missing"
    assert esg["document"] is None


@pytest.mark.asyncio
async def test_serialize_deleted_document_is_effective_missing(env):
    """document_id pointant un document supprimé → status='missing', document=null."""
    from app.modules.applications.service import serialize_checklist

    db, app = env["db"], env["app"]
    # Référence stockée volontairement « cassée » (document inexistant).
    checklist = list(app.checklist)
    checklist[0] = {**checklist[0], "status": "provided", "document_id": str(uuid.uuid4())}
    app.checklist = checklist
    await db.commit()

    items = await serialize_checklist(db, app)
    assert items[0]["status"] == "missing"
    assert items[0]["document"] is None
    assert items[0]["document_id"] is None


@pytest.mark.asyncio
async def test_progress_counts_effective_provided(env):
    """checklist_progress = compte exact des items effectivement provided."""
    from app.modules.applications.schemas import compute_checklist_progress
    from app.modules.applications.service import (
        attach_checklist_document,
        serialize_checklist,
    )

    db, app, doc = env["db"], env["app"], env["doc"]
    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    items = await serialize_checklist(db, app)
    progress = compute_checklist_progress(items)
    assert progress.provided == 1
    assert progress.total == 2


@pytest.mark.asyncio
async def test_progress_empty_checklist_total_zero(db_session):
    """Checklist vide → total=0 (FR-017)."""
    from app.modules.applications.schemas import compute_checklist_progress
    from app.modules.applications.service import serialize_checklist

    account = await make_account(db_session)
    user = await make_pme_user(db_session, account=account)
    fund = await _make_fund(db_session)
    app = await _make_application(
        db_session, user=user, account=account, fund=fund, checklist=[]
    )
    await db_session.commit()

    items = await serialize_checklist(db_session, app)
    progress = compute_checklist_progress(items)
    assert items == []
    assert progress.total == 0
    assert progress.provided == 0


# ==========================================================================
# T009 — Rattacher / remplacer (PUT) — service + endpoint
# ==========================================================================


@pytest.mark.asyncio
async def test_attach_missing_to_provided(env):
    """Nominal : missing → provided, document peuplé, progression incrémentée."""
    from app.modules.applications.service import attach_checklist_document

    db, app, doc = env["db"], env["app"], env["doc"]
    result = await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    assert result["item"]["status"] == "provided"
    assert result["item"]["document"]["original_filename"] == "rccm_2026.pdf"
    assert result["checklist_progress"] == {"provided": 1, "total": 2}


@pytest.mark.asyncio
async def test_attach_cross_account_raises(env):
    """Document d'un autre compte → DocumentCrossAccount (→ 403, FR-010, SC-003)."""
    from app.modules.applications.service import (
        DocumentCrossAccount,
        attach_checklist_document,
    )

    db, app = env["db"], env["app"]
    other_account = await make_account(db, name="Tenant B")
    other_user = await make_pme_user(db, account=other_account)
    foreign_doc = await _make_document(
        db, user=other_user, account=other_account, filename="foreign.pdf"
    )
    await db.commit()

    with pytest.raises(DocumentCrossAccount):
        await attach_checklist_document(db, app, "company_registration", foreign_doc.id)


@pytest.mark.asyncio
async def test_attach_legacy_document_same_owner_succeeds(env):
    """Document legacy (account_id NULL) du même propriétaire → rattachable (D6)."""
    from app.modules.applications.service import attach_checklist_document

    db, app, user = env["db"], env["app"], env["user"]
    legacy_doc = await _make_document(db, user=user, account=None, filename="legacy.pdf")
    await db.commit()

    result = await attach_checklist_document(db, app, "company_registration", legacy_doc.id)
    assert result["item"]["status"] == "provided"


@pytest.mark.asyncio
async def test_attach_legacy_document_other_owner_raises(env):
    """Document legacy (account_id NULL) d'un autre propriétaire → refusé (FR-010)."""
    from app.modules.applications.service import (
        DocumentCrossAccount,
        attach_checklist_document,
    )

    db, app = env["db"], env["app"]
    other_account = await make_account(db, name="Tenant B")
    other_user = await make_pme_user(db, account=other_account)
    legacy_foreign = await _make_document(db, user=other_user, account=None)
    await db.commit()

    with pytest.raises(DocumentCrossAccount):
        await attach_checklist_document(db, app, "company_registration", legacy_foreign.id)


@pytest.mark.asyncio
async def test_attach_unknown_item_raises(env):
    """item_key inconnu → ApplicationItemNotFound (→ 404)."""
    from app.modules.applications.service import (
        ApplicationItemNotFound,
        attach_checklist_document,
    )

    db, app, doc = env["db"], env["app"], env["doc"]
    with pytest.raises(ApplicationItemNotFound):
        await attach_checklist_document(db, app, "does_not_exist", doc.id)


@pytest.mark.asyncio
async def test_attach_unknown_document_raises(env):
    """document_id inconnu → DocumentNotFound (→ 404)."""
    from app.modules.applications.service import (
        DocumentNotFound,
        attach_checklist_document,
    )

    db, app = env["db"], env["app"]
    with pytest.raises(DocumentNotFound):
        await attach_checklist_document(db, app, "company_registration", uuid.uuid4())


@pytest.mark.asyncio
async def test_attach_creates_one_audit_row(env):
    """Une ligne d'audit (field='checklist') est créée au rattachement (SC-006)."""
    from app.modules.applications.service import attach_checklist_document

    db, app, doc = env["db"], env["app"], env["doc"]
    before = (await _count_audit_checklist_rows(db)).scalar_one()
    with source_of_change_scope("manual"):
        await attach_checklist_document(db, app, "company_registration", doc.id)
        await db.commit()
    after = (await _count_audit_checklist_rows(db)).scalar_one()
    assert after - before == 1


@pytest.mark.asyncio
async def test_attach_leaves_other_items_unchanged(env):
    """Atomicité par item (FR-021) : seul l'item ciblé est modifié."""
    from app.modules.applications.service import attach_checklist_document

    db, app, doc = env["db"], env["app"], env["doc"]
    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    esg = next(it for it in app.checklist if it["key"] == "esg_report")
    assert esg["status"] == "missing"
    assert esg["document_id"] is None


@pytest.mark.asyncio
async def test_attach_second_item_preserves_first(env):
    """Non-écrasement : deux rattachements séquentiels (relecture après commit)
    sur deux items distincts cohabitent (verrou with_for_update — FR-021)."""
    from app.modules.applications.service import attach_checklist_document

    db, app, doc = env["db"], env["app"], env["doc"]
    doc2 = await _make_document(
        db, user=env["user"], account=env["account"], filename="esg.pdf"
    )
    await db.commit()

    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()
    await attach_checklist_document(db, app, "esg_report", doc2.id)
    await db.commit()

    statuses = {it["key"]: it["status"] for it in app.checklist}
    assert statuses["company_registration"] == "provided"
    assert statuses["esg_report"] == "provided"


@pytest.mark.asyncio
async def test_attach_concurrent_sessions_no_lost_update(env):
    """FR-021 — Concurrence inter-sessions : un rattachement committé par une
    autre session entre le chargement et le verrou ne doit PAS être écrasé.

    Reproduit le last-write-wins que le verrou + ``populate_existing`` doivent
    éliminer : sans relecture effective sous verrou, ce test échoue (item1 perdu).
    """
    from tests.conftest import test_session_factory
    from app.modules.applications.service import attach_checklist_document

    db, app = env["db"], env["app"]  # session A — app chargé (checklist périmée)
    doc1 = await _make_document(db, user=env["user"], account=env["account"], filename="d1.pdf")
    doc2 = await _make_document(db, user=env["user"], account=env["account"], filename="d2.pdf")
    await db.commit()

    # Session B (indépendante) rattache item1 et COMMIT.
    async with test_session_factory() as db_b:
        app_b = await db_b.get(FundApplication, app.id)
        await attach_checklist_document(db_b, app_b, "company_registration", doc1.id)
        await db_b.commit()

    # Session A — instance encore « périmée » — rattache item2 : doit RELIRE
    # l'état committé (item1 provided) sous verrou et le préserver.
    await attach_checklist_document(db, app, "esg_report", doc2.id)
    await db.commit()

    statuses = {it["key"]: it["status"] for it in app.checklist}
    assert statuses["company_registration"] == "provided"  # non écrasé
    assert statuses["esg_report"] == "provided"


@pytest.mark.asyncio
async def test_attach_replace_keeps_progress(env):
    """Remplacement (provided → autre document) : document_id remplacé,
    progression inchangée (FR-007)."""
    from app.modules.applications.service import attach_checklist_document

    db, app, doc = env["db"], env["app"], env["doc"]
    doc2 = await _make_document(
        db, user=env["user"], account=env["account"], filename="rccm_v2.pdf"
    )
    await db.commit()

    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()
    result = await attach_checklist_document(db, app, "company_registration", doc2.id)
    await db.commit()

    assert result["item"]["document"]["original_filename"] == "rccm_v2.pdf"
    assert result["checklist_progress"] == {"provided": 1, "total": 2}


# --- Endpoints (codes HTTP du contrat) ---


@pytest.mark.asyncio
async def test_put_endpoint_nominal_200(env, auth_client):
    db, app, doc = env["db"], env["app"], env["doc"]
    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.put(
            f"/api/applications/{app.id}/checklist/company_registration/document",
            json={"document_id": str(doc.id)},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["item"]["status"] == "provided"
    assert data["item"]["document"]["original_filename"] == "rccm_2026.pdf"
    assert data["checklist_progress"] == {"provided": 1, "total": 2}


@pytest.mark.asyncio
async def test_put_endpoint_cross_account_403(env, auth_client):
    db, app = env["db"], env["app"]
    other_account = await make_account(db, name="Tenant B")
    other_user = await make_pme_user(db, account=other_account)
    foreign_doc = await _make_document(db, user=other_user, account=other_account)
    await db.commit()

    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.put(
            f"/api/applications/{app.id}/checklist/company_registration/document",
            json={"document_id": str(foreign_doc.id)},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_put_endpoint_unknown_item_404(env, auth_client):
    app, doc = env["app"], env["doc"]
    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.put(
            f"/api/applications/{app.id}/checklist/nope/document",
            json={"document_id": str(doc.id)},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_endpoint_unknown_application_404(env, auth_client):
    doc = env["doc"]
    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.put(
            f"/api/applications/{uuid.uuid4()}/checklist/company_registration/document",
            json={"document_id": str(doc.id)},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_endpoint_missing_document_id_422(env, auth_client):
    app = env["app"]
    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.put(
            f"/api/applications/{app.id}/checklist/company_registration/document",
            json={},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_detail_includes_progress_and_document(env, auth_client):
    """GET détail : checklist enrichie + checklist_progress."""
    db, app, doc = env["db"], env["app"], env["doc"]
    from app.modules.applications.service import attach_checklist_document

    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.get(f"/api/applications/{app.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checklist_progress"] == {"provided": 1, "total": 2}
    rccm = next(it for it in body["checklist"] if it["key"] == "company_registration")
    assert rccm["status"] == "provided"
    assert rccm["document"]["original_filename"] == "rccm_2026.pdf"


# ==========================================================================
# T021 — Détacher (DELETE)
# ==========================================================================


@pytest.mark.asyncio
async def test_detach_provided_to_missing(env):
    """provided → missing, document=null, progression décrémentée."""
    from app.modules.applications.service import (
        attach_checklist_document,
        detach_checklist_document,
    )

    db, app, doc = env["db"], env["app"], env["doc"]
    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()
    result = await detach_checklist_document(db, app, "company_registration")
    await db.commit()

    assert result["item"]["status"] == "missing"
    assert result["item"]["document"] is None
    assert result["checklist_progress"] == {"provided": 0, "total": 2}


@pytest.mark.asyncio
async def test_detach_idempotent_on_missing(env):
    """Détacher un item déjà missing → renvoie l'item inchangé (idempotent)."""
    from app.modules.applications.service import detach_checklist_document

    db, app = env["db"], env["app"]
    result = await detach_checklist_document(db, app, "esg_report")
    await db.commit()
    assert result["item"]["status"] == "missing"
    assert result["item"]["document"] is None


@pytest.mark.asyncio
async def test_detach_does_not_delete_document(env):
    """Le document détaché existe toujours et reste rattachable ailleurs (FR-011)."""
    from app.modules.applications.service import (
        attach_checklist_document,
        detach_checklist_document,
    )

    db, app, doc = env["db"], env["app"], env["doc"]
    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()
    await detach_checklist_document(db, app, "company_registration")
    await db.commit()

    still_there = await db.get(Document, doc.id)
    assert still_there is not None
    # Rattachable sur un autre item après détachement.
    result = await attach_checklist_document(db, app, "esg_report", doc.id)
    assert result["item"]["status"] == "provided"


@pytest.mark.asyncio
async def test_detach_unknown_item_raises(env):
    from app.modules.applications.service import (
        ApplicationItemNotFound,
        detach_checklist_document,
    )

    db, app = env["db"], env["app"]
    with pytest.raises(ApplicationItemNotFound):
        await detach_checklist_document(db, app, "nope")


@pytest.mark.asyncio
async def test_detach_creates_audit_row(env):
    from app.modules.applications.service import (
        attach_checklist_document,
        detach_checklist_document,
    )

    db, app, doc = env["db"], env["app"], env["doc"]
    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()
    before = (await _count_audit_checklist_rows(db)).scalar_one()
    with source_of_change_scope("manual"):
        await detach_checklist_document(db, app, "company_registration")
        await db.commit()
    after = (await _count_audit_checklist_rows(db)).scalar_one()
    assert after - before == 1


@pytest.mark.asyncio
async def test_delete_endpoint_nominal_200(env, auth_client):
    db, app, doc = env["db"], env["app"], env["doc"]
    from app.modules.applications.service import attach_checklist_document

    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.delete(
            f"/api/applications/{app.id}/checklist/company_registration/document"
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["item"]["status"] == "missing"
    assert data["checklist_progress"] == {"provided": 0, "total": 2}


# ==========================================================================
# T027 — Progression dans la LISTE des dossiers
# ==========================================================================


@pytest.mark.asyncio
async def test_list_includes_checklist_progress(env, auth_client):
    """GET /api/applications/ : chaque dossier porte checklist_progress exact."""
    db, app, doc = env["db"], env["app"], env["doc"]
    from app.modules.applications.service import attach_checklist_document

    await attach_checklist_document(db, app, "company_registration", doc.id)
    await db.commit()

    async with auth_client(env["user"], env["account"]) as ac:
        resp = await ac.get("/api/applications/")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["checklist_progress"] == {"provided": 1, "total": 2}
