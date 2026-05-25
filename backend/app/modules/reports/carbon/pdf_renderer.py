"""F21 — Rendu HTML/PDF du rapport carbone (Jinja2 + pipeline partagé)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.lib.date_fr import format_date_fr
from app.modules.reports.pdf_pipeline import html_to_pdf_bytes


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
    """Rendre le HTML puis générer le PDF via le pipeline partagé.

    Pipeline : WeasyPrint → fallback reportlab → PDF minimal pure-Python.
    """
    html_content = render_carbon_html(context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(html_to_pdf_bytes(html_content))


def render_carbon_report_pdf(*, output_path: Path, context: dict[str, Any]) -> Path:
    """Wrapper compatible avec l'ancienne signature ``render_carbon_report_docx``.

    Conserve l'API ``output_path=..., context=...`` pour minimiser le diff
    chez les callers ayant migré de .docx vers .pdf.
    """
    render_carbon_pdf(context, output_path)
    return output_path


__all__ = [
    "render_carbon_html",
    "render_carbon_pdf",
    "render_carbon_report_pdf",
    "TEMPLATES_DIR",
]
