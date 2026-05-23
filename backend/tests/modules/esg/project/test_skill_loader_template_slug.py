"""[bug F047 US4] — `_slug_matches_page` doit traiter les gabarits `[id]`.

Avant ce patch, `_specificity_score` comparait `page_slug` strictement à la
liste `activation_rules.page_slugs`. La déclaration `"/profile/projects/[id]/esg"`
ne matchait jamais l'URL réelle `/profile/projects/abc-123` (ou même
`/profile/projects/abc-123/esg`), ce qui empêchait le skill F23
`skill_project_esg_assessment` de se charger sur la fiche projet.

Symptôme observé en live (BDD `tool_call_logs`) : sur la fiche projet,
le LLM tombait sur `skill_score_gcf` (procédure « 1) Demander la nature... »)
au lieu de `skill_project_esg_assessment` (procédure « TU DOIS appeler
create_project_esg_assessment AVANT toute autre action »).
"""

from __future__ import annotations

import pytest

from app.graph.skill_loader import _slug_matches_page, _specificity_score


@pytest.mark.unit
class TestSlugMatchesPage:
    @pytest.mark.parametrize(
        "pattern,page,expected",
        [
            # Match strict (rétro-compat sans gabarit).
            ("/esg", "/esg", True),
            ("/esg", "/financing", False),
            # Gabarit [id] → un segment quelconque.
            (
                "/profile/projects/[id]/esg",
                "/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36/esg",
                True,
            ),
            (
                "/profile/projects/[id]",
                "/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36",
                True,
            ),
            # Trailing slash toléré.
            (
                "/profile/projects/[id]",
                "/profile/projects/abc-123/",
                True,
            ),
            # Le gabarit ne doit pas matcher la racine ni un mauvais suffixe.
            ("/profile/projects/[id]", "/profile/projects", False),
            (
                "/profile/projects/[id]",
                "/profile/projects/abc-123/esg",
                False,
            ),
            # Plusieurs segments dans [id] interdits.
            (
                "/profile/projects/[id]",
                "/profile/projects/a/b",
                False,
            ),
            # Placeholder personnalisé `[project_id]` aussi accepté.
            (
                "/profile/projects/[project_id]/esg",
                "/profile/projects/abc-123/esg",
                True,
            ),
        ],
    )
    def test_slug_match(self, pattern: str, page: str, expected: bool):
        assert _slug_matches_page(pattern, page) is expected


@pytest.mark.unit
class TestSpecificityScoreOnProjectPage:
    """`_specificity_score` doit attribuer le bonus page_slug même quand
    l'URL contient un UUID, grâce au matching gabarit `[id]` → regex.
    """

    def _fake_skill(self, page_slugs: list[str], intent_keywords: list[str]):
        class _Skill:
            activation_rules = {
                "page_slugs": page_slugs,
                "intent_keywords": intent_keywords,
            }

        return _Skill()

    def test_uuid_page_matches_template_slug(self):
        skill = self._fake_skill(
            page_slugs=["/profile/projects/[id]"],
            intent_keywords=["IFC PS"],
        )
        ctx = {
            "page_slug": "/profile/projects/2fd64c66-3aa4-4de7-b9eb-f47d50d03e36",
            "intent": "Évalue mon projet contre IFC PS",
        }
        # Score attendu : 1.0 (page) + 0.5 (intent keyword) = 1.5
        assert _specificity_score(skill, ctx) == pytest.approx(1.5)

    def test_project_esg_beats_score_gcf_on_project_page(self):
        """Sur fiche projet, `skill_project_esg_assessment` (1.5) doit
        l'emporter sur `skill_score_gcf` (0.5 sur intent seul).
        """
        f23 = self._fake_skill(
            page_slugs=["/profile/projects/[id]/esg", "/profile/projects/[id]"],
            intent_keywords=["IFC PS", "GCF ESS", "BOAD ESS"],
        )
        gcf = self._fake_skill(
            page_slugs=["/financing", "/applications"],
            intent_keywords=["GCF", "score"],
        )
        ctx = {
            "page_slug": "/profile/projects/abc-uuid-here",
            "intent": "Évalue mon projet contre IFC PS",
        }
        assert _specificity_score(f23, ctx) > _specificity_score(gcf, ctx), (
            "skill_project_esg_assessment doit dominer sur la fiche projet."
        )
