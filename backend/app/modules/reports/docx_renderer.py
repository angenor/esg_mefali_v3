"""Generation de rapports ESG au format Word (.docx) via python-docx.

Remplace l'approche WeasyPrint (HTML -> PDF) qui requiert des libs natives
lourdes (Pango/Cairo/GTK) difficiles a deployer. python-docx est pur Python
et n'a aucune dependance systeme.

Les graphiques sont insérés en PNG (rendu matplotlib) car .docx ne supporte
pas SVG inline de maniere fiable.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from app.models.esg import ESGAssessment
from app.models.user import User
from app.modules.reports.charts import (
    generate_bar_chart_svg,  # noqa: F401 — keep import compat
    generate_benchmark_chart_svg,  # noqa: F401
    generate_radar_chart_svg,  # noqa: F401
)

logger = logging.getLogger(__name__)


# Couleurs du theme ESG Mefali (RGB)
COLOR_HEADER = RGBColor(0x1E, 0x40, 0xAF)  # blue-800
COLOR_PILLAR_E = RGBColor(0x22, 0xC5, 0x5E)  # green-500
COLOR_PILLAR_S = RGBColor(0x3B, 0x82, 0xF6)  # blue-500
COLOR_PILLAR_G = RGBColor(0xA8, 0x55, 0xF7)  # purple-500
COLOR_OVERALL = RGBColor(0xF5, 0x9E, 0x0B)  # amber-500
COLOR_MUTED = RGBColor(0x64, 0x74, 0x8B)  # slate-500

PILLAR_LABELS = {
    "environment": "Environnement",
    "social": "Social",
    "governance": "Gouvernance",
}
PILLAR_COLORS = {
    "environment": COLOR_PILLAR_E,
    "social": COLOR_PILLAR_S,
    "governance": COLOR_PILLAR_G,
}


# ─── Helpers graphiques (PNG bytes pour insertion dans .docx) ────────


def _radar_chart_png(scores: dict[str, float]) -> bytes:
    """Radar chart E/S/G en PNG bytes (200 DPI, fond transparent)."""
    labels = ["Environnement", "Social", "Gouvernance"]
    values = [
        scores.get("environment", 0),
        scores.get("social", 0),
        scores.get("governance", 0),
    ]
    # Boucler pour fermer le polygone
    values_closed = values + [values[0]]
    angles = [n / 3 * 2 * 3.14159265 for n in range(3)] + [0]

    fig, ax = plt.subplots(
        figsize=(5, 5), subplot_kw=dict(polar=True), dpi=120
    )
    ax.plot(angles, values_closed, color="#1e40af", linewidth=2)
    ax.fill(angles, values_closed, color="#3b82f6", alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_title("Performance ESG par pilier", fontsize=13, pad=20)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _bar_chart_png(criteria: list[dict], pillar_label: str) -> bytes:
    """Bar chart des criteres d'un pilier en PNG bytes."""
    if not criteria:
        return b""
    codes = [c.get("code", "?") for c in criteria]
    scores = [c.get("score", 0) for c in criteria]
    fig, ax = plt.subplots(figsize=(6, 3), dpi=120)
    bars = ax.bar(codes, scores, color="#3b82f6")
    ax.set_ylim(0, 10)
    ax.set_ylabel("Score / 10", fontsize=10)
    ax.set_title(f"Pilier {pillar_label} — scores par critere", fontsize=12)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.3)
    for bar, score in zip(bars, scores, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2, score + 0.2,
            f"{score}", ha="center", va="bottom", fontsize=9,
        )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ─── Rendu .docx ──────────────────────────────────────────────────────


def _add_title_block(
    doc: Document,
    company_name: str,
    sector_label: str,
    generation_date: str,
) -> None:
    """En-tete du rapport : titre + sous-titre + date."""
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Rapport d'Evaluation ESG")
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = COLOR_HEADER

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(f"{company_name} — {sector_label}")
    run.font.size = Pt(14)
    run.font.color.rgb = COLOR_MUTED

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_p.add_run(f"Genere le {generation_date}")
    run.font.size = Pt(10)
    run.font.italic = True
    run.font.color.rgb = COLOR_MUTED


def _add_scores_table(
    doc: Document,
    overall: float,
    environment: float,
    social: float,
    governance: float,
) -> None:
    """Tableau synthese des 4 scores (global + 3 piliers)."""
    doc.add_heading("Scores globaux", level=1)
    table = doc.add_table(rows=2, cols=4)
    table.style = "Light Grid Accent 1"
    headers = ["Score global", "Environnement", "Social", "Gouvernance"]
    values = [overall, environment, social, governance]
    colors = [COLOR_OVERALL, COLOR_PILLAR_E, COLOR_PILLAR_S, COLOR_PILLAR_G]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.bold = True
        run.font.size = Pt(10)
    for i, (v, color) in enumerate(zip(values, colors, strict=False)):
        cell = table.rows[1].cells[i]
        cell.text = ""
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"{v:.1f} / 100")
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = color


def _add_executive_summary(doc: Document, summary: str) -> None:
    """Section resume executif (texte LLM)."""
    doc.add_heading("Resume executif", level=1)
    if not summary or not summary.strip():
        p = doc.add_paragraph()
        run = p.add_run("Aucun resume disponible.")
        run.font.italic = True
        return
    for paragraph in summary.split("\n\n"):
        para = paragraph.strip()
        if para:
            doc.add_paragraph(para)


