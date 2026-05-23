"""T061 [US4] — Conformity test : `esg_scoring_node` dispatche correctement
sans muter le pipeline F05 entreprise (mitigation R3).
"""

from __future__ import annotations

import pytest

from app.graph.nodes import _route_esg_target


@pytest.mark.parametrize(
    "current_page,expected",
    [
        ("/profile/projects/123e4567-e89b-12d3-a456-426614174000/esg", "project"),
        ("/profile/projects/abc/esg/", "project"),
        # Mise à jour bugfix mai 2026 : la fiche projet sans suffixe /esg
        # route AUSSI vers la branche projet F047 (sinon le LLM bascule sur
        # esg_scoring_node, qui retombe sur F05 entreprise et appelle
        # `finalize_esg_assessment` au lieu de `finalize_project_esg_assessment`).
        ("/profile/projects/abc", "project"),
        ("/profile/projects/abc/", "project"),
        ("/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36", "project"),
        # Hors fiche projet → branche F05 entreprise (inchangé).
        ("/esg", "company"),
        ("/profile", "company"),
        ("/profile/projects", "company"),
        ("/profile/projects/", "company"),
        ("/profile/projects/abc/esg/quelquechose", "company"),
        ("", "company"),
        (None, "company"),
    ],
)
def test_route_esg_target(current_page, expected):
    state = {"current_page": current_page}
    assert _route_esg_target(state) == expected


def test_route_esg_target_returns_company_for_random_state():
    """Garde-fou : par défaut on reste sur la branche F05 entreprise (R3)."""
    state = {"current_page": "/some/other/route", "messages": []}
    assert _route_esg_target(state) == "company"
