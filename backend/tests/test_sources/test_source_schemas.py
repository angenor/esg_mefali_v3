"""Tests unitaires des schemas Pydantic Source (F01)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.source import (
    SourceCreate,
    SourceMarkOutdated,
    SourceUpdate,
)


def test_source_create_valid_payload():
    """Payload SourceCreate valide."""
    payload = SourceCreate(
        url="https://ademe.fr/base-carbone-v23",
        title="ADEME Base Carbone v23",
        publisher="ADEME",
        version="v23",
        date_publi=date(2024, 1, 1),
        page=12,
        section="Annexe 3",
    )
    assert payload.title == "ADEME Base Carbone v23"
    assert str(payload.url).startswith("https://ademe.fr")
    assert payload.page == 12


def test_source_create_rejects_invalid_url():
    """URL non https/http rejete."""
    with pytest.raises(ValidationError):
        SourceCreate(
            url="not-a-url",
            title="x",
            publisher="x",
            version="v1",
            date_publi=date.today(),
        )


def test_source_create_rejects_negative_page():
    """page=0 rejete (doit etre >= 1)."""
    with pytest.raises(ValidationError):
        SourceCreate(
            url="https://ok.com/d.pdf",
            title="x",
            publisher="x",
            version="v1",
            date_publi=date.today(),
            page=0,
        )


def test_source_create_rejects_empty_title():
    """title vide rejete."""
    with pytest.raises(ValidationError):
        SourceCreate(
            url="https://ok.com/d.pdf",
            title="",
            publisher="x",
            version="v1",
            date_publi=date.today(),
        )


def test_source_mark_outdated_requires_reason():
    """SourceMarkOutdated.reason ne peut pas etre vide ou whitespace."""
    with pytest.raises(ValidationError):
        SourceMarkOutdated(reason="")
    with pytest.raises(ValidationError):
        SourceMarkOutdated(reason="   ")
    ok = SourceMarkOutdated(reason="Nouvelle version disponible")
    assert ok.reason == "Nouvelle version disponible"


def test_source_update_partial_valid():
    """SourceUpdate accepte des champs partiels."""
    upd = SourceUpdate(title="Nouveau titre")
    data = upd.model_dump(exclude_unset=True)
    assert data == {"title": "Nouveau titre"}
