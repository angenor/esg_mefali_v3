"""F15 — Tools LangChain pour Templates Dossier (read-only).

Le LLM ne peut PAS muter Templates (catalogue admin-only). Les seuls
tools exposés sont en lecture :

- ``list_templates`` : liste filtrable des templates publiés.
- ``get_effective_template`` : résolution offre→template effectif.

Test garde-fou : ``tests/graph/tools/test_no_template_mutation_tool.py``.
"""

from __future__ import annotations

import json
import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


@tool
async def list_templates(
    config: RunnableConfig,
    instrument_type: str | None = None,
    language: str | None = None,
    limit: int = 10,
) -> str:
    """Liste les templates de dossier de candidature publiés.

    Use when:
    - exploration des modèles de dossier disponibles.
    - aide à la sélection avant ``create_fund_application``.
    Don't use when:
    - création/édition d'un template (admin-only via back-office).
    Exemple: "Quels modèles de dossier existent ?" -> list_templates(language='fr').

    Args:
        instrument_type: Filtre optionnel ``subvention|prêt_concessionnel|
            equity|blending|mixte``.
        language: Filtre optionnel ``fr|en``.
        limit: Nombre maximum de templates (défaut 10, max 50).
    """
    from app.modules.applications.template_service import (
        list_templates as svc_list_templates,
    )

    try:
        db, _user_id = get_db_and_user(config)
        capped_limit = max(1, min(int(limit), 50))
        templates, total = await svc_list_templates(
            db,
            instrument_type=instrument_type,
            language=language,
            status="published",
            limit=capped_limit,
        )
        items = [
            {
                "id": str(t.id),
                "name": t.name,
                "instrument_type": t.instrument_type,
                "language": t.language,
                "version": t.version,
                "section_count": len(t.sections or []),
                "doc_count": len(t.required_documents or []),
            }
            for t in templates
        ]
        return json.dumps(
            {"ok": True, "total": total, "items": items},
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("list_templates failed")
        return json.dumps({"ok": False, "error": str(e)})


@tool
async def get_effective_template(
    config: RunnableConfig,
    offer_id: str | None = None,
    instrument_type: str | None = None,
    language: str = "fr",
) -> str:
    """Récupère le template effectif (publié) pour une offre+langue.

    Use when:
    - avant ``create_fund_application``, pour vérifier qu'un template
      officiel existe.
    Don't use when:
    - exploration libre (utiliser ``list_templates``).

    Args:
        offer_id: UUID de l'offre F07 cible (optionnel — fallback par
            ``instrument_type`` si absent).
        instrument_type: Type d'instrument pour fallback générique.
        language: ``fr`` (défaut) ou ``en``.
    """
    from app.modules.applications.template_service import (
        get_effective_template_for_offer,
    )

    try:
        db, _user_id = get_db_and_user(config)
        oid = uuid.UUID(offer_id) if offer_id else None
        template = await get_effective_template_for_offer(
            db,
            offer_id=oid,
            instrument_type=instrument_type,
            language=language,
        )
        if template is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        "Aucun template publié n'existe pour cette offre. "
                        "Demander à un admin de publier un template."
                    ),
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "ok": True,
                "id": str(template.id),
                "name": template.name,
                "instrument_type": template.instrument_type,
                "language": template.language,
                "version": template.version,
                "tone": template.tone,
                "section_count": len(template.sections or []),
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("get_effective_template failed")
        return json.dumps({"ok": False, "error": str(e)})


TEMPLATE_TOOLS = [list_templates, get_effective_template]
