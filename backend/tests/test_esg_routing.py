"""Tests d'integration RED pour le fix routage chat → esg_scoring_node.

Couvre AC1-AC4 de la spec spec-fix-esg-scoring-node-routing.md :
- AC1 : transition vers esg_scoring sur intention explicite
- AC2 : creation effective d'un assessment via endpoint REST (smoke test
        — la creation par tool est testee dans test_esg_scoring_node.py)
- AC3 : continuation dans esg_scoring sur message court (« hypothèses prudentes »)
- AC4 : anti-boucle widget — un widget ESG `state=answered` doit forcer le
        routage vers esg_scoring meme sans keyword ESG dans le message.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import HumanMessage

from app.graph.nodes import router_node
from app.graph.state import ConversationState
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
)
from tests.conftest import make_unique_email, test_session_factory


def _make_state(
    message: str,
    *,
    active_module: str | None = None,
    conversation_id: str | None = None,
) -> ConversationState:
    """Construire un ConversationState minimal pour le router."""
    state: dict = {
        "messages": [HumanMessage(content=message)],
        "user_id": None,
        "user_profile": None,
        "context_memory": [],
        "profile_updates": None,
        "profiling_instructions": None,
        "document_upload": None,
        "document_analysis_summary": None,
        "has_document": False,
        "esg_assessment": None,
        "_route_esg": False,
        "carbon_data": None,
        "_route_carbon": False,
        "financing_data": None,
        "_route_financing": False,
        "application_data": None,
        "_route_application": False,
        "credit_data": None,
        "_route_credit": False,
        "action_plan_data": None,
        "_route_action_plan": False,
        "tool_call_count": 0,
        "active_module": active_module,
        "active_module_data": None,
        "current_page": None,
        "guidance_stats": None,
        "active_entities": None,
    }
    if conversation_id is not None:
        state["conversation_id"] = conversation_id  # type: ignore[typeddict-item]
    return state  # type: ignore[return-value]


# ─── AC1 — Transition module ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac1_intent_phrase_routes_to_esg_scoring() -> None:
    """AC1 : message d'intention ESG → _route_esg=True quand active_module=null."""
    state = _make_state("je veux faire mon évaluation ESG")
    with patch(
        "app.graph.nodes._is_topic_continuation",
        new=AsyncMock(return_value=True),
    ):
        result = await router_node(state)
    assert result.get("_route_esg") is True


# ─── AC2 — Creation effective d'un assessment ────────────────────────


async def _register_login(client: AsyncClient) -> str:
    data = {
        "email": make_unique_email(),
        "password": "motdepasse123",
        "full_name": "AC2 User",
        "company_name": "AC2 Co",
    }
    await client.post("/api/auth/register", json=data)
    resp = await client.post(
        "/api/auth/login",
        json={"email": data["email"], "password": data["password"]},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_ac2_create_assessment_via_rest_endpoint(client: AsyncClient) -> None:
    """AC2 : POST /api/esg/assessments cree bien une row draft avec sector du profil.

    Le scenario complet (clic widget « Oui, créer » → tool create_esg_assessment)
    est couvert par test_esg_scoring_node.py. Ici on valide le chemin REST
    qui sera declenche par le bouton « Nouvelle evaluation » de la page /esg.
    """
    token = await _register_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.patch(
        "/api/company/profile",
        headers=headers,
        json={"sector": "agriculture"},
    )

    response = await client.post("/api/esg/assessments", headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["sector"] == "agriculture"


# ─── AC3 — Continuation dans esg_scoring (smoke router) ──────────────


@pytest.mark.asyncio
async def test_ac3_router_keeps_esg_module_on_continuation() -> None:
    """AC3 : si active_module='esg_scoring', un message court (« hypothèses prudentes »)
    doit rester dans le module (continuation), pour que esg_scoring_node puisse
    invoquer batch_save_esg_criteria + finalize_esg_assessment.
    """
    state = _make_state(
        "hypothèses prudentes",
        active_module="esg_scoring",
    )
    with patch(
        "app.graph.nodes._is_topic_continuation",
        new=AsyncMock(return_value=True),
    ):
        result = await router_node(state)
    assert result.get("_route_esg") is True
    assert result.get("active_module") == "esg_scoring"


# ─── AC4 — Anti-boucle widget ────────────────────────────────────────


async def _seed_answered_esg_widget(conversation_id: uuid.UUID) -> None:
    """Inserer un widget ESG `state=answered` sur la conversation."""
    async with test_session_factory() as db:
        q = InteractiveQuestion(
            conversation_id=conversation_id,
            module="chat",
            question_type="qcu",
            prompt="Voulez-vous créer l'évaluation ESG maintenant ?",
            options=[
                {"id": "yes", "label": "Oui, créer l'évaluation"},
                {"id": "no", "label": "Non, plus tard"},
            ],
            min_selections=1,
            max_selections=1,
            requires_justification=False,
            state=InteractiveQuestionState.ANSWERED.value,
            response_values=["yes"],
        )
        db.add(q)
        await db.commit()


@pytest.mark.asyncio
async def test_ac4_answered_esg_widget_forces_routing(client: AsyncClient) -> None:
    """AC4 : si un widget ESG `answered` existe et active_module=null/chat,
    le router doit forcer _route_esg=True meme si le message ne contient
    aucun keyword ESG (anti-boucle widget de confirmation).
    """
    token = await _register_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    conv_resp = await client.post(
        "/api/chat/conversations",
        json={"title": "AC4"},
        headers=headers,
    )
    conv_id = conv_resp.json()["id"]
    await _seed_answered_esg_widget(uuid.UUID(conv_id))

    state = _make_state("ok", conversation_id=conv_id)

    with (
        patch(
            "app.graph.nodes._is_topic_continuation",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.core.database.async_session_factory",
            test_session_factory,
        ),
    ):
        result = await router_node(state)

    assert result.get("_route_esg") is True, (
        "Le widget ESG repondu doit forcer le routage vers esg_scoring"
    )
