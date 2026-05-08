"""F21 — Tests unitaires du rendu HTML/PDF du rapport carbone."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.reports.carbon.pdf_renderer import render_carbon_html


def _make_min_context() -> dict:
    return {
        "company_name": "PME Test SA",
        "company_country": "SN",
        "assessment_year": 2025,
        "generation_date": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        "total_tco2e": 12.5,
        "intensity": 0.45,
        "scope1": 5.0,
        "scope2": 4.0,
        "scope3": 3.5,
        "breakdown_pie_svg": "",
        "categories_table": [
            {"label": "Énergie", "value": 5.0, "share": 40.0},
            {"label": "Transport", "value": 7.5, "share": 60.0},
        ],
        "sector_comparison_svg": "",
        "yearly_line_svg": "",
        "reduction_actions": [
            {
                "title": "Optimiser la flotte",
                "description": "Renouveler 30 % du parc en hybride d'ici 2027.",
                "is_sourced": False,
                "source_index": None,
            },
        ],
        "equivalences": [
            {
                "label": "Vols Paris-NYC",
                "value": 12.5,
                "unit": "vols",
                "is_sourced": False,
                "source_index": None,
                "fallback_label": "Recommandation générale (non sourcée)",
            },
        ],
        "methodology_factors": [],
        "numbered_sources": [
            {
                "index": 1,
                "title": "ADEME Base Carbone v23",
                "publisher": "ADEME",
                "version": "23",
                "date_publi": "2024-01-15",
                "page": None,
                "section": "Mix électrique UEMOA",
                "url": "https://base-carbone.fr",
            },
        ],
    }


class TestRenderCarbonHtml:
    def test_renders_to_html_string(self) -> None:
        html = render_carbon_html(_make_min_context())
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_contains_nine_sections_markers(self) -> None:
        html = render_carbon_html(_make_min_context())
        # Section markers (numérotation 1..9 + libellés).
        assert "Synthèse" in html
        assert "Ventilation par catégorie" in html
        assert "Comparaison sectorielle" in html
        assert "Évolution multi-années" in html
        assert "Plan de réduction" in html
        assert "Équivalences pédagogiques" in html
        assert "Méthodologie" in html
        assert "Sources et références" in html

    def test_company_name_rendered(self) -> None:
        ctx = _make_min_context()
        ctx["company_name"] = "ACME Recyclage SARL"
        html = render_carbon_html(ctx)
        assert "ACME Recyclage" in html

    def test_unsourced_action_shows_fallback_label(self) -> None:
        html = render_carbon_html(_make_min_context())
        assert "Recommandation générale (non sourcée)" in html

    def test_numbered_sources_rendered(self) -> None:
        html = render_carbon_html(_make_min_context())
        assert "ADEME Base Carbone v23" in html
        assert "ADEME" in html

    def test_date_format_french(self) -> None:
        html = render_carbon_html(_make_min_context())
        # `15/01/2024` doit apparaître (filtre format_date_fr appliqué).
        assert "15/01/2024" in html

    def test_empty_categories_renders_empty_state(self) -> None:
        ctx = _make_min_context()
        ctx["categories_table"] = []
        html = render_carbon_html(ctx)
        assert isinstance(html, str)

    def test_empty_sources_renders_empty_message(self) -> None:
        ctx = _make_min_context()
        ctx["numbered_sources"] = []
        html = render_carbon_html(ctx)
        assert "Aucune source mobilisée" in html
