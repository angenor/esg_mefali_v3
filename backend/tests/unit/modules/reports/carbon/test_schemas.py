"""F21 — Tests unitaires des schémas Pydantic du rapport carbone."""

import uuid
from datetime import datetime, timezone

import pytest

from app.modules.reports.carbon.schemas import (
    CarbonReportListItem,
    CarbonReportRequest,
    CarbonReportResponse,
    CarbonReportStatus,
)


class TestCarbonReportRequest:
    def test_default_includes_appendix(self) -> None:
        req = CarbonReportRequest()
        assert req.include_appendix_sources is True

    def test_explicit_false(self) -> None:
        req = CarbonReportRequest(include_appendix_sources=False)
        assert req.include_appendix_sources is False


class TestCarbonReportResponse:
    def test_required_fields(self) -> None:
        rid = uuid.uuid4()
        aid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        resp = CarbonReportResponse(
            id=rid,
            assessment_id=aid,
            status=CarbonReportStatus.generating,
            created_at=now,
        )
        assert resp.id == rid
        assert resp.assessment_id == aid
        assert resp.report_type == "carbon"  # défaut

    def test_status_string_coerced(self) -> None:
        resp = CarbonReportResponse(
            id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.status == CarbonReportStatus.ready


class TestCarbonReportListItem:
    def test_serialization_with_download_url(self) -> None:
        item = CarbonReportListItem(
            id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            status=CarbonReportStatus.completed,
            file_size=12345,
            generated_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            download_url="/api/reports/abc/download",
        )
        d = item.model_dump()
        assert "download_url" in d
        assert d["status"] == "completed"

    def test_optional_fields_default_none(self) -> None:
        item = CarbonReportListItem(
            id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            status=CarbonReportStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        assert item.file_size is None
        assert item.generated_at is None
        assert item.download_url is None


class TestCarbonReportStatus:
    def test_all_statuses_present(self) -> None:
        assert CarbonReportStatus.pending.value == "pending"
        assert CarbonReportStatus.generating.value == "generating"
        assert CarbonReportStatus.ready.value == "ready"
        assert CarbonReportStatus.failed.value == "failed"
        assert CarbonReportStatus.completed.value == "completed"
