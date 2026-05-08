"""F15 — Tests des tools LangChain ``TEMPLATE_TOOLS``."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.tools.template_tools import (
    TEMPLATE_TOOLS,
    get_effective_template,
    list_templates,
)

pytestmark = pytest.mark.unit


def _mock_config() -> dict:
    """Construit un RunnableConfig mocké avec db et user_id."""
    return {
        "configurable": {
            "db": MagicMock(),
            "user_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        },
    }


def _mock_template(**overrides):
    template = MagicMock()
    template.id = overrides.get("id", uuid.uuid4())
    template.name = overrides.get("name", "Template test")
    template.instrument_type = overrides.get("instrument_type", "subvention")
    template.language = overrides.get("language", "fr")
    template.version = overrides.get("version", "1.0")
    template.tone = overrides.get("tone", "formel")
    template.sections = overrides.get("sections", [{"key": "intro"}])
    template.required_documents = overrides.get("required_documents", [])
    return template


def test_template_tools_export_list() -> None:
    """L'export TEMPLATE_TOOLS contient bien 2 tools (read-only)."""
    assert len(TEMPLATE_TOOLS) == 2
    names = {t.name for t in TEMPLATE_TOOLS}
    assert names == {"list_templates", "get_effective_template"}


@pytest.mark.asyncio
async def test_list_templates_success() -> None:
    """Le tool retourne la liste sérialisée en JSON ok=true."""
    template = _mock_template()
    with patch(
        "app.modules.applications.template_service.list_templates",
        new_callable=AsyncMock,
        return_value=([template], 1),
    ), patch(
        "app.graph.tools.template_tools.get_db_and_user",
        return_value=(MagicMock(), uuid.uuid4()),
    ):
        result = await list_templates.ainvoke(
            {"language": "fr", "limit": 5},
            config=_mock_config(),
        )
        data = json.loads(result)
        assert data["ok"] is True
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Template test"


@pytest.mark.asyncio
async def test_list_templates_caps_limit() -> None:
    """Limit > 50 est plafonnée."""
    with patch(
        "app.modules.applications.template_service.list_templates",
        new_callable=AsyncMock,
        return_value=([], 0),
    ) as mock_list, patch(
        "app.graph.tools.template_tools.get_db_and_user",
        return_value=(MagicMock(), uuid.uuid4()),
    ):
        await list_templates.ainvoke({"limit": 999}, config=_mock_config())
        # Vérifier que le service a été appelé avec limit=50
        _, kwargs = mock_list.call_args
        assert kwargs.get("limit") == 50


@pytest.mark.asyncio
async def test_list_templates_handles_error() -> None:
    """En cas d'exception, retourne ok=false."""
    with patch(
        "app.graph.tools.template_tools.get_db_and_user",
        side_effect=RuntimeError("boom"),
    ):
        result = await list_templates.ainvoke({}, config=_mock_config())
        data = json.loads(result)
        assert data["ok"] is False
        assert "boom" in data["error"]


@pytest.mark.asyncio
async def test_get_effective_template_found() -> None:
    template = _mock_template(name="Found template")
    with patch(
        "app.modules.applications.template_service.get_effective_template_for_offer",
        new_callable=AsyncMock,
        return_value=template,
    ), patch(
        "app.graph.tools.template_tools.get_db_and_user",
        return_value=(MagicMock(), uuid.uuid4()),
    ):
        result = await get_effective_template.ainvoke(
            {"instrument_type": "subvention", "language": "fr"},
            config=_mock_config(),
        )
        data = json.loads(result)
        assert data["ok"] is True
        assert data["name"] == "Found template"


@pytest.mark.asyncio
async def test_get_effective_template_not_found() -> None:
    with patch(
        "app.modules.applications.template_service.get_effective_template_for_offer",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.graph.tools.template_tools.get_db_and_user",
        return_value=(MagicMock(), uuid.uuid4()),
    ):
        result = await get_effective_template.ainvoke({}, config=_mock_config())
        data = json.loads(result)
        assert data["ok"] is False
        assert "Aucun template" in data["error"]


@pytest.mark.asyncio
async def test_get_effective_template_with_offer_id_uuid() -> None:
    """Le tool accepte un offer_id UUID string."""
    template = _mock_template()
    with patch(
        "app.modules.applications.template_service.get_effective_template_for_offer",
        new_callable=AsyncMock,
        return_value=template,
    ), patch(
        "app.graph.tools.template_tools.get_db_and_user",
        return_value=(MagicMock(), uuid.uuid4()),
    ):
        result = await get_effective_template.ainvoke(
            {"offer_id": str(uuid.uuid4()), "language": "en"},
            config=_mock_config(),
        )
        data = json.loads(result)
        assert data["ok"] is True
