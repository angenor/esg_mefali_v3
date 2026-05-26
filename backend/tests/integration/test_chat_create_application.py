"""T008 (F048 US1) — Création de dossier via le chat depuis /documents.

Vérifie que, lorsqu'un tour LLM est routé vers le nœud ``application`` avec
``current_page=/documents``, le tool ``create_fund_application`` est EXPOSÉ par
le sélecteur (régression du bug « outil indisponible ») ET exécutable (crée un
dossier réel lié à l'offre + au projet).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.graph.tool_selector import select_tools_for_node
from app.graph.tools.application_tools import APPLICATION_TOOLS, create_fund_application
from app.models.application import FundApplication


def test_selector_exposes_create_fund_application_from_documents_page() -> None:
    """Le sélecteur expose create_fund_application sur node=application + /documents."""
    selected, _ = select_tools_for_node(
        node_name="application",
        current_page="/documents",
        all_tools=APPLICATION_TOOLS,
    )
    assert "create_fund_application" in {t.name for t in selected}


@pytest.mark.asyncio
async def test_create_fund_application_tool_executes_from_documents(
    db_session, f048_pme_user, f048_offer, f048_project,
):
    """Le tool create_fund_application crée un dossier lié (offre + projet)."""
    config = {
        "configurable": {
            "db": db_session,
            "user_id": f048_pme_user.id,
            "account_id": f048_pme_user.account_id,
            "conversation_id": uuid.uuid4(),
            "current_page": "/documents",
        }
    }

    result = await create_fund_application.ainvoke(
        {
            "fund_id": str(f048_offer.fund_id),
            "offer_id": str(f048_offer.id),
            "project_id": str(f048_project.id),
        },
        config=config,
    )

    # Aucun message d'« outil indisponible » / d'erreur.
    assert "indisponible" not in result.lower()
    assert "cree" in result.lower() or "créé" in result.lower() or "succès" in result.lower()

    rows = (
        await db_session.execute(
            select(FundApplication).where(
                FundApplication.user_id == f048_pme_user.id,
                FundApplication.offer_id == f048_offer.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].project_id == f048_project.id
    assert rows[0].fund_id == f048_offer.fund_id
