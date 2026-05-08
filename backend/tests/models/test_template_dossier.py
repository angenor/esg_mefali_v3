"""F15 — Tests unitaires modèle ``TemplateDossier``."""

from __future__ import annotations

import pytest

from app.models.template_dossier import (
    TemplateDossier,
    TemplateInstrumentType,
    TemplateLanguage,
    TemplateStatus,
)

pytestmark = pytest.mark.unit


def test_enum_values_complete() -> None:
    """Les enums Python miroirs des CHECK constraints sont complets."""
    assert {e.value for e in TemplateLanguage} == {"fr", "en"}
    assert {e.value for e in TemplateStatus} == {"draft", "published"}
    assert {e.value for e in TemplateInstrumentType} == {
        "subvention", "prêt_concessionnel", "equity", "blending", "mixte",
    }


def test_tablename() -> None:
    assert TemplateDossier.__tablename__ == "templates_dossier"


def test_constraints_present() -> None:
    """Les CHECK constraints critiques sont déclarées sur le modèle."""
    constraint_names = {c.name for c in TemplateDossier.__table__.constraints if c.name}
    assert "templates_dossier_instrument_chk" in constraint_names
    assert "templates_dossier_language_chk" in constraint_names
    assert "templates_dossier_status_chk" in constraint_names
    assert "templates_dossier_four_eyes_chk" in constraint_names
    assert "templates_dossier_published_requires_verifier_chk" in constraint_names


def test_versioning_mixin_columns() -> None:
    """VersioningMixin F04 fournit version/valid_from/valid_to/superseded_by."""
    cols = {c.name for c in TemplateDossier.__table__.columns}
    assert "version" in cols
    assert "valid_from" in cols
    assert "valid_to" in cols
    assert "superseded_by" in cols


def test_repr_contains_key_fields() -> None:
    template = TemplateDossier(
        name="X",
        instrument_type="subvention",
        language="fr",
        sections=[],
        required_documents=[],
        tone="formel",
        skill_id="00000000-0000-0000-0000-000000000001",
        source_id="00000000-0000-0000-0000-000000000002",
        captured_by="00000000-0000-0000-0000-000000000003",
        version="1.0",
        status="draft",
    )
    rep = repr(template)
    assert "TemplateDossier" in rep
    assert "subvention" in rep
    assert "fr" in rep


def test_exempt_models_includes_template_dossier() -> None:
    """Le modèle est dans EXEMPT_MODELS (catalogue admin-only F03)."""
    from app.core.auditable import EXEMPT_MODELS

    assert "TemplateDossier" in EXEMPT_MODELS
