"""F21 — Tests unitaires du tool LangChain `generate_carbon_report`."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
def runnable_config(db_session):
    user_id = uuid.uuid4()
    return {
        "configurable": {
            "db": db_session,
            "user_id": str(user_id),
        }
    }, user_id


class TestGenerateCarbonReportTool:
    async def test_returns_error_when_invalid_assessment_id(
        self, runnable_config
    ) -> None:
        from app.graph.tools.carbon_tools import generate_carbon_report

        config, _ = runnable_config
        with patch(
            "app.graph.tools.carbon_tools.get_db_and_user",
            return_value=(config["configurable"]["db"], uuid.UUID(config["configurable"]["user_id"])),
        ):
            result = await generate_carbon_report.ainvoke(
                {"assessment_id": "not-a-uuid"}, config=config
            )
        data = json.loads(result)
        assert data["ok"] is False
        assert "invalide" in data["error"].lower() or "invalid" in data["error"].lower()

    async def test_returns_error_when_no_assessment(self, runnable_config) -> None:
        from app.graph.tools.carbon_tools import generate_carbon_report

        config, user_id = runnable_config
        with patch(
            "app.graph.tools.carbon_tools.get_db_and_user",
            return_value=(config["configurable"]["db"], user_id),
        ), patch(
            "app.modules.carbon.service.get_latest_assessment", AsyncMock(return_value=None)
        ):
            result = await generate_carbon_report.ainvoke({}, config=config)
        data = json.loads(result)
        assert data["ok"] is False
        assert "aucun bilan" in data["error"].lower()

    async def test_tool_is_in_carbon_tools_export(self) -> None:
        """Verifier que le tool est exporte dans CARBON_TOOLS."""
        from app.graph.tools.carbon_tools import CARBON_TOOLS, generate_carbon_report

        assert generate_carbon_report in CARBON_TOOLS
