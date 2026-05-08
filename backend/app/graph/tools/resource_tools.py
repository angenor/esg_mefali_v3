"""F20 — Tools LangChain READ-ONLY pour la bibliothèque Resources.

Trois actions :
- ``search_resources(query, type, category)`` : recherche full-text simple.
- ``get_resource_content(slug)`` : retourne le markdown + source liée.
- ``recommend_resources_for_user()`` : recommandation contextuelle déterministe.

INVARIANT (US6 / FR-022 / SC-007) : aucun tool ne mute la table ``resources``.
Test de conformité bloquant dans
``tests/graph/tools/test_no_resource_mutation_tool.py`` (pattern F23).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user
from app.modules.resources.service import ResourceService

logger = logging.getLogger(__name__)


def _serialize_resource(r: Any) -> dict:
    return {
        "id": str(r.id),
        "type": r.type,
        "title": r.title,
        "slug": r.slug,
        "description": r.description,
        "category": list(r.category or []),
        "language": r.language,
        "duration_seconds": r.duration_seconds,
        "intermediary_id": str(r.intermediary_id) if r.intermediary_id else None,
        "version": r.version,
        "view_count": r.view_count,
    }


@tool
async def search_resources(
    query: str,
    type: str | None = None,
    category: str | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Cherche les ressources publiées de la bibliothèque (F20).

    Use when:
    - l'utilisateur demande un guide, un modèle, une vidéo ou une FAQ.
    - tu veux pointer vers une fiche pratique d'intermédiaire (BOAD, GCF...).

    Don't use when:
    - une mutation est demandée (interdit, lecture seule).

    Args:
        query: mots-clés (FR), 1-100 caractères.
        type: filtrer par type (guide, template_doc, video, faq, intermediary_guide).
        category: filtrer par catégorie (governance, environment, ...).

    Returns:
        JSON sérialisé d'une liste (max 10) de ressources avec slug + titre.
    """
    if not query or not query.strip():
        return json.dumps({"results": [], "error": "query required"}, ensure_ascii=False)

    if config is None:
        return json.dumps({"results": [], "error": "missing config"}, ensure_ascii=False)
    try:
        db, _ = get_db_and_user(config)
    except ValueError as exc:
        return json.dumps({"results": [], "error": str(exc)}, ensure_ascii=False)

    service = ResourceService(db)
    resources = await service.search_resources(
        query.strip(), type_=type, category=category, limit=10
    )
    payload = {"results": [_serialize_resource(r) for r in resources]}
    return json.dumps(payload, ensure_ascii=False)


@tool
async def get_resource_content(
    slug: str,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Retourne le contenu markdown et la source d'une ressource publiée (F20).

    Use when:
    - tu veux citer le contenu d'un guide à un utilisateur.

    Args:
        slug: slug URL de la ressource (ex 'guide-esg-uemoa').

    Returns:
        JSON avec le markdown et la source liée, ou error si introuvable.
    """
    if not slug:
        return json.dumps({"error": "slug required"}, ensure_ascii=False)

    if config is None:
        return json.dumps({"error": "missing config"}, ensure_ascii=False)
    try:
        db, _ = get_db_and_user(config)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    service = ResourceService(db)
    resource = await service.get_by_slug(slug)
    if resource is None:
        return json.dumps(
            {"error": "resource_not_found", "slug": slug}, ensure_ascii=False
        )

    payload = {
        **_serialize_resource(resource),
        "content_md": resource.content_md,
        "source_id": str(resource.source_id),
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
async def recommend_resources_for_user(
    limit: int = 5,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Recommande 1-5 ressources adaptées au profil et aux scores de l'utilisateur (F20).

    Use when:
    - l'utilisateur termine un module (ESG, carbone) et veut aller plus loin.
    - le score d'un pilier est bas (< 50) et tu veux suggérer un guide ciblé.

    Args:
        limit: nombre maximum de recommandations (1-10, défaut 5).

    Returns:
        JSON liste de ressources triées par pertinence décroissante.
    """
    if config is None:
        return json.dumps({"results": [], "error": "missing config"}, ensure_ascii=False)
    try:
        db, _ = get_db_and_user(config)
    except ValueError as exc:
        return json.dumps({"results": [], "error": str(exc)}, ensure_ascii=False)

    bounded_limit = max(1, min(int(limit or 5), 10))

    configurable = config.get("configurable", {}) or {}
    scores = configurable.get("scores")
    active_module = configurable.get("active_module")

    service = ResourceService(db)
    resources = await service.get_recommendations(
        scores=scores if isinstance(scores, dict) else None,
        active_module=active_module if isinstance(active_module, str) else None,
        limit=bounded_limit,
    )
    payload = {"results": [_serialize_resource(r) for r in resources]}
    return json.dumps(payload, ensure_ascii=False)


RESOURCE_TOOLS: list = [
    search_resources,
    get_resource_content,
    recommend_resources_for_user,
]
