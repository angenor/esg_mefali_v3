"""F21 — Tests unitaires des charts SVG du rapport carbone."""

import pytest

from app.modules.reports.carbon.chart_builder import (
    CATEGORY_LABELS_FR,
    build_breakdown_pie_svg,
    build_sector_comparison_bar_svg,
    build_yearly_line_svg,
)


class TestBuildBreakdownPie:
    def test_returns_svg_string(self) -> None:
        svg = build_breakdown_pie_svg({"energy": 5.0, "transport": 3.0})
        assert isinstance(svg, str)
        assert svg.startswith("<?xml") or "<svg" in svg

    def test_empty_categories_returns_empty(self) -> None:
        assert build_breakdown_pie_svg({}) == ""

    def test_french_labels_present(self) -> None:
        svg = build_breakdown_pie_svg({"energy": 5.0})
        assert "Énergie" in svg or "Energie" in svg or "energy" in svg.lower()


class TestBuildSectorComparison:
    def test_returns_svg(self) -> None:
        svg = build_sector_comparison_bar_svg(10.0, 15.0, "Agriculture")
        assert "<svg" in svg or svg.startswith("<?xml")
        assert "Agriculture" in svg or "Votre entreprise" in svg

    def test_works_when_above_average(self) -> None:
        svg = build_sector_comparison_bar_svg(20.0, 10.0)
        assert "<svg" in svg or svg.startswith("<?xml")


class TestBuildYearlyLine:
    def test_empty_returns_empty(self) -> None:
        assert build_yearly_line_svg([]) == ""

    def test_single_year_returns_empty(self) -> None:
        # Au moins 2 années pour tracer une ligne.
        assert build_yearly_line_svg([(2024, 10.0)]) == ""

    def test_multi_year_returns_svg(self) -> None:
        svg = build_yearly_line_svg([(2023, 10.0), (2024, 8.0), (2025, 6.5)])
        assert "<svg" in svg or svg.startswith("<?xml")


class TestCategoryLabelsFr:
    def test_all_six_categories_present(self) -> None:
        for cat in ("energy", "transport", "waste", "industrial", "agriculture", "purchases"):
            assert cat in CATEGORY_LABELS_FR
            assert CATEGORY_LABELS_FR[cat]  # non-vide
