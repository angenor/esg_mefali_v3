"""T007 (F048 US1) — Gating ESG avant génération du dossier (D4).

Réf. contracts/application-creation.md T7/T8.

Le référentiel applicable à l'offre est résolu via
``multi_referential_service.resolve_offer_referential_id`` (mocké ici — pas de
FK offre→référentiel, cf. research D4/U1). Le gating compare les critères
``is_required`` de ce référentiel à la couverture de l'évaluation ESG-projet :

- critères requis manquants → ``{ok:false, blocked:true, ...}`` (pas de génération) ;
- critères requis couverts → ``None`` (génération autorisée).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.account import Account
from app.models.indicator import Criterion
from app.models.project import Project
from app.models.referential import Referential
from app.models.source import Source
from app.models.user import User
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)

pytestmark = pytest.mark.asyncio

_GATING_PATH = "app.graph.tools.application_tools._check_esg_gating"
_RESOLVER_PATH = "app.modules.esg.multi_referential_service.resolve_offer_referential_id"


async def _seed(db_session, *, n_required: int = 2):
    """Crée account/user/source/referential + n_required critères + projet + assessment draft."""
    account = Account(name=f"acc-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()

    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@mefali.test",
        hashed_password="x", full_name="Admin", company_name="Mefali",
        role="ADMIN", account_id=None,
    )
    verifier = User(
        email=f"verif-{uuid.uuid4().hex[:6]}@mefali.test",
        hashed_password="x", full_name="Verifier", company_name="Mefali",
        role="ADMIN", account_id=None,
    )
    db_session.add_all([admin, verifier])
    await db_session.flush()

    # F01 — sourçage 4-yeux : captured_by != verified_by (CHECK).
    source = Source(
        url=f"https://example.test/{uuid.uuid4().hex[:6]}",
        title="Src", publisher="Pub", version="1.0", date_publi=date.today(),
        captured_by=admin.id, created_by_user_id=admin.id,
        verified_by=verifier.id, verified_at=datetime.now(timezone.utc),
        verification_status="verified",
    )
    db_session.add(source)
    await db_session.flush()

    referential = Referential(
        code=f"ref_{uuid.uuid4().hex[:6]}", label="Réf test",
        description="desc", source_id=source.id,
        publication_status="published", created_by_user_id=admin.id,
    )
    db_session.add(referential)
    await db_session.flush()

    criteria = []
    for i in range(n_required):
        crit = Criterion(
            code=f"C{i}-{uuid.uuid4().hex[:4]}", label=f"Critère {i}",
            expression={}, source_id=source.id,
            publication_status="published", created_by_user_id=admin.id,
            weight=Decimal("1.00"), is_required=True, applies_to_project=True,
            referential_id=referential.id,
        )
        db_session.add(crit)
        criteria.append(crit)
    await db_session.flush()

    project = Project(account_id=account.id, name="Projet", status="draft")
    db_session.add(project)
    await db_session.flush()

    assessment = ProjectEsgAssessment(
        account_id=account.id, project_id=project.id,
        referential_id=referential.id, referential_version="1.0",
        state="draft", created_by=admin.id,
    )
    db_session.add(assessment)
    await db_session.flush()

    return account, project, referential, criteria, assessment


async def _cover(db_session, assessment, account_id, criterion):
    db_session.add(ProjectEsgCriterionResponse(
        account_id=account_id, assessment_id=assessment.id,
        criterion_id=criterion.id, response_type="qcu",
        response_value={"choice": "oui"}, normalized_score=Decimal("1.000"),
        source_id=None, unsourced=True,
    ))
    await db_session.flush()


async def test_gating_blocks_when_required_criteria_missing(db_session):
    """T7 — critères requis non couverts → blocked:true, pas de génération."""
    from app.graph.tools.application_tools import _check_esg_gating

    account, project, referential, _criteria, _assessment = await _seed(db_session)

    with patch(_RESOLVER_PATH, new_callable=AsyncMock, return_value=referential.id):
        result = await _check_esg_gating(
            db_session,
            account_id=account.id,
            project_id=project.id,
            offer_id=uuid.uuid4(),
        )

    assert result is not None
    assert result.get("blocked") is True
    assert result.get("ok") is False
    assert result.get("missing_criteria"), "doit lister les critères manquants"


async def test_gating_allows_when_required_criteria_covered(db_session):
    """T8 — tous les critères requis couverts → None (génération autorisée)."""
    from app.graph.tools.application_tools import _check_esg_gating

    account, project, referential, criteria, assessment = await _seed(db_session)
    for crit in criteria:
        await _cover(db_session, assessment, account.id, crit)

    with patch(_RESOLVER_PATH, new_callable=AsyncMock, return_value=referential.id):
        result = await _check_esg_gating(
            db_session,
            account_id=account.id,
            project_id=project.id,
            offer_id=uuid.uuid4(),
        )

    assert result is None, f"attendu None (autorisé), reçu {result}"


async def test_gating_skipped_without_project_or_offer(db_session):
    """Sans project_id/offer_id, pas de gating possible → None (permissif)."""
    from app.graph.tools.application_tools import _check_esg_gating

    result = await _check_esg_gating(
        db_session, account_id=uuid.uuid4(), project_id=None, offer_id=None,
    )
    assert result is None


async def test_resolve_offer_referential_id_unknown_offer_returns_none(db_session):
    """Le résolveur retourne None si l'offre est introuvable."""
    from app.modules.esg.multi_referential_service import (
        resolve_offer_referential_id,
    )

    assert await resolve_offer_referential_id(db_session, offer_id=uuid.uuid4()) is None


