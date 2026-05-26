"""T002 (F048) — Tests d'intégration du service partagé de création de dossier.

Réf. contracts/application-creation.md T1, T2.

Le service ``create_application`` doit :
- (a) dériver ``fund_id``/``intermediary_id`` depuis ``offer_id`` et lier ``project_id`` ;
- (b) dédoublonner un dossier ``draft`` pour ``(user_id, project_id, offer_id)`` ;
- (c) lever ``ValueError`` si ``offer_id`` est inexistant (→ 404 amont).
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.applications.service import create_application

pytestmark = pytest.mark.asyncio


async def test_create_with_offer_derives_fund_and_links_project(
    db_session, f048_pme_user, f048_offer, f048_project,
):
    """T1 — create(offer_id) dérive fund/intermediary et lie project_id."""
    application = await create_application(
        db_session,
        user_id=f048_pme_user.id,
        offer_id=f048_offer.id,
        project_id=f048_project.id,
        account_id=f048_pme_user.account_id,
    )

    assert application.offer_id == f048_offer.id
    assert application.fund_id == f048_offer.fund_id
    assert application.intermediary_id == f048_offer.intermediary_id
    assert application.project_id == f048_project.id
    status = (
        application.status.value
        if hasattr(application.status, "value")
        else application.status
    )
    assert status == "draft"


async def test_create_is_idempotent_dedup_draft(
    db_session, f048_pme_user, f048_offer, f048_project,
):
    """T2 — 2e appel même (user, project, offer) en draft → MÊME dossier."""
    first = await create_application(
        db_session,
        user_id=f048_pme_user.id,
        offer_id=f048_offer.id,
        project_id=f048_project.id,
        account_id=f048_pme_user.account_id,
    )
    second = await create_application(
        db_session,
        user_id=f048_pme_user.id,
        offer_id=f048_offer.id,
        project_id=f048_project.id,
        account_id=f048_pme_user.account_id,
    )

    assert first.id == second.id, "La dédup doit retourner le dossier draft existant"


async def test_create_with_unknown_offer_raises(
    db_session, f048_pme_user,
):
    """T — offer_id inexistant → ValueError (mappé 404 amont)."""
    with pytest.raises(ValueError):
        await create_application(
            db_session,
            user_id=f048_pme_user.id,
            offer_id=uuid.uuid4(),
            account_id=f048_pme_user.account_id,
        )
