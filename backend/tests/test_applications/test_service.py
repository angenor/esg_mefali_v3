"""Tests unitaires du service dossiers de candidature."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.application import (
    ApplicationStatus,
    FundApplication,
    TargetType,
    VALID_TRANSITIONS,
)


# --- Helpers ---


def _make_fund(name: str = "FNDE", org: str = "Etat") -> MagicMock:
    fund = MagicMock()
    fund.id = uuid.uuid4()
    fund.name = name
    fund.organization = org
    fund.description = "Fonds national"
    fund.sectors_eligible = ["agriculture", "energie"]
    return fund


def _make_intermediary(
    name: str = "SIB",
    intermediary_type: str = "partner_bank",
) -> MagicMock:
    inter = MagicMock()
    inter.id = uuid.uuid4()
    inter.name = name
    inter.intermediary_type = MagicMock(value=intermediary_type)
    inter.intermediary_type.__eq__ = lambda self, other: self.value == (other.value if hasattr(other, 'value') else other)
    inter.intermediary_type.__hash__ = lambda self: hash(self.value)
    inter.contact_email = "contact@sib.ci"
    inter.contact_phone = "+225 27 20 30 40 50"
    inter.physical_address = "Abidjan, Plateau"
    return inter


def _make_application(
    target_type: str = "fund_direct",
    status: str = "draft",
    sections: dict | None = None,
) -> FundApplication:
    app = MagicMock(spec=FundApplication)
    app.id = uuid.uuid4()
    app.user_id = uuid.uuid4()
    app.fund_id = uuid.uuid4()
    app.match_id = None
    app.intermediary_id = None
    app.target_type = MagicMock(value=target_type)
    app.status = MagicMock(value=status)
    app.sections = sections or {
        "company_presentation": {
            "title": "Présentation de l'entreprise",
            "content": None,
            "status": "not_generated",
            "updated_at": None,
        },
    }
    app.checklist = []
    app.intermediary_prep = None
    app.simulation = None
    app.created_at = datetime.now(timezone.utc)
    app.updated_at = datetime.now(timezone.utc)
    app.submitted_at = None
    app.fund = _make_fund()
    app.intermediary = None
    return app


# --- Tests determine_target_type ---


@pytest.mark.asyncio
async def test_determine_target_type_no_intermediary():
    """Sans intermediaire → fund_direct."""
    from app.modules.applications.service import determine_target_type

    db = AsyncMock()
    result = await determine_target_type(db, None)
    assert result == TargetType.fund_direct


@pytest.mark.asyncio
async def test_determine_target_type_bank():
    """Intermediaire partner_bank → intermediary_bank."""
    from app.modules.applications.service import determine_target_type

    inter = _make_intermediary("SIB", "partner_bank")
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = inter
    db.execute.return_value = mock_result

    result = await determine_target_type(db, inter.id)
    assert result == TargetType.intermediary_bank


# --- Tests create_application ---


@pytest.mark.asyncio
async def test_create_application_fund_direct():
    """Creer un dossier fund_direct."""
    from app.modules.applications.service import create_application

    fund = _make_fund()
    db = AsyncMock()

    # Mock la requete de verification du fonds
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fund
    db.execute.return_value = mock_result

    # Patch determine_target_type pour eviter la requete reelle
    with patch(
        "app.modules.applications.service.determine_target_type",
        new_callable=AsyncMock,
        return_value=TargetType.fund_direct,
    ):
        application = await create_application(
            db, user_id=uuid.uuid4(), fund_id=fund.id,
        )

    assert application is not None
    db.add.assert_called_once()
    db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_create_application_fund_not_found():
    """Fonds non trouve → ValueError."""
    from app.modules.applications.service import create_application

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="Fonds non trouve"):
        await create_application(db, user_id=uuid.uuid4(), fund_id=uuid.uuid4())


# --- Tests update_application_status ---


@pytest.mark.asyncio
async def test_update_status_valid_transition():
    """Transition draft → preparing_documents OK."""
    from app.modules.applications.service import update_application_status

    app = _make_application(status="draft")
    db = AsyncMock()

    result = await update_application_status(db, app, "preparing_documents")
    assert result.status == "preparing_documents"


@pytest.mark.asyncio
async def test_update_status_invalid_transition():
    """Transition draft → accepted KO."""
    from app.modules.applications.service import update_application_status

    app = _make_application(status="draft")
    db = AsyncMock()

    with pytest.raises(ValueError, match="Transition invalide"):
        await update_application_status(db, app, "accepted")


@pytest.mark.asyncio
async def test_update_status_submitted_sets_date():
    """Soumission marque la date submitted_at."""
    from app.modules.applications.service import update_application_status

    app = _make_application(status="ready_for_fund")
    db = AsyncMock()

    result = await update_application_status(db, app, "submitted_to_fund")
    assert result.submitted_at is not None


# --- Tests update_section ---


@pytest.mark.asyncio
async def test_update_section_content():
    """Mettre a jour le contenu d'une section."""
    from app.modules.applications.service import update_section

    app = _make_application()
    db = AsyncMock()

    result = await update_section(
        db, app, "company_presentation",
        content="<p>Contenu mis a jour</p>",
        status="validated",
    )
    assert result["section_key"] == "company_presentation"
    assert result["content"] == "<p>Contenu mis a jour</p>"
    assert result["status"] == "validated"


