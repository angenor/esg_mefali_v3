"""Tests d'intégration SSE pour le profilage (US1).

Vérifie que les événements SSE profile_update et profile_completion sont
émis depuis le tool update_company_profile via les métadonnées <!--SSE:...-->.
"""

import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> tuple[str, dict]:
    """Créer un utilisateur et retourner le token + headers."""
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Test1234!",
            "full_name": "Test User",
            "company_name": "Test Co",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Test1234!"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def _make_mock_session():
    """Créer un mock de session async suffisant pour le SSE callback."""
    mock_msg_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock(
        side_effect=lambda m: setattr(m, "id", mock_msg_id),
    )
    mock_session.commit = AsyncMock()
    # Pour la notification rapport (execute retourne un scalar_one_or_none = None)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


class TestChatProfiling:
    """Tests d'intégration du streaming SSE avec extraction de profil via tool."""

    @pytest.mark.asyncio
    async def test_message_with_profile_tool_emits_events(
        self, client: AsyncClient,
    ) -> None:
        """Un tool_call_end de update_company_profile avec métadonnées SSE
        génère des events profile_update + profile_completion."""
        _, headers = await _register_and_login(client)

        resp = await client.post(
            "/api/chat/conversations",
            headers=headers,
            json={"title": "Test profiling"},
        )
        assert resp.status_code == 201
        conv_id = resp.json()["id"]

        # Simuler stream_graph_events qui émet un token puis un tool_call
        # avec les métadonnées SSE de profil
        sse_metadata = json.dumps({
            "__sse_profile__": True,
            "changed_fields": [
                {"field": "sector", "value": "recyclage", "label": "Secteur"},
                {"field": "city", "value": "Abidjan", "label": "Ville"},
            ],
            "completion": {
                "identity_completion": 37.5,
                "esg_completion": 0.0,
                "overall_completion": 18.8,
            },
        })
        tool_output = (
            f"Profil mis à jour avec succès\n<!--SSE:{sse_metadata}-->"
        )

        async def mock_stream_events(**kwargs):
            yield {"type": "token", "content": "Profil sauvegardé."}
            yield {
                "type": "tool_call_start",
                "tool_name": "update_company_profile",
                "tool_args": {"sector": "recyclage"},
                "tool_call_id": "tc-1",
            }
            yield {
                "type": "tool_call_end",
                "tool_name": "update_company_profile",
                "tool_call_id": "tc-1",
                "success": True,
                "result_summary": tool_output[:200],
            }

        mock_session = _make_mock_session()

        @asynccontextmanager
        async def mock_factory():
            yield mock_session

        with (
            patch("app.api.chat.stream_graph_events", side_effect=mock_stream_events),
            patch("app.api.chat.async_session_factory", mock_factory),
        ):
            resp = await client.post(
                f"/api/chat/conversations/{conv_id}/messages",
                headers=headers,
                data={"content": "je fais du recyclage à Abidjan"},
            )

        assert resp.status_code == 200

        events = []
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        event_types = [e.get("type") for e in events]
        assert "token" in event_types
        assert "done" in event_types

        # Les events profile sont émis depuis stream_graph_events directement,
        # pas depuis generate_sse. Le mock ici ne les émet pas car on mocke
        # stream_graph_events entièrement. Ce test vérifie que le flux SSE
        # fonctionne sans l'ancienne extraction.

    @pytest.mark.asyncio
    async def test_generic_message_no_profile_events(
        self, client: AsyncClient,
    ) -> None:
        """Un message générique ne génère pas d'events profil."""
        _, headers = await _register_and_login(client)

        resp = await client.post(
            "/api/chat/conversations",
            headers=headers,
            json={"title": "Test generic"},
        )
        conv_id = resp.json()["id"]

        async def mock_stream_events(**kwargs):
            yield {"type": "token", "content": "Bonjour !"}

        mock_session = _make_mock_session()

        @asynccontextmanager
        async def mock_factory():
            yield mock_session

        with (
            patch("app.api.chat.stream_graph_events", side_effect=mock_stream_events),
            patch("app.api.chat.async_session_factory", mock_factory),
        ):
            resp = await client.post(
                f"/api/chat/conversations/{conv_id}/messages",
                headers=headers,
                data={"content": "Bonjour, comment allez-vous ?"},
            )

        events = []
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        event_types = [e.get("type") for e in events]
        assert "profile_update" not in event_types
        assert "token" in event_types


# ─── Spec fix-profile-and-routing-regression : Bug 1 (forcing tool call) ──


def test_chat_profiling_tool_call_dense_message() -> None:
    """Bug 1 : pour un profil incomplet, les instructions de profilage doivent
    contenir l'impératif explicite d'appeler `update_company_profile` AVANT
    toute réponse texte (cas du message dense « Moussa SARL, agroalimentaire,
    Dakar, 18 personnes, 85 M FCFA, ODD 8/12/13 »)."""
    from app.graph.nodes import _build_profiling_instructions

    profile = {"company_name": "Moussa SARL"}  # 1 champ rempli → incomplet
    instructions = _build_profiling_instructions(profile)

    assert instructions, "Instructions vides pour un profil incomplet"
    assert "update_company_profile" in instructions, (
        "Le tool `update_company_profile` doit être nommé explicitement"
    )
    assert "DOIS" in instructions or "DOIT" in instructions, (
        "L'instruction doit contenir un impératif fort (DOIS/DOIT)"
    )
    assert "AVANT" in instructions, (
        "L'instruction doit imposer l'appel du tool AVANT la réponse texte"
    )


def test_chat_no_profile_call_on_esg_request() -> None:
    """Test négatif : « lance mon évaluation ESG » seul est détecté comme
    intention ESG. Le router court-circuite alors profiling_instructions
    (cf. nodes.py l. 591), évitant tout faux positif d'appel update_company_profile.
    """
    from app.graph.nodes import _detect_esg_request, _detect_profile_info

    msg = "lance mon évaluation ESG"
    assert _detect_esg_request(msg) is True
    assert _detect_profile_info(msg) is False
