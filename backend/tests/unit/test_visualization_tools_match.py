"""F11 — Tests unitaires pour show_match_card tool.

TDD strict : tests AVANT implémentation.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError


def _extract_json_payload(result: str) -> dict:
    sse_marker = "<!--SSE:"
    if sse_marker in result:
        result = result.split(sse_marker, 1)[0]
    return json.loads(result)


def _valid_match_payload(**overrides):
    base = {
        "project_id": str(uuid.uuid4()),
        "offer_id": str(uuid.uuid4()),
        "fund_name": "Green Climate Fund",
        "intermediary_name": "BOAD",
        "compatibility_score": 78,
        "amount_range": "1-5 M FCFA",
        "timeline": "12-18 mois",
        "instruments": ["subvention", "blending"],
        "missing_criteria_count": 2,
        "drilldown_url": "/financing/offers/abc?project_id=xyz",
    }
    base.update(overrides)
    return base


def _make_config(account_id: uuid.UUID | None = None) -> dict:
    """RunnableConfig factice avec db / user / account."""
    db = AsyncMock()
    db.execute = AsyncMock()
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    return {
        "configurable": {
            "db": db,
            "user_id": user_id,
            "account_id": str(account_id) if account_id else str(uuid.uuid4()),
        },
    }


def test_tool_registered() -> None:
    from app.graph.tools.visualization_tools import (
        VISUALIZATION_TOOLS,
        show_match_card,
    )
    assert show_match_card.name == "show_match_card"
    assert show_match_card in VISUALIZATION_TOOLS


@pytest.mark.asyncio
async def test_invocation_valid() -> None:
    """Invocation valide retourne un JSON contenant project_id et offer_id."""
    from app.graph.tools.visualization_tools import show_match_card

    payload = _valid_match_payload()
    result = await show_match_card.ainvoke(payload)
    parsed = _extract_json_payload(result)
    assert parsed["fund_name"] == "Green Climate Fund"
    assert parsed["compatibility_score"] == 78
    assert parsed["project_id"] == payload["project_id"]
    assert parsed["offer_id"] == payload["offer_id"]


@pytest.mark.asyncio
async def test_invocation_invalid_score() -> None:
    """compatibility_score > 100 rejeté."""
    from app.graph.tools.visualization_tools import show_match_card

    with pytest.raises((ValidationError, ValueError)):
        await show_match_card.ainvoke(_valid_match_payload(compatibility_score=150))


@pytest.mark.asyncio
async def test_invocation_missing_required_field() -> None:
    from app.graph.tools.visualization_tools import show_match_card

    payload = _valid_match_payload()
    del payload["fund_name"]
    with pytest.raises((ValidationError, ValueError)):
        await show_match_card.ainvoke(payload)


@pytest.mark.asyncio
async def test_invocation_invalid_uuid() -> None:
    """project_id non-UUID rejeté."""
    from app.graph.tools.visualization_tools import show_match_card

    with pytest.raises((ValidationError, ValueError)):
        await show_match_card.ainvoke(_valid_match_payload(project_id="not-a-uuid"))


def test_args_schema() -> None:
    from app.graph.tools.visualization_tools import show_match_card
    from app.schemas.visualization import MatchCardArgs
    assert show_match_card.args_schema is MatchCardArgs


def test_docstring_use_when() -> None:
    from app.graph.tools.visualization_tools import show_match_card
    doc = show_match_card.description.lower()
    assert "use when" in doc or "utilise quand" in doc or "utiliser quand" in doc