@pytest.mark.asyncio
async def test_update_section_not_found():
    """Section inexistante → ValueError."""
    from app.modules.applications.service import update_section

    app = _make_application()
    db = AsyncMock()

    with pytest.raises(ValueError, match="Section.*non trouvee"):
        await update_section(db, app, "inexistante", content="test")


# --- Tests get_checklist ---


@pytest.mark.asyncio
async def test_get_checklist():
    """Recuperer la checklist d'un dossier."""
    from app.modules.applications.service import get_checklist

    app = _make_application()
    app.checklist = [{"key": "rccm", "name": "RCCM", "status": "missing"}]
    db = AsyncMock()

    result = await get_checklist(db, app)
    assert len(result) == 1
    assert result[0]["key"] == "rccm"


# --- Tests transitions matrice ---


def test_valid_transitions_completeness():
    """Verifier que tous les statuts ont des transitions definies."""
    for status in ApplicationStatus:
        assert status.value in VALID_TRANSITIONS, f"Statut {status.value} manquant"


def test_terminal_states_have_no_transitions():
    """Les etats terminaux n'ont pas de transitions sortantes."""
    assert VALID_TRANSITIONS["accepted"] == []
    assert VALID_TRANSITIONS["rejected"] == []


# --- Tests US8: Transitions de statut exhaustives (T051) ---


