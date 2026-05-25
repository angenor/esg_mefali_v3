"""F05 — Rendu HTML/PDF du rapport ESG entreprise.

Remplace l'ancien `docx_renderer.py` (python-docx) par un pipeline Jinja2 +
WeasyPrint cohérent avec F047/F21. Le pipeline `html_to_pdf_bytes` gère le
fallback reportlab → PDF minimal pure-Python si WeasyPrint est indisponible.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.models.esg import ESGAssessment
from app.models.user import User
from app.modules.reports.pdf_pipeline import html_to_pdf_bytes

logger = logging.getLogger(__name__)


TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "_esg_company_report.html"


_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
_BULLET_PATTERN = re.compile(r"^[-*]\s+(.+)$")


def _markdown_to_paragraphs(summary: str) -> list[dict[str, str]]:
    """Convertit le résumé exécutif (markdown brut LLM) en blocs Jinja-friendly.

    Stratégie :
    - retire les titres ``# ...`` redondants (le template fournit déjà la H2) ;
    - convertit ``- foo`` en ``{"kind": "bullet", "text": "foo"}`` ;
    - laisse les paragraphes en clair, avec gras/italique Markdown convertis
      en HTML (``<strong>``/``<em>``).
    """
    if not summary or not summary.strip():
        return []

    blocks: list[dict[str, str]] = []
    for raw in summary.split("\n\n"):
        para = raw.strip()
        if not para:
            continue
        if _HEADING_PATTERN.match(para):
            continue
        bullet = _BULLET_PATTERN.match(para)
        if bullet:
            text = bullet.group(1)
            text = _BOLD_PATTERN.sub(r"<strong>\1</strong>", text)
            text = _ITALIC_PATTERN.sub(r"<em>\1</em>", text)
            blocks.append({"kind": "bullet", "text": text})
            continue
        text = _BOLD_PATTERN.sub(r"<strong>\1</strong>", para)
        text = _ITALIC_PATTERN.sub(r"<em>\1</em>", text)
        blocks.append({"kind": "p", "text": text})
    return blocks


def _build_context(
    *,
    assessment: ESGAssessment,
    user: User,
    executive_summary: str,
    pillar_scores: dict[str, float],
    pillar_criteria: dict[str, list[dict[str, Any]]],
    sector_label: str,
    mobilized_sources: list[dict[str, Any]] | None,
    radar_chart_svg: str | None = None,
    pillar_bar_charts: dict[str, str] | None = None,
    benchmark_chart_svg: str | None = None,
    benchmark_position: str | None = None,
    benchmark_position_label: str | None = None,
) -> dict[str, Any]:
    return {
        "company_name": user.company_name or "Entreprise",
        "sector_label": sector_label,
        "overall_score": float(assessment.overall_score or 0),
        "environment_score": float(pillar_scores.get("environment", 0)),
        "social_score": float(pillar_scores.get("social", 0)),
        "governance_score": float(pillar_scores.get("governance", 0)),
        "pillar_scores": {
            "environment": float(pillar_scores.get("environment", 0)),
            "social": float(pillar_scores.get("social", 0)),
            "governance": float(pillar_scores.get("governance", 0)),
        },
        "executive_summary_paragraphs": _markdown_to_paragraphs(executive_summary),
        "pillar_criteria": pillar_criteria or {
            "environment": [], "social": [], "governance": [],
        },
        "strengths": assessment.strengths or [],
        "gaps": assessment.gaps or [],
        "recommendations": assessment.recommendations or [],
        "radar_chart_svg": radar_chart_svg or "",
        "pillar_bar_charts": pillar_bar_charts or {},
        "benchmark_chart_svg": benchmark_chart_svg or "",
        "benchmark_position": benchmark_position,
        "benchmark_position_label": benchmark_position_label,
        "mobilized_sources": mobilized_sources or [],
        "generation_date": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
    }


def render_esg_company_html(context: dict[str, Any]) -> str:
    """Rendre le template Jinja2 du rapport ESG entreprise en HTML."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(**context)


def render_esg_report_pdf(
    *,
    output_path: Path,
    assessment: ESGAssessment,
    user: User,
    executive_summary: str,
    pillar_scores: dict[str, float],
    pillar_criteria: dict[str, list[dict[str, Any]]],
    sector_label: str,
    mobilized_sources: list[dict[str, Any]] | None = None,
    radar_chart_svg: str | None = None,
    pillar_bar_charts: dict[str, str] | None = None,
    benchmark_chart_svg: str | None = None,
    benchmark_position: str | None = None,
    benchmark_position_label: str | None = None,
) -> Path:
    """Générer le rapport ESG entreprise PDF.

    Pipeline : Jinja2 HTML → WeasyPrint (avec fallback reportlab → PDF minimal).
    Le HTML reste exempt d'éléments lourds non rendus par les fallbacks
    (texte structuré H1/H2/H3 + paragraphes) et embarque les chiffres en
    clair pour la lisibilité du PDF de secours.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    context = _build_context(
        assessment=assessment,
        user=user,
        executive_summary=executive_summary,
        pillar_scores=pillar_scores,
        pillar_criteria=pillar_criteria,
        sector_label=sector_label,
        mobilized_sources=mobilized_sources,
        radar_chart_svg=radar_chart_svg,
        pillar_bar_charts=pillar_bar_charts,
        benchmark_chart_svg=benchmark_chart_svg,
        benchmark_position=benchmark_position,
        benchmark_position_label=benchmark_position_label,
    )
    html = render_esg_company_html(context)
    pdf_bytes = html_to_pdf_bytes(html)
    output_path.write_bytes(pdf_bytes)
    return output_path


__all__ = [
    "render_esg_company_html",
    "render_esg_report_pdf",
    "TEMPLATES_DIR",
    "TEMPLATE_NAME",
]
