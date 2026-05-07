"""F11 — Tests unitaires pour show_kpi_card tool.

TDD strict : tests écrits AVANT implémentation (T018 avant T021).
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError


def _extract_json_payload(result: str) -> dict:
    """Extraire le JSON principal en isolant le marker SSE éventuel."""
    sse_marker = "<!--SSE:"
    if sse_marker in result:
        result = result.split(sse_marker, 1)[0]
    return json.loads(result)


def test_tool_is_registered() -> None:
    """Le tool show_kpi_card est exporté et a le bon nom."""
    from app.graph.tools.visualization_tools import (
        VISUALIZATION_TOOLS,
        show_kpi_card,
    )

    assert show_kpi_card.name == "show_kpi_card"
    assert show_kpi_card in VISUALIZATION_TOOLS


@pytest.mark.asyncio
async def test_invocation_valid_returns_json_string() -> None:
    """Invocation valide retourne un JSON string contenant tous les champs."""
    from app.graph.tools.visualization_tools import show_kpi_card

    sid = str(uuid.uuid4())
    result = await show_kpi_card.ainvoke({
        "title": "Empreinte carbone 2026",
        "value": "45 tCO2e",
        "delta": -12.0,
        "delta_label": "vs 2024",
        "delta_direction": "down",
        "delta_is_good": True,
        "color": "emerald",
        "source_id": sid,
        "drilldown_url": "/carbon/results",
    })

    payload = _extract_json_payload(result)
    assert payload["title"] == "Empreinte carbone 2026"
    assert payload["value"] == "45 tCO2e"
    assert payload["delta"] == -12.0
    assert payload["color"] == "emerald"
    assert payload["source_id"] == sid


@pytest.mark.asyncio
async def test_invocation_minimal() -> None:
    """Champs minimaux requis (title + value)."""
    from app.graph.tools.visualization_tools import show_kpi_card

    result = await show_kpi_card.ainvoke({
        "title": "Score ESG",
        "value": "72/100",
    })

    payload = _extract_json_payload(result)
    assert payload["title"] == "Score ESG"
    assert payload["color"] == "emerald"  # défaut
    assert payload["delta"] is None


@pytest.mark.asyncio
async def test_invocation_invalid_payload_raises() -> None:
    """Payload invalide → ValidationError remontée par LangChain."""
    from app.graph.tools.visualization_tools import show_kpi_card

    # title vide rejeté par Pydantic (min_length=1)
    with pytest.raises((ValidationError, ValueError)):
        await show_kpi_card.ainvoke({
            "title": "",
            "value": "1",
        })


@pytest.mark.asyncio
async def test_invocation_extra_field_raises() -> None:
    """Champ inconnu rejeté (extra="forbid")."""
    from app.graph.tools.visualization_tools import show_kpi_card

    with pytest.raises((ValidationError, ValueError)):
        await show_kpi_card.ainvoke({
            "title": "X",
            "value": "1",
            "hallucinated": "boom",
        })


@pytest.mark.asyncio
async def test_invocation_with_money() -> None:
    """value_money sérialisé en {amount, currency}."""
    from app.graph.tools.visualization_tools import show_kpi_card

    result = await show_kpi_card.ainvoke({
        "title": "CA",
        "value": "655 957 FCFA",
        "value_money": {"amount": "655957.00", "currency": "XOF"},
    })

    payload = _extract_json_payload(result)
    assert payload["value_money"] == {"amount": "655957.00", "currency": "XOF"}


def test_args_schema_pydantic() -> None:
    """args_schema pointe vers KPICardArgs."""
    from app.graph.tools.visualization_tools import show_kpi_card
    from app.schemas.visualization import KPICardArgs

    assert show_kpi_card.args_schema is KPICardArgs


def test_docstring_5_sections() -> None:
    """Docstring contient les 5 sections : use when / don't use when / exemple / anti."""
    from app.graph.tools.visualization_tools import show_kpi_card

    doc = show_kpi_card.description.lower()
    assert "use when" in doc or "utilise quand" in doc or "utiliser quand" in doc
    # On accepte les deux écritures (anglais ou français)
    assert "exemple" in doc or "example" in doc


@pytest.mark.asyncio
async def test_emits_sse_marker() -> None:
    """Le tool émet un marker SSE pour transport vers frontend."""
    from app.graph.tools.visualization_tools import show_kpi_card

    result = await show_kpi_card.ainvoke({
        "title": "Score",
        "value": "72",
    })
    assert "<!--SSE:" in result
    assert "__sse_visualization_block__" in result
    assert "show_kpi_card" in result


@pytest.mark.asyncio
async def test_sse_marker_payload_parsable() -> None:
    """Le payload du marker SSE est un JSON parsable contenant le block_type."""
    from app.graph.tools.visualization_tools import show_kpi_card

    result = await show_kpi_card.ainvoke({
        "title": "Score",
        "value": "72",
    })
    sse_marker = "<!--SSE:"
    end_marker = "-->"
    start = result.index(sse_marker) + len(sse_marker)
    end = result.index(end_marker, start)
    sse_data = json.loads(result[start:end])
    assert sse_data.get("block_type") == "show_kpi_card"
    assert sse_data.get("type") == "visualization_block"
    assert sse_data.get("payload", {}).get("title") == "Score"