class TestStatusTransitions:
    """Tests exhaustifs de la machine a etats de statut."""

    @pytest.mark.asyncio
    async def test_direct_path_full(self) -> None:
        """Parcours direct complet : draft → ... → accepted."""
        from app.modules.applications.service import update_application_status

        direct_path = [
            "preparing_documents",
            "in_progress",
            "review",
            "ready_for_fund",
            "submitted_to_fund",
            "under_review",
            "accepted",
        ]
        app = _make_application(status="draft")
        db = AsyncMock()

        for next_status in direct_path:
            result = await update_application_status(db, app, next_status)
            current = result.status.value if hasattr(result.status, "value") else result.status
            assert current == next_status

    @pytest.mark.asyncio
    async def test_intermediary_path_full(self) -> None:
        """Parcours intermediaire complet : draft → ... → accepted."""
        from app.modules.applications.service import update_application_status

        intermediary_path = [
            "preparing_documents",
            "in_progress",
            "review",
            "ready_for_intermediary",
            "submitted_to_intermediary",
            "submitted_to_fund",
            "under_review",
            "accepted",
        ]
        app = _make_application(status="draft", target_type="intermediary_bank")
        db = AsyncMock()

        for next_status in intermediary_path:
            result = await update_application_status(db, app, next_status)
            current = result.status.value if hasattr(result.status, "value") else result.status
            assert current == next_status

    @pytest.mark.asyncio
    async def test_review_can_go_back_to_in_progress(self) -> None:
        """Depuis review, on peut revenir a in_progress."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="review")
        db = AsyncMock()
        result = await update_application_status(db, app, "in_progress")
        current = result.status.value if hasattr(result.status, "value") else result.status
        assert current == "in_progress"

    @pytest.mark.asyncio
    async def test_ready_for_intermediary_can_go_back_to_review(self) -> None:
        """Depuis ready_for_intermediary, on peut revenir a review."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="ready_for_intermediary")
        db = AsyncMock()
        result = await update_application_status(db, app, "review")
        current = result.status.value if hasattr(result.status, "value") else result.status
        assert current == "review"

    @pytest.mark.asyncio
    async def test_rejected_path(self) -> None:
        """Le parcours peut aboutir a un rejet."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="under_review")
        db = AsyncMock()
        result = await update_application_status(db, app, "rejected")
        current = result.status.value if hasattr(result.status, "value") else result.status
        assert current == "rejected"

    @pytest.mark.asyncio
    async def test_invalid_skip_transition(self) -> None:
        """On ne peut pas sauter une etape (draft → review)."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="draft")
        db = AsyncMock()
        with pytest.raises(ValueError, match="Transition invalide"):
            await update_application_status(db, app, "review")

    @pytest.mark.asyncio
    async def test_invalid_backward_transition(self) -> None:
        """On ne peut pas revenir en arriere arbitrairement (accepted → draft)."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="accepted")
        db = AsyncMock()
        with pytest.raises(ValueError, match="Transition invalide"):
            await update_application_status(db, app, "draft")

    @pytest.mark.asyncio
    async def test_submitted_sets_submitted_at(self) -> None:
        """La soumission met a jour submitted_at."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="ready_for_fund")
        app.submitted_at = None
        db = AsyncMock()
        result = await update_application_status(db, app, "submitted_to_fund")
        assert result.submitted_at is not None

    @pytest.mark.asyncio
    async def test_error_message_shows_allowed_transitions(self) -> None:
        """Le message d'erreur indique les transitions autorisees."""
        from app.modules.applications.service import update_application_status

        app = _make_application(status="draft")
        db = AsyncMock()
        with pytest.raises(ValueError, match="preparing_documents"):
            await update_application_status(db, app, "accepted")


# --- Tests generate_section (US1) ---


