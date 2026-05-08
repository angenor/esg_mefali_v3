"""F16 — Tools LangChain pour le simulateur sourcé.

- :func:`compare_simulations` : compare 1..5 offres pour un projet, émet le
  marker SSE F11 ``visualization_block`` avec un payload ComparisonTable
  conforme F11 et retourne un résumé JSON court au LLM.
- :func:`simulate_financing_offer` (alias léger pour 1 offre — pratique pour
  un usage conversationnel).

Read-only sur le catalogue (jamais d'écriture).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.database import async_session_factory
from app.modules.applications.multi_simulate_service import (
    OfferAccessDeniedError,
    ProjectNotFoundError,
    simulate_multi,
)
from app.modules.applications.simulation_schemas import (
    DegradedColumn,
    SimulationResult,
)


logger = logging.getLogger(__name__)


class CompareSimulationsArgs(BaseModel):
    """Arguments du tool ``compare_simulations`` (Pydantic strict)."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID = Field(..., description="UUID du projet vert.")
    offer_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="1 à 5 UUIDs d'offres (Fonds×Intermédiaire) à comparer.",
    )

    @field_validator("offer_ids", mode="after")
    @classmethod
    def _dedup(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        seen: set[uuid.UUID] = set()
        result: list[uuid.UUID] = []
        for oid in value:
            if oid not in seen:
                seen.add(oid)
                result.append(oid)
        if not result:
            raise ValueError("au moins 1 offre requise")
        if len(result) > 5:
            raise ValueError("max_5_offres")
        return result


def _build_comparison_payload(
    response, *, project_id: uuid.UUID
) -> dict[str, Any]:
    """Construit un payload ComparisonTable F11-compatible.

    Le payload final est typé côté F11 par ``ComparisonTableArgs`` (subjects,
    rows, winner_indices). Ici on produit la structure JSON brute que le
    composant frontend ``ComparisonTableBlock`` consomme.
    """
    subjects: list[dict[str, str]] = []
    cost_row_values: list[dict[str, Any]] = []
    timeline_row_values: list[dict[str, Any]] = []
    instrument_row_values: list[dict[str, Any]] = []

    cheapest = response.comparison_metadata.cheapest_offer_id
    fastest = response.comparison_metadata.fastest_offer_id

    for oid, col in response.per_offer.items():
        if isinstance(col, SimulationResult):
            subjects.append(
                {"id": str(oid), "label": f"Offre {str(oid)[:8]}"}
            )
            cost_row_values.append(
                {
                    "subject_id": str(oid),
                    "value": str(col.cost_breakdown.total_cost.amount),
                    "currency": col.cost_breakdown.total_cost.currency,
                    "type": "money",
                }
            )
            total_weeks_max = sum(
                (s.weeks_max or 0)
                for s in col.timeline
                if s.step_id != "preparation"
            )
            timeline_row_values.append(
                {
                    "subject_id": str(oid),
                    "value": total_weeks_max,
                    "type": "duration",
                    "unit": "weeks",
                }
            )
            instrument_row_values.append(
                {
                    "subject_id": str(oid),
                    "value": col.roi.instrument,
                    "type": "string",
                }
            )
        else:
            assert isinstance(col, DegradedColumn)
            subjects.append(
                {
                    "id": str(oid),
                    "label": f"Offre {str(oid)[:8]} (indisponible)",
                }
            )

    rows = [
        {
            "label_fr": "Coût total",
            "values": cost_row_values,
            "winner_subject_id": str(cheapest) if cheapest else None,
        },
        {
            "label_fr": "Durée totale (semaines)",
            "values": timeline_row_values,
            "winner_subject_id": str(fastest) if fastest else None,
        },
        {
            "label_fr": "Instrument financier",
            "values": instrument_row_values,
            "winner_subject_id": None,
        },
    ]

    return {
        "title_fr": "Comparaison des offres simulées",
        "subjects": subjects,
        "rows": rows,
        "project_id": str(project_id),
        "cheapest_offer_id": str(cheapest) if cheapest else None,
        "fastest_offer_id": str(fastest) if fastest else None,
    }


def _build_sse_marker(payload: dict) -> str:
    """Marker SSE F11 ``visualization_block`` (block_type=comparison_table)."""
    marker_data = {
        "__sse_visualization_block__": True,
        "type": "visualization_block",
        "block_type": "comparison_table",
        "payload": payload,
    }
    return f"<!--SSE:{json.dumps(marker_data, ensure_ascii=False)}-->"


@tool(args_schema=CompareSimulationsArgs)
async def compare_simulations(**kwargs) -> str:
    """Compare 1..5 offres pour un projet et rend un tableau comparatif F11.

    Use when:
    - la PME demande à comparer 2 ou 3 offres précises (par UUID) sur son projet ;
    - un dossier de candidature exige de défendre le choix d'une offre.

    Don't use when:
    - aucun project_id n'est connu (poser d'abord une question interactive).
    - la PME demande la liste de toutes les offres (utiliser ``search_compatible_funds``).

    Args (validés via ``CompareSimulationsArgs``) :
        project_id : UUID du projet (multi-tenant : doit appartenir au compte).
        offer_ids : 1..5 UUIDs d'offres (dédupliqués automatiquement).

    Returns:
        JSON court ``{ok: true, compared: N, cheapest_offer_id, fastest_offer_id}``
        précédé du marker SSE F11 ``visualization_block`` qui transporte le
        payload ComparisonTable au frontend.
    """
    args = CompareSimulationsArgs(**kwargs)
    project_id = args.project_id
    offer_ids = args.offer_ids

    try:
        async with async_session_factory() as db:
            response = await simulate_multi(
                db,
                project_id=project_id,
                offer_ids=offer_ids,
                account_id=None,  # tool conversationnel : RLS via session PG
            )
    except ProjectNotFoundError:
        return json.dumps(
            {"ok": False, "error": "project_required"},
            ensure_ascii=False,
        )
    except OfferAccessDeniedError:
        return json.dumps(
            {"ok": False, "error": "access_denied"},
            ensure_ascii=False,
        )
    except ValueError as exc:
        return json.dumps(
            {"ok": False, "error": str(exc)},
            ensure_ascii=False,
        )

    payload = _build_comparison_payload(response, project_id=project_id)
    marker = _build_sse_marker(payload)
    summary = {
        "ok": True,
        "compared": response.comparison_metadata.total_offers,
        "cheapest_offer_id": (
            str(response.comparison_metadata.cheapest_offer_id)
            if response.comparison_metadata.cheapest_offer_id
            else None
        ),
        "fastest_offer_id": (
            str(response.comparison_metadata.fastest_offer_id)
            if response.comparison_metadata.fastest_offer_id
            else None
        ),
        "degraded_offers": [
            str(x) for x in response.comparison_metadata.degraded_offers
        ],
    }
    return marker + json.dumps(summary, ensure_ascii=False)


SIMULATION_TOOLS: list = [compare_simulations]