def _add_pillar_section(
    doc: Document,
    pillar_key: str,
    pillar_label: str,
    score: float,
    criteria: list[dict],
) -> None:
    """Section detaillee pour un pilier : score + tableau criteres."""
    doc.add_heading(f"Pilier {pillar_label}", level=1)

    score_p = doc.add_paragraph()
    run = score_p.add_run(f"Score : {score:.1f} / 100")
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.color.rgb = PILLAR_COLORS.get(pillar_key, COLOR_HEADER)

    if not criteria:
        p = doc.add_paragraph()
        run = p.add_run("Aucun critere evalue pour ce pilier.")
        run.font.italic = True
        return

    # Graphique en barres
    try:
        png = _bar_chart_png(criteria, pillar_label)
        if png:
            doc.add_picture(io.BytesIO(png), width=Cm(15))
    except Exception:
        logger.debug("Bar chart pilier %s ignore (erreur matplotlib)",
                     pillar_key, exc_info=True)

    # Tableau des criteres
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light List Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(["Code", "Score", "Justification"]):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(h)
        run.font.bold = True
    for crit in criteria:
        row = table.add_row().cells
        row[0].text = str(crit.get("code", ""))
        row[1].text = f"{crit.get('score', 0)} / 10"
        row[2].text = str(crit.get("justification", "") or "")


def _add_sources_appendix(
    doc: Document, mobilized_sources: list[dict]
) -> None:
    """Annexe F01 : liste des sources mobilisees pendant la generation."""
    doc.add_page_break()
    doc.add_heading("Annexe — Sources et references (F01)", level=1)

    if not mobilized_sources:
        p = doc.add_paragraph()
        run = p.add_run(
            "Aucune source citee par l'agent durant cette generation."
        )
        run.font.italic = True
        return

    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(["Editeur", "Titre", "Annee", "URL"]):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(h)
        run.font.bold = True
        run.font.size = Pt(10)

    for src in mobilized_sources:
        row = table.add_row().cells
        row[0].text = str(src.get("publisher", "") or "")
        row[1].text = str(src.get("title", "") or "")
        row[2].text = str(src.get("year", "") or "")
        row[3].text = str(src.get("url", "") or "")


def render_esg_report_docx(
    *,
    output_path: Path,
    assessment: ESGAssessment,
    user: User,
    executive_summary: str,
    pillar_scores: dict[str, float],
    pillar_criteria: dict[str, list[dict]],
    sector_label: str,
    mobilized_sources: list[dict] | None = None,
) -> Path:
    """Generer le rapport ESG complet au format .docx.

    Args:
        output_path: Chemin de destination (sera ecrase si existe).
        assessment: Evaluation ESG (status=completed).
        user: User proprietaire (pour company_name).
        executive_summary: Texte du resume executif (LLM).
        pillar_scores: dict {environment, social, governance, [overall]}.
        pillar_criteria: dict {pillar -> list[{code, score, justification}]}.
        sector_label: Libelle secteur affichable.
        mobilized_sources: Sources F01 citees pendant la generation.

    Returns:
        Le chemin du fichier .docx genere.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # Marges
    for section in doc.sections:
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)

    generation_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    _add_title_block(
        doc,
        company_name=user.company_name or "Entreprise",
        sector_label=sector_label,
        generation_date=generation_date,
    )

    doc.add_paragraph()

    # Radar chart synthese
    try:
        png = _radar_chart_png(pillar_scores)
        doc.add_picture(io.BytesIO(png), width=Cm(12))
        last_para = doc.paragraphs[-1]
        last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        logger.debug("Radar chart ignore (erreur matplotlib)", exc_info=True)

    # Scores
    _add_scores_table(
        doc,
        overall=assessment.overall_score or 0,
        environment=pillar_scores.get("environment", 0),
        social=pillar_scores.get("social", 0),
        governance=pillar_scores.get("governance", 0),
    )

    # Resume executif
    _add_executive_summary(doc, executive_summary)

    # Sections par pilier
    for key in ("environment", "social", "governance"):
        _add_pillar_section(
            doc,
            pillar_key=key,
            pillar_label=PILLAR_LABELS[key],
            score=pillar_scores.get(key, 0),
            criteria=pillar_criteria.get(key) or [],
        )

    # Forces / Lacunes
    if assessment.strengths:
        doc.add_heading("Points forts identifies", level=1)
        for s in assessment.strengths:
            doc.add_paragraph(str(s), style="List Bullet")
    if assessment.gaps:
        doc.add_heading("Lacunes a combler", level=1)
        for g in assessment.gaps:
            doc.add_paragraph(str(g), style="List Bullet")
    if assessment.recommendations:
        doc.add_heading("Recommandations", level=1)
        for r in assessment.recommendations:
            text = r.get("description", str(r)) if isinstance(r, dict) else str(r)
            doc.add_paragraph(text, style="List Bullet")

    # Annexe sources F01
    _add_sources_appendix(doc, mobilized_sources or [])

    doc.save(str(output_path))
    return output_path
