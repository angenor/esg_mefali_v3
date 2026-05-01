"""Tests RED pour la detection d'intention ESG dans le router (spec fix-esg-scoring-node-routing).

Couvre 8 phrases d'intention ESG : verbes courants (lance, demarre, commence,
calcule, finalise, cree, evalue) et patterns existants. Le test « voir mon score
ESG » est explicitement attendu en CONSULTATION (False) — il documente la
frontiere entre _detect_esg_request (interactive → esg_scoring) et
_detect_esg_query (consultation → chat_node).

Tests router_node mockent _is_topic_continuation pour eviter le round-trip LLM.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from app.graph.nodes import (
    _WIDGET_ESG_CONSULTATION_PATTERN,
    _WIDGET_ESG_PROMPT_PATTERN,
    _detect_esg_request,
    router_node,
)
from app.graph.state import ConversationState


def _make_state(message: str) -> ConversationState:
    """Etat minimal sans module actif pour tester le routing initial."""
    return ConversationState(
        messages=[HumanMessage(content=message)],
        user_id=None,
        user_profile=None,
        context_memory=[],
        profile_updates=None,
        profiling_instructions=None,
        document_upload=None,
        document_analysis_summary=None,
        has_document=False,
        esg_assessment=None,
        _route_esg=False,
        carbon_data=None,
        _route_carbon=False,
        financing_data=None,
        _route_financing=False,
        application_data=None,
        _route_application=False,
        credit_data=None,
        _route_credit=False,
        action_plan_data=None,
        _route_action_plan=False,
        tool_call_count=0,
        active_module=None,
        active_module_data=None,
        current_page=None,
        guidance_stats=None,
        active_entities=None,
    )


# Phrases qui doivent declencher _detect_esg_request=True (intention d'evaluation)
ESG_INTENT_PHRASES_TRUE = [
    "lance mon évaluation ESG",
    "démarre mon scoring ESG",
    "commence mon évaluation",
    "calcule mes scores ESG",
    "finalise mon évaluation",
    "crée mon évaluation ESG",
    "évalue ma conformité ESG",
    # Patch H : phrase capturee SEULEMENT par les nouveaux verbes d'intention.
    # « lance ESG » (verbe + ESG sans nom intermediaire) ne matche aucun des
    # anciens patterns (qui exigent « évaluation ESG / scoring ESG / analyse
    # ESG / audit ESG / lancer ... évaluation ... ESG »). Seul le nouveau
    # `lanc\w*.{0,40}\besg\b` capture cette formulation directe.
    "lance ESG maintenant",
]

# Phrase de CONSULTATION : doit rester False sur _detect_esg_request
ESG_QUERY_PHRASES_FALSE = [
    "voir mon score ESG",
]


@pytest.mark.parametrize("phrase", ESG_INTENT_PHRASES_TRUE)
def test_detect_esg_request_true_for_intent_phrases(phrase: str) -> None:
    """Chaque phrase d'intention ESG doit etre detectee."""
    assert _detect_esg_request(phrase) is True, (
        f"_detect_esg_request a echoue sur la phrase d'intention : « {phrase} »"
    )


@pytest.mark.parametrize("phrase", ESG_QUERY_PHRASES_FALSE)
def test_detect_esg_request_false_for_query_phrases(phrase: str) -> None:
    """Les phrases de consultation (« voir mon score ESG ») ne doivent PAS router vers scoring."""
    # Justification : « voir mon score ESG » est une CONSULTATION (lecture seule)
    # qui doit etre traitee par chat_node via get_esg_assessment_chat, pas par
    # esg_scoring_node (qui demarre une nouvelle evaluation interactive).
    assert _detect_esg_request(phrase) is False, (
        f"_detect_esg_request devrait etre False pour la consultation : « {phrase} »"
    )


@pytest.mark.parametrize("phrase", ESG_INTENT_PHRASES_TRUE)
@pytest.mark.asyncio
async def test_router_node_routes_esg_for_intent_phrases(phrase: str) -> None:
    """router_node doit retourner _route_esg=True pour les intentions ESG."""
    state = _make_state(phrase)
    # Mock _is_topic_continuation au cas ou (active_module=None ici donc pas appele)
    with patch(
        "app.graph.nodes._is_topic_continuation",
        new=AsyncMock(return_value=True),
    ):
        result = await router_node(state)
    assert result.get("_route_esg") is True, (
        f"router_node n'a pas active _route_esg pour : « {phrase} » ; resultat={result}"
    )


