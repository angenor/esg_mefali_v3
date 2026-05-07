"""F11 — Tests unitaires pour show_comparison_table tool.

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


def _valid_payload():
    return {
        "title": "Comparaison fonds GCF",
        "subjects": [
            {"id": "boad", "label": "GCF via BOAD"},
            {"id": "undp", "label": "GCF via UNDP"},
        ],
        "rows": [
            {
                "label": "Frais d'instruction",
                "type": "money",
                "values": [
                    {
                        "subject_id": "boad",
                        "value": "100000",
                        "money": {"amount": "100000.00", "currency": "XOF"},
                    },
                    {
                        "subject_id": "undp",
                        "value": "150000",
                        "money": {"amount": "150000.00", "currency": "XOF"},
                    },
                ],
            },
            {
                "label": "Délai instruction",
                "type": "duration",
                "values": [
                    {"subject_id": "boad", "value": "12 mois"},
                    {"subject_id": "undp", "value": "8 mois"},
                ],
                "higher_is_better": False,
            },
        ],
    }


def test_tool_registered() -> None:
    from app.graph.tools.visualization_tools import (
        VISUALIZATION_TOOLS,
        show_comparison_table,
    )
    assert show_comparison_table.name == "show_comparison_table"
    assert show_comparison_table in VISUALIZATION_TOOLS


@pytest.mark.asyncio
async def test_invocation_valid() -> None:
    from app.graph.tools.visualization_tools import show_comparison_table

    result = await show_comparison_table.ainvoke(_valid_payload())
    payload = _extract_json_payload(result)
    assert payload["title"] == "Comparaison fonds GCF"
    assert len(payload["subjects"]) == 2
    assert payload["highlight_winner"] is True


@pytest.mark.asyncio
async def test_invocation_too_many_subjects_rejected() -> None:
    """> 5 subjects rejeté."""
    from app.graph.tools.visualization_tools import show_comparison_table

    p = _valid_payload()
    p["subjects"] = [{"id": f"s{i}", "label": f"S{i}"} for i in range(6)]
    with pytest.raises((ValidationError, ValueError)):
        await show_comparison_table.ainvoke(p)


@pytest.mark.asyncio
async def test_cross_field_validator_subject_ids_mismatch() -> None:
    """values.subject_id ne couvre pas exactement subjects.id → erreur."""
    from app.graph.tools.visualization_tools import show_comparison_table

    p = _valid_payload()
    # rows[0].values référence "xxx" au lieu de "boad"
    p["rows"][0]["values"] = [
        {"subject_id": "xxx", "value": "1"},
        {"subject_id": "undp", "value": "2"},
    ]
    with pytest.raises((ValidationError, ValueError)):
        await show_comparison_table.ainvoke(p)


@pytest.mark.asyncio
async def test_invocation_invalid_row_type() -> None:
    from app.graph.tools.visualization_tools import show_comparison_table

    p = _valid_payload()
    p["rows"][0]["type"] = "not-a-type"
    with pytest.raises((ValidationError, ValueError)):
        await show_comparison_table.ainvoke(p)


def test_args_schema() -> None:
    from app.graph.tools.visualization_tools import show_comparison_table
    from app.schemas.visualization import ComparisonTableArgs
    assert show_comparison_table.args_schema is ComparisonTableArgs
