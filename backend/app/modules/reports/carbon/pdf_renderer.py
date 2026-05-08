"""F21 — Rendu HTML/PDF du rapport carbone (Jinja2 + WeasyPrint)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.lib.date_fr import format_date_fr


TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_carbon_html(context: dict[str, Any]) -> str:
    """Rendre le template HTML du rapport carbone avec le contexte fourni.

    Le contexte doit inclure les 9 sections : ``company_name``,
    ``assessment_year``, ``generation_date``, ``total_tco2e``,
    ``intensity``, ``scope1/2/3``, ``breakdown_pie_svg``,
    ``categories_table``, ``sector_comparison_svg``, ``yearly_line_svg``,
    ``reduction_actions``, ``equivalences``, ``methodology_factors``,
    ``numbered_sources``, ``company_country``.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["format_date_fr"] = format_date_fr
    template = env.get_template("carbon_report.html")
    return template.render(**context)


def render_carbon_pdf(context: dict[str, Any], output_path: Path) -> None:
    """Rendre le template HTML puis convertir en PDF via WeasyPrint."""
    html_content = render_carbon_html(context)
    # Import lazy : WeasyPrint a des dépendances système lourdes.
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_content).write_pdf(str(output_path))


__all__ = ["render_carbon_html", "render_carbon_pdf", "TEMPLATES_DIR"]
