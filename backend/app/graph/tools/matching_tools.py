"""Tools LangChain pour le matching Project ↔ Offer (F14).

4 tools async décorés ``@tool`` :
- ``list_matches_for_project`` (lecture) : retourne JSON compact
- ``compare_offers_for_fund_v2`` (lecture) : émet marker SSE block visualisation
- ``recompute_matches_for_project`` (mutation, scope=llm)
- ``get_match_details`` (lecture)

Tous utilisent ``args_schema`` Pydantic strict (extra='forbid').
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.audit_context import source_of_change_scope
from app.graph.tools.common import get_db_and_user
from app.models.user import User
from app.modules.financing import matching_service


logger = logging.getLogger(__name__)


# =====================================================================
# Helpers
# =====================================================================


async def _resolve_account_id(config: RunnableConfig) -> tuple[Any, uuid.UUID, uuid.UUID]:
    """(db, user_id, account_id) depuis le RunnableConfig (cf. project_tools)."""
    db, user_id = get_db_and_user(config)
    configurable = (config or {}).get("configurable", {})
    raw = configurable.get("account_id")
    if raw is not None:
        account_id = uuid.UUID(raw) if isinstance(raw, str) else raw
    else:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.account_id is None:
            raise ValueError(
                "account_id introuvable pour l'utilisateur courant — tool "
                "matching inutilisable hors d'un compte."
            )
        account_id = user.account_id
    return db, user_id, account_id


# =====================================================================
# Args schemas
# =====================================================================


class ListMatchesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet")]
    min_score: Annotated[int, Field(ge=0, le=100, default=60)] = 60
    limit: Annotated[int, Field(ge=1, le=50, default=10)] = 10
    bottleneck: Annotated[
        str | None,
        Field(default=None, description="fund/intermediary/balanced ou null"),
    ] = None


class CompareOffersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet")]
    fund_id: Annotated[uuid.UUID, Field(description="UUID du fonds")]


class RecomputeMatchesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet")]


class GetMatchDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet")]
    offer_id: Annotated[uuid.UUID, Field(description="UUID de l'offre")]


# =====================================================================
# Tools
# =====================================================================


@tool(args_schema=ListMatchesArgs)
async def list_matches_for_project(
    project_id: uuid.UUID,
    min_score: int = 60,
    limit: int = 10,
    bottleneck: str | None = None,
    config: RunnableConfig | None = None,
) -> str:
    """Liste les offres matchées pour un projet (lecture seule).

    Use when:
    - L'utilisateur demande « quelles offres correspondent à mon projet ? ».
    - Avant un comparateur, pour identifier le top N.
    Don't use when:
    - Comparaison directe entre 2 intermédiaires d'un même fonds (utiliser
      ``compare_offers_for_fund_v2``).

    Args:
        project_id: UUID du projet
        min_score: Score minimum (default 60)
        limit: Nombre max de matches retournés (default 10, max 50)
        bottleneck: Filtrer par goulot (fund/intermediary/balanced), optionnel
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config or {})
        items, total = await matching_service.list_matches_for_project(
            db,
            account_id=account_id,
            project_id=project_id,
            min_score=min_score,
            bottleneck=bottleneck,
            limit=min(limit, 50),
            page=1,
        )
        payload = {
            "project_id": str(project_id),
            "total": total,
            "matches": [
                {
                    "id": str(m.id),
                    "offer_id": str(m.offer_id),
                    "global_score": m.global_score,
                    "fund_score": m.fund_score,
                    "intermediary_score": m.intermediary_score,
                    "bottleneck": m.bottleneck,
                }
                for m in items
            ],
        }
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        logger.exception("list_matches_for_project failed")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=CompareOffersArgs)
async def compare_offers_for_fund_v2(
    project_id: uuid.UUID,
    fund_id: uuid.UUID,
    config: RunnableConfig | None = None,
) -> str:
    """Compare les voies d'accès (intermédiaires) à un fonds pour un projet.

    Émet un block visualisation typé F11 ``ComparisonTable`` via marker SSE.

    Use when:
    - L'utilisateur demande « compare BOAD vs UNDP vs AFD pour le GCF ».
    - Avant le choix d'intermédiaire pour une candidature.
    """
    try:
        db, _user_id, _account_id = await _resolve_account_id(config or {})
        result = await matching_service.compare_offers_for_fund(
            db, project_id=project_id, fund_id=fund_id,
        )
        await db.commit()

        # Marker SSE pour F11 ComparisonTable.
        block = {
            "__sse_visualization_block__": True,
            "block_type": "comparison_table",
            "payload": {
                "fund_id": str(result["fund_id"]),
                "project_id": str(result["project_id"]),
                "subjects": result["subjects"],
                "rows": result["rows"],
            },
        }
        marker = "<!--SSE:" + json.dumps(block, ensure_ascii=False, default=str) + "-->"
        summary = (
            f"{len(result['subjects'])} voie(s) d'accès comparée(s) pour le fonds. "
            "Voir le tableau ci-dessous."
        )
        return summary + "\n" + marker
    except Exception as e:  # noqa: BLE001
        logger.exception("compare_offers_for_fund_v2 failed")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=RecomputeMatchesArgs)
async def recompute_matches_for_project(
    project_id: uuid.UUID,
    config: RunnableConfig | None = None,
) -> str:
    """Déclenche un recalcul des matches d'un projet (mutation).

    Use when:
    - L'utilisateur a modifié son projet et veut un score à jour.
    - Diagnostic : vérifier que le matching est synchrone avec les données.
    """
    try:
        db, _user_id, _account_id = await _resolve_account_id(config or {})
        with source_of_change_scope("llm"):
            request_id, total = await matching_service.recompute_matches_for_project(
                db, project_id=project_id,
            )
            await matching_service.execute_recompute_batch(
                db, project_id=project_id,
            )
        return json.dumps(
            {
                "ok": True,
                "recompute_request_id": str(request_id),
                "total_offers_to_compute": total,
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("recompute_matches_for_project failed")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=GetMatchDetailsArgs)
async def get_match_details(
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
    config: RunnableConfig | None = None,
) -> str:
    """Détail d'un match (critères manquants, sub-scores).

    Use when:
    - L'utilisateur veut comprendre un score détaillé.
    - Avant de chercher des sources F01 sur un critère manquant.
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config or {})
        match = await matching_service.get_match_details(
            db,
            account_id=account_id,
            project_id=project_id,
            offer_id=offer_id,
        )
        if match is None:
            return json.dumps(
                {"ok": False, "error": "match_not_found"},
                ensure_ascii=False,
            )
        payload = {
            "ok": True,
            "id": str(match.id),
            "global_score": match.global_score,
            "fund_score": match.fund_score,
            "intermediary_score": match.intermediary_score,
            "bottleneck": match.bottleneck,
            "score_breakdown": match.score_breakdown,
            "recommended_actions": match.recommended_actions,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        logger.exception("get_match_details failed")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


# =====================================================================
# Exports
# =====================================================================

MATCHING_TOOLS = [
    list_matches_for_project,
    compare_offers_for_fund_v2,
    recompute_matches_for_project,
    get_match_details,
]

MATCHING_READ_TOOLS = [
    list_matches_for_project,
    compare_offers_for_fund_v2,
    get_match_details,
]