# ─── Patch C : widgets creation vs consultation ────────────────────────


def test_widget_prompt_creation_intent_matches() -> None:
    """Un prompt widget de creation doit etre capture par le pattern ESG."""
    prompt = "Voulez-vous créer l'évaluation ESG maintenant ?"
    assert _WIDGET_ESG_PROMPT_PATTERN.search(prompt) is not None


def test_widget_prompt_consultation_filtered_out() -> None:
    """Un prompt de consultation (« avez-vous déjà créé … ») doit etre filtre.

    La regex de creation peut techniquement matcher « créé … évaluation ESG »,
    mais le pattern de consultation `_WIDGET_ESG_CONSULTATION_PATTERN` doit
    detecter la marque temporelle (« déjà » / « avez-vous ») pour exclure ce
    widget de l'anti-boucle.
    """
    prompt = "Avez-vous déjà créé une évaluation ESG précédemment ?"
    assert _WIDGET_ESG_CONSULTATION_PATTERN.search(prompt) is not None


# ─── Patch D : negation guard sur _detect_esg_request ─────────────────


def test_detect_esg_request_false_on_negation() -> None:
    """Une formulation negative (« ne lance PAS d'évaluation ESG ») ne doit
    PAS declencher la detection ESG positive."""
    assert _detect_esg_request("ne lance PAS d'évaluation ESG") is False


# ─── Spec fix-profile-and-routing-regression : priorité ESG après tour chat ──


@pytest.mark.asyncio
async def test_esg_priority_after_chat_turn() -> None:
    """Bug 2 : si active_module='chat' (séquelle d'un tour précédent) et que
    l'utilisateur envoie une intention ESG explicite, le router doit forcer
    le reset d'active_module et router vers esg_scoring (et non rester en chat
    via le classifieur de continuation LLM).
    """
    state = _make_state("lance mon évaluation ESG")
    state["active_module"] = "chat"  # type: ignore[typeddict-item]

    # Mock _is_topic_continuation : si on l'appelait avec "chat" comme module,
    # le LLM par défaut retournerait CONTINUER. La garde défensive doit empêcher
    # cet appel et forcer le routage ESG normal.
    mock_continuation = AsyncMock(return_value=True)
    with patch("app.graph.nodes._is_topic_continuation", new=mock_continuation):
        result = await router_node(state)

    assert result.get("_route_esg") is True, (
        "L'intention ESG explicite doit forcer _route_esg=True même si "
        f"active_module='chat' était présent ; resultat={result}"
    )
    assert result.get("active_module") is None, (
        "active_module doit être réinitialisé à None pour permettre "
        "esg_scoring_node de prendre la main"
    )
    # Patch review (acceptance auditor) : prouver que la garde court-circuite
    # bien le classifieur LLM de continuation, et pas seulement que le résultat
    # final converge par hasard.
    mock_continuation.assert_not_called()


@pytest.mark.asyncio
async def test_router_debug_logs(caplog: pytest.LogCaptureFixture) -> None:
    """AC4 : router_node émet un log DEBUG par tour avec les 6 champs requis :
    last_user_msg, is_esg_request, active_module, has_active_esg, _route_esg,
    is_continuation. Tronqué à 80 chars (RGPD).
    """
    state = _make_state("lance mon évaluation ESG")

    with caplog.at_level(logging.DEBUG, logger="app.graph.nodes"):
        with patch(
            "app.graph.nodes._is_topic_continuation",
            new=AsyncMock(return_value=True),
        ):
            await router_node(state)

    debug_records = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "router_node decision" in r.getMessage()
    ]
    assert debug_records, "Aucun log DEBUG router_node decision émis"
    msg = debug_records[-1].getMessage()
    for needle in (
        "last_user_msg=",
        "is_esg_request=",
        "active_module=",
        "has_active_esg=",
        "_route_esg=",
        "is_continuation=",
    ):
        assert needle in msg, f"Champ {needle!r} manquant dans le log DEBUG : {msg}"