@pytest.mark.asyncio
async def test_generate_section_fund_direct():
    """Generer une section pour un dossier fund_direct via LLM."""
    from app.modules.applications.service import generate_section

    app = _make_application(target_type="fund_direct")
    db = AsyncMock()

    # Mock LLM response
    mock_response = MagicMock()
    mock_response.content = "<p>Contenu genere par le LLM</p>"

    # F15 BUG-001 : on patche get_or_create_profile pour fournir un profil
    # mock à la nouvelle injection company_context.
    mock_profile = MagicMock(
        company_name="Test Co", country="Sénégal", city=None,
        employee_count=10, year_founded=2020, annual_revenue_xof=50_000_000,
        annual_revenue_money=None,
    )
    mock_profile.sector = MagicMock(value="agriculture")

    with (
        patch("app.graph.nodes.get_llm") as mock_get_llm,
        patch(
            "app.graph.nodes._fetch_rag_context_for_financing",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch(
            "app.modules.company.service.get_or_create_profile",
            new_callable=AsyncMock,
            return_value=mock_profile,
        ),
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await generate_section(db, app, "company_presentation")

    assert result["section_key"] == "company_presentation"
    assert result["content"] == "<p>Contenu genere par le LLM</p>"
    assert result["status"] == "generated"


@pytest.mark.asyncio
async def test_generate_section_invalid_key():
    """Section inexistante → ValueError."""
    from app.modules.applications.service import generate_section

    app = _make_application(target_type="fund_direct")
    db = AsyncMock()

    with pytest.raises(ValueError, match="Section.*non trouvee"):
        await generate_section(db, app, "section_inexistante")


# --- Tests build_section_prompt ---


def test_build_section_prompt_includes_target_type():
    """Le prompt inclut le target_type."""
    from app.modules.applications.service import build_section_prompt

    prompt = build_section_prompt(
        target_type="intermediary_bank",
        section_key="company_banking_history",
        section_config={
            "title": "Historique bancaire",
            "description": "Presentation bancaire",
            "tone": "Business case",
        },
        company_context="Entreprise ABC",
        fund_context="SUNREF",
    )
    assert "intermediary_bank" in prompt
    assert "Business case" in prompt
    assert "Historique bancaire" in prompt


# --- Tests US2: Generation section bancaire ---


@pytest.mark.asyncio
async def test_generate_section_intermediary_bank():
    """Generer une section avec ton bancaire."""
    from app.modules.applications.service import generate_section

    sections = {
        "company_banking_history": {
            "title": "Présentation de l'entreprise et historique bancaire",
            "content": None,
            "status": "not_generated",
            "updated_at": None,
        },
    }
    app = _make_application(target_type="intermediary_bank", sections=sections)
    db = AsyncMock()

    mock_response = MagicMock()
    mock_response.content = "<p>Historique bancaire genere</p>"

    mock_profile = MagicMock(
        company_name="Test Co", country="Sénégal", city=None,
        employee_count=10, year_founded=2020, annual_revenue_xof=50_000_000,
        annual_revenue_money=None,
    )
    mock_profile.sector = MagicMock(value="agriculture")

    with (
        patch("app.graph.nodes.get_llm") as mock_get_llm,
        patch(
            "app.graph.nodes._fetch_rag_context_for_financing",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch(
            "app.modules.company.service.get_or_create_profile",
            new_callable=AsyncMock,
            return_value=mock_profile,
        ),
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await generate_section(db, app, "company_banking_history")

    assert result["section_key"] == "company_banking_history"
    assert result["status"] == "generated"


def test_build_section_prompt_bank_tone():
    """Le prompt bancaire contient le vocabulaire business case."""
    from app.modules.applications.service import build_section_prompt
    from app.modules.applications.templates import get_template_for_target

    template = get_template_for_target("intermediary_bank")
    banking_section = next(s for s in template if s["key"] == "company_banking_history")

    prompt = build_section_prompt(
        target_type="intermediary_bank",
        section_key="company_banking_history",
        section_config=banking_section,
        company_context="Entreprise ABC, CA 500M FCFA",
        fund_context="SUNREF via AFD",
    )
    assert "intermediary_bank" in prompt
    assert "solvabilite" in prompt.lower() or "bancaire" in prompt.lower()


# --- Tests US2: Checklist adaptee ---


def test_get_checklist_bank_vs_direct():
    """Les checklists bancaire et directe sont differentes."""
    from app.modules.applications.templates import get_checklist_for_target

    bank_cl = get_checklist_for_target("intermediary_bank")
    direct_cl = get_checklist_for_target("fund_direct")

    # La checklist bancaire doit avoir plus d'elements (bilans, releves, etc.)
    assert len(bank_cl) > len(direct_cl)

    # La checklist bancaire doit contenir des elements financiers specifiques
    bank_keys = [item["key"] for item in bank_cl]
    assert "bank_statements" in bank_keys
    assert "tax_declarations" in bank_keys
    assert "collateral_docs" in bank_keys

    # La checklist directe ne contient pas ces elements
    direct_keys = [item["key"] for item in direct_cl]
    assert "bank_statements" not in direct_keys


def test_checklist_items_have_missing_status():
    """Les elements de checklist sont initialises a missing."""
    from app.modules.applications.templates import get_checklist_for_target

    checklist = get_checklist_for_target("intermediary_bank")
    for item in checklist:
        assert item["status"] == "missing"
        assert item["document_id"] is None


# --- Tests US2: determine_target_type ---


@pytest.mark.asyncio
async def test_determine_target_type_agency():
    """Intermediaire implementation_agency → intermediary_agency."""
    from app.modules.applications.service import determine_target_type

    inter = _make_intermediary("PNUD", "implementation_agency")
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = inter
    db.execute.return_value = mock_result

    result = await determine_target_type(db, inter.id)
    assert result == TargetType.intermediary_agency


@pytest.mark.asyncio
async def test_determine_target_type_developer():
    """Intermediaire project_developer → intermediary_developer."""
    from app.modules.applications.service import determine_target_type

    inter = _make_intermediary("Gold Standard", "project_developer")
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = inter
    db.execute.return_value = mock_result

    result = await determine_target_type(db, inter.id)
    assert result == TargetType.intermediary_developer
