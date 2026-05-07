"""F11 — Tests unitaires pour show_map tool.

TDD strict : tests AVANT implémentation.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError


def _extract_json_payload(result: str) -> dict:
    sse_marker = "<!--SSE:"
    if sse_marker in result:
        result = result.split(sse_marker, 1)[0]
    return json.loads(result)


def _valid_marker(**overrides):
    base = {
        "lat": 7.6906,
        "lon": -5.0307,
        "label": "Bouaké",
        "type": "project",
    }
    base.update(overrides)
    return base


def test_tool_registered() -> None:
    from app.graph.tools.visualization_tools import (
        VISUALIZATION_TOOLS,
        show_map,
    )
    assert show_map.name == "show_map"
    assert show_map in VISUALIZATION_TOOLS


@pytest.mark.asyncio
async def test_invocation_valid_minimal() -> None:
    from app.graph.tools.visualization_tools import show_map

    result = await show_map.ainvoke({
        "markers": [_valid_marker()],
    })
    payload = _extract_json_payload(result)
    assert payload["zoom"] == 6
    assert payload["show_uemoa_overlay"] is False
    assert len(payload["markers"]) == 1


@pytest.mark.asyncio
async def test_invocation_with_overlay() -> None:
    from app.graph.tools.visualization_tools import show_map

    result = await show_map.ainvoke({
        "title": "Carte UEMOA",
        "center": [12.0, -2.0],
        "zoom": 5,
        "markers": [
            _valid_marker(),
            _valid_marker(lat=6.1319, lon=1.2228, label="Lomé", type="intermediary"),
        ],
        "show_uemoa_overlay": True,
    })
    payload = _extract_json_payload(result)
    assert payload["show_uemoa_overlay"] is True
    assert payload["title"] == "Carte UEMOA"
    assert len(payload["markers"]) == 2


@pytest.mark.asyncio
async def test_invocation_empty_markers_rejected() -> None:
    from app.graph.tools.visualization_tools import show_map

    with pytest.raises((ValidationError, ValueError)):
        await show_map.ainvoke({"markers": []})


@pytest.mark.asyncio
async def test_invocation_invalid_lat() -> None:
    from app.graph.tools.visualization_tools import show_map

    with pytest.raises((ValidationError, ValueError)):
        await show_map.ainvoke({"markers": [_valid_marker(lat=91.0)]})


@pytest.mark.asyncio
async def test_invocation_long_popup_rejected() -> None:
    from app.graph.tools.visualization_tools import show_map

    with pytest.raises((ValidationError, ValueError)):
        await show_map.ainvoke({
            "markers": [_valid_marker(popup_content="x" * 600)],
        })


def test_args_schema() -> None:
    from app.graph.tools.visualization_tools import show_map
    from app.schemas.visualization import MapArgs
    assert show_map.args_schema is MapArgs
