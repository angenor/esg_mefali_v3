"""F045 T010 - Tests Pydantic v2 strict pour les 5 nouveaux champs projet.

Verifie la validation Literal/range/dedupe pour :
- taxonomie_verte_uemoa_aligned (bool | None)
- gcf_priority_themes (list[Literal..], max_length=8, dedupe)
- gender_inclusion (bool | None)
- vulnerable_populations (list[Literal..], max_length=5, dedupe)
- project_esg_score (int | None, 0..100)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


@pytest.mark.unit
def test_project_create_accepts_new_fields() -> None:
    from app.modules.projects.schemas import ProjectCreate

    p = ProjectCreate(
        name="Agroforesterie Togo",
        taxonomie_verte_uemoa_aligned=True,
        gcf_priority_themes=["adaptation", "REDD+", "forêts"],
        gender_inclusion=True,
        vulnerable_populations=["femmes", "jeunes"],
        project_esg_score=72,
    )
    assert p.taxonomie_verte_uemoa_aligned is True
    assert p.gcf_priority_themes == ["adaptation", "REDD+", "forêts"]
    assert p.gender_inclusion is True
    assert p.vulnerable_populations == ["femmes", "jeunes"]
    assert p.project_esg_score == 72


@pytest.mark.unit
def test_project_create_defaults_new_fields() -> None:
    from app.modules.projects.schemas import ProjectCreate

    p = ProjectCreate(name="Vide")
    assert p.taxonomie_verte_uemoa_aligned is None
    assert p.gcf_priority_themes == []
    assert p.gender_inclusion is None
    assert p.vulnerable_populations == []
    assert p.project_esg_score is None


@pytest.mark.unit
def test_gcf_priority_themes_rejects_unknown_value() -> None:
    from app.modules.projects.schemas import ProjectCreate

    with pytest.raises(ValidationError):
        ProjectCreate(name="X", gcf_priority_themes=["invalid_theme"])


@pytest.mark.unit
def test_vulnerable_populations_rejects_unknown_value() -> None:
    from app.modules.projects.schemas import ProjectCreate

    with pytest.raises(ValidationError):
        ProjectCreate(name="X", vulnerable_populations=["LGBTQ+"])


@pytest.mark.unit
def test_project_esg_score_range() -> None:
    from app.modules.projects.schemas import ProjectCreate

    with pytest.raises(ValidationError):
        ProjectCreate(name="X", project_esg_score=-1)
    with pytest.raises(ValidationError):
        ProjectCreate(name="X", project_esg_score=101)
    ProjectCreate(name="X", project_esg_score=0)
    ProjectCreate(name="X", project_esg_score=100)


@pytest.mark.unit
def test_gcf_priority_themes_dedupe() -> None:
    from app.modules.projects.schemas import ProjectCreate

    p = ProjectCreate(
        name="X",
        gcf_priority_themes=["adaptation", "adaptation", "eau"],
    )
    assert p.gcf_priority_themes == ["adaptation", "eau"]


@pytest.mark.unit
def test_vulnerable_populations_dedupe() -> None:
    from app.modules.projects.schemas import ProjectCreate

    p = ProjectCreate(
        name="X",
        vulnerable_populations=["femmes", "jeunes", "femmes"],
    )
    assert p.vulnerable_populations == ["femmes", "jeunes"]


@pytest.mark.unit
def test_project_update_supports_new_fields() -> None:
    from app.modules.projects.schemas import ProjectUpdate

    u = ProjectUpdate(
        taxonomie_verte_uemoa_aligned=False,
        gcf_priority_themes=["énergie"],
        project_esg_score=55,
    )
    assert u.taxonomie_verte_uemoa_aligned is False
    assert u.gcf_priority_themes == ["énergie"]
    assert u.project_esg_score == 55
