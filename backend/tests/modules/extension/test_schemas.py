"""Tests Pydantic schemas pour le module extension (F24)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.modules.extension.schemas import (
    AuthExchangeRequest,
    AuthExchangeResponse,
    DetectRequest,
    DetectResponse,
    FundUrlPattern,
    ProfileSnapshot,
    ProjectSnapshotItem,
)


class TestAuthExchangeRequest:
    def test_valid(self):
        req = AuthExchangeRequest(email="user@test.fr", password="Password1!")
        assert req.email == "user@test.fr"
        assert req.password == "Password1!"

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            AuthExchangeRequest(  # type: ignore[call-arg]
                email="x@y.fr", password="Password1!", malicious="yes"
            )

    def test_rejects_short_password(self):
        with pytest.raises(ValidationError):
            AuthExchangeRequest(email="x@y.fr", password="short")

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            AuthExchangeRequest(email="not-an-email", password="Password1!")


class TestAuthExchangeResponse:
    def test_valid_default_scope(self):
        resp = AuthExchangeResponse(
            access_token="a", refresh_token="b", expires_in=2592000
        )
        assert resp.scope == "extension"

    def test_rejects_zero_expires_in(self):
        with pytest.raises(ValidationError):
            AuthExchangeResponse(
                access_token="a", refresh_token="b", expires_in=0
            )


class TestDetectRequest:
    def test_valid_https(self):
        req = DetectRequest(url="https://example.com/page")
        assert req.url.startswith("https://")

    def test_valid_http(self):
        req = DetectRequest(url="http://example.com")
        assert req.url == "http://example.com"

    def test_rejects_no_scheme(self):
        with pytest.raises(ValidationError):
            DetectRequest(url="example.com/foo")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            DetectRequest(url="https://x.fr", evil="yes")  # type: ignore[call-arg]

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            DetectRequest(url="https://" + "a" * 3000)


class TestDetectResponse:
    def test_valid(self):
        resp = DetectResponse(
            offer_id=uuid.uuid4(),
            offer_name="Offre",
            source_id=uuid.uuid4(),
            confidence=0.9,
        )
        assert resp.confidence == 0.9

    def test_rejects_confidence_above_one(self):
        with pytest.raises(ValidationError):
            DetectResponse(
                offer_id=uuid.uuid4(), offer_name="X", confidence=1.5
            )


class TestProfileSnapshot:
    def test_empty_projects(self):
        snap = ProfileSnapshot(sector=None, country=None, projects=[])
        assert snap.projects == []

    def test_max_three_projects(self):
        # max_length=3 sur le champ projects
        items = [
            ProjectSnapshotItem(id=uuid.uuid4(), name=f"P{i}", status="draft")
            for i in range(4)
        ]
        with pytest.raises(ValidationError):
            ProfileSnapshot(sector="agri", country="SN", projects=items)


class TestFundUrlPattern:
    def test_valid_homepage(self):
        p = FundUrlPattern(pattern=r"^https://x\.fr", scope="homepage")
        assert p.scope == "homepage"

    def test_rejects_invalid_scope(self):
        with pytest.raises(ValidationError):
            FundUrlPattern(pattern=r"^x", scope="other")  # type: ignore[arg-type]

    def test_rejects_empty_pattern(self):
        with pytest.raises(ValidationError):
            FundUrlPattern(pattern="", scope="homepage")