async def test_resolve_offer_referential_id_falls_back_to_mefali(db_session):
    """Sans FK fonds→référentiel, le résolveur retombe sur Mefali (D4/U1)."""
    from datetime import date

    from app.core.constants import MEFALI_REFERENTIAL_CODE
    from app.models.financing import (
        AccessType, Fund, FundStatus, FundType, Intermediary,
        IntermediaryType, OrganizationType,
    )
    from app.models.offer import Offer
    from app.modules.esg.multi_referential_service import (
        resolve_offer_referential_id,
    )

    account, _project, _ref, _criteria, _assessment = await _seed(db_session)
    # Source verifiée déjà créée par _seed ? Non — on recrée admins+source.
    a1 = User(email=f"x1-{uuid.uuid4().hex[:6]}@m.test", hashed_password="x",
              full_name="A", company_name="M", role="ADMIN", account_id=None)
    a2 = User(email=f"x2-{uuid.uuid4().hex[:6]}@m.test", hashed_password="x",
              full_name="B", company_name="M", role="ADMIN", account_id=None)
    db_session.add_all([a1, a2])
    await db_session.flush()
    src = Source(
        url=f"https://ex.test/{uuid.uuid4().hex[:6]}", title="S", publisher="P",
        version="1.0", date_publi=date.today(), captured_by=a1.id,
        created_by_user_id=a1.id, verified_by=a2.id,
        verified_at=datetime.now(timezone.utc), verification_status="verified",
    )
    db_session.add(src)
    await db_session.flush()

    # Référentiel Mefali (fallback attendu).
    mefali = Referential(
        code=MEFALI_REFERENTIAL_CODE, label="Mefali", description="d",
        source_id=src.id, publication_status="published", created_by_user_id=a1.id,
    )
    db_session.add(mefali)
    await db_session.flush()

    fund = Fund(
        name="F", organization="O", fund_type=FundType.multilateral,
        description="d", eligibility_criteria={}, sectors_eligible=[],
        required_documents=[], esg_requirements={}, status=FundStatus.active,
        access_type=AccessType.intermediary_required, application_process=[],
        typical_timeline_months=12, source_id=src.id, publication_status="published",
    )
    inter = Intermediary(
        name="I", intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.development_bank, country="SN",
        city="Dakar", accreditations=[], services_offered={},
        eligibility_for_sme={}, required_documents=[], fees_structured={},
        is_active=True, source_id=src.id, publication_status="published",
        version="1.0", valid_from=date.today(),
    )
    db_session.add_all([fund, inter])
    await db_session.flush()
    offer = Offer(
        fund_id=fund.id, intermediary_id=inter.id, name="O", accepted_languages=["FR"],
        effective_criteria={}, effective_required_documents=[], effective_fees={},
        is_active=True, publication_status="published", source_id=src.id,
        version="1.0", valid_from=date.today(),
    )
    db_session.add(offer)
    await db_session.flush()

    resolved = await resolve_offer_referential_id(db_session, offer_id=offer.id)
    assert resolved == mefali.id
