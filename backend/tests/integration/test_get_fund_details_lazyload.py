"""Régression — `get_fund_details` ne doit plus lever MissingGreenlet.

Bug constaté en live (parcours F048) : `get_fund_details` traversait les
relations lazy `fund.fund_intermediaries` puis `fi.intermediary` sur une
session async → ``sqlalchemy.exc.MissingGreenlet``. Le fonds GCF (qui a des
intermédiaires liés, ex. BOAD) faisait systématiquement échouer la consultation.

Correctif : requête explicite (jointure FundIntermediary↔Intermediary) au lieu
du lazy-load. Ce test charge un vrai fonds + intermédiaire + liaison et vérifie
que le tool retourne le nom de l'intermédiaire sans erreur.
"""

from __future__ import annotations

import uuid

import pytest

from app.graph.tools.financing_tools import get_fund_details

pytestmark = pytest.mark.asyncio


async def test_get_fund_details_lists_intermediaries_without_greenlet_error(
    db_session, f048_pme_user, f048_fund, f048_intermediary, f048_fund_intermediary,
):
    """Le fonds a un intermédiaire lié (BOAD) → consultation OK, nom présent."""
    config = {
        "configurable": {
            "db": db_session,
            "user_id": f048_pme_user.id,
            "account_id": f048_pme_user.account_id,
            "conversation_id": uuid.uuid4(),
        }
    }

    result = await get_fund_details.ainvoke(
        {"fund_id": str(f048_fund.id)}, config=config,
    )

    # Pas d'erreur lazy-load remontée au LLM.
    assert "MissingGreenlet" not in result
    assert "Erreur lors de la consultation" not in result
    # L'intermédiaire lié (BOAD) doit apparaître dans la fiche.
    assert "BOAD" in result
    assert f048_fund.name in result
