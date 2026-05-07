"""F04 — Tests immuabilité du snapshot après création."""

from __future__ import annotations

import pytest

from app.modules.applications.snapshot import (
    SnapshotImmutableError,
    validate_immutable,
)


def test_validate_immutable_allows_initial_creation() -> None:
    """Création initiale (existing=None) → OK."""
    validate_immutable(None, {"foo": "bar"})


def test_validate_immutable_rejects_reset_to_none() -> None:
    with pytest.raises(SnapshotImmutableError):
        validate_immutable({"foo": "bar"}, None)


def test_validate_immutable_rejects_modification() -> None:
    existing = {"schema_version": "1.0", "scores": {"esg_total": 75.0}}
    new = {"schema_version": "1.0", "scores": {"esg_total": 80.0}}  # delta!
    with pytest.raises(SnapshotImmutableError):
        validate_immutable(existing, new)


def test_validate_immutable_accepts_identical_payload() -> None:
    snap = {"schema_version": "1.0", "scores": {"esg_total": 75.0}}
    # Idempotence : passer le MÊME payload est OK.
    validate_immutable(snap, dict(snap))
