"""F13 — Tests d'intégration POST /api/reports/esg/{id}/generate multi-réf (T048)."""

from __future__ import annotations

import uuid

import pytest

from app.api.deps import get_current_user
from app.main import app
from app.models.account import Account
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.user import User


def _weasyprint_available() -> bool:
    """Vérifie que WeasyPrint et ses libs natives sont chargeables."""
    try:
        import weasyprint  # noqa: F401
        return True
    except (ImportError, OSError):
        return False


_HAS_WEASY = _weasyprint_available()


pytestmark = pytest.mark.asyncio


async def _make_user_with_assessment(db_session) -> tuple[User, ESGAssessment]:
    account = Account(name=f"AC-{uuid.uuid4().hex[:6]}")
    db_session.add(account)
    await db_session.flush()
    user = User(
        email=f"u-{uuid.uuid4().hex[:6]}@t.com",
        hashed_password="x",
        full_name="T",
        company_name="T",
        account_id=account.id,
    )
    db_session.add(user)
    await db_session.flush()
    a = ESGAssessment(
        user_id=user.id,
        account_id=account.id,
        sector="agriculture",
        status=ESGStatusEnum.completed,
        overall_score=70.0,
        environment_score=70.0,
        social_score=70.0,
        governance_score=70.0,
        assessment_data={
            "criteria_scores": {
                f"{p}{i}": {"score": 7, "justification": "ok"}
                for p in ("E", "S", "G")
                for i in range(1, 11)
            }
        },
    )
    db_session.add(a)
    await db_session.commit()
    return user, a


@pytest.mark.skipif(
    not _HAS_WEASY,
    reason="WeasyPrint native libs non disponibles sur cette plateforme.",
)
async def test_generate_report_default_body_succeeds(client, db_session):
    """T048 (b) — sans body : default referentials=['mefali'] (rétrocompat F06)."""
    user, assessment = await _make_user_with_assessment(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(f"/api/reports/esg/{assessment.id}/generate")
        # 201 (rétrocompatibilité F06)
        assert resp.status_code in (201, 200), f"Got {resp.status_code}: {resp.text}"
    finally:
        del app.dependency_overrides[get_current_user]


@pytest.mark.skipif(
    not _HAS_WEASY,
    reason="WeasyPrint native libs non disponibles sur cette plateforme.",
)
async def test_generate_report_with_multi_referentials(client, db_session):
    """T048 (a) — body multi-référentiels accepté."""
    user, assessment = await _make_user_with_assessment(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/reports/esg/{assessment.id}/generate",
            json={"referentials": ["mefali", "ifc_ps"], "include_appendix_sources": True},
        )
        # On vérifie au moins que ça ne renvoie pas 422 si codes valides
        assert resp.status_code != 422, f"Got 422: {resp.text}"
    finally:
        del app.dependency_overrides[get_current_user]


async def test_generate_report_invalid_referential_returns_422(client, db_session):
    """T048 (c) — code de référentiel invalide → 422 avec liste valide."""
    user, assessment = await _make_user_with_assessment(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/reports/esg/{assessment.id}/generate",
            json={"referentials": ["xyz_invalid"], "include_appendix_sources": False},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "valid_codes" in body.get("detail", {}) or "valid_codes" in str(body)
    finally:
        del app.dependency_overrides[get_current_user]


async def test_generate_report_extra_field_rejected(client, db_session):
    """Body avec champ inconnu → 422 (extra=forbid sur GenerateReportRequest)."""
    user, assessment = await _make_user_with_assessment(db_session)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = await client.post(
            f"/api/reports/esg/{assessment.id}/generate",
            json={"referentials": ["mefali"], "unknown_field": "x"},
        )
        assert resp.status_code == 422
    finally:
        del app.dependency_overrides[get_current_user]
