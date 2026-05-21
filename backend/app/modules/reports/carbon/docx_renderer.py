"""Génération du rapport carbone au format Word (.docx).

Remplace WeasyPrint pour éviter les dépendances natives Pango/Cairo
(cohérence avec docx_renderer ESG).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

logger = logging.getLogger(__name__)


COLOR_HEADER = RGBColor(0x14, 0x53, 0x2D)  # green-800
COLOR_ACCENT = RGBColor(0x22, 0xC5, 0x5E)  # green-500
COLOR_MUTED = RGBColor(0x64, 0x74, 0x8B)
COLOR_WARNING = RGBColor(0xDC, 0x26, 0x26)


def _breakdown_pie_png(categories: dict[str, float]) -> bytes:
    """Camembert PNG des émissions par catégorie."""
    if not categories:
        return b""
    labels = list(categories.keys())
    values = list(categories.values())
    fig, ax = plt.subplots(figsize=(5, 4), dpi=120)
    colors = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ef4444", "#14b8a6"]
    ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        colors=colors[: len(values)], startangle=90,
        textprops={"fontsize": 9},
    )
    ax.set_title("Répartition des émissions par catégorie", fontsize=12)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _add_title_block(doc: Document, company: str, year: int, gen_date: str) -> None:
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("Rapport Empreinte Carbone")
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = COLOR_HEADER

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run(company)
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = COLOR_HEADER

    year_p = doc.add_paragraph()
    year_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = year_p.add_run(f"Exercice {year}")
    run.font.size = Pt(12)
    run.font.color.rgb = COLOR_MUTED

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p.paragraph_format.space_after = Pt(12)
    run = date_p.add_run(f"Généré le {gen_date}")
    run.font.size = Pt(10)
    run.font.italic = True
    run.font.color.rgb = COLOR_MUTED


def _add_total_kpi(doc: Document, total: float, scope1: float, scope2: float, scope3: float) -> None:
    doc.add_heading("Synthèse des émissions", level=1)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"{total:.2f}")
    run.font.size = Pt(36)
    run.font.bold = True
    run.font.color.rgb = COLOR_ACCENT
    run2 = p.add_run(" tCO₂e / an")
    run2.font.size = Pt(14)
    run2.font.color.rgb = COLOR_MUTED

    if scope1 + scope2 + scope3 > 0:
        table = doc.add_table(rows=2, cols=3)
        table.style = "Light Grid Accent 1"
        headers = ["Scope 1 (directes)", "Scope 2 (énergie)", "Scope 3 (indirectes)"]
        values = [scope1, scope2, scope3]
        for i, h in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(h)
            run.font.bold = True
            run.font.size = Pt(10)
        for i, v in enumerate(values):
            cell = table.rows[1].cells[i]
            cell.text = ""
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(f"{v:.2f} tCO₂e")
            run.font.size = Pt(13)
            run.font.bold = True
        doc.add_paragraph()


def _add_breakdown(doc: Document, categories_table: list[dict], categories_raw: dict) -> None:
    doc.add_heading("Répartition par catégorie", level=1)

    # Camembert centré
    try:
        png = _breakdown_pie_png(categories_raw)
        if png:
            doc.add_picture(io.BytesIO(png), width=Cm(12))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        logger.debug("Camembert carbone ignoré", exc_info=True)

    # Tableau détaillé
    if categories_table:
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light List Accent 1"
        hdr = table.rows[0].cells
        for i, h in enumerate(["Catégorie", "Émissions (tCO₂e)", "Part"]):
            hdr[i].text = ""
            run = hdr[i].paragraphs[0].add_run(h)
            run.font.bold = True
        for row in categories_table:
            cells = table.add_row().cells
            cells[0].text = str(row.get("label", "—"))
            cells[1].text = f"{row.get('value', 0):.3f}"
            cells[2].text = f"{row.get('share', 0):.1f} %"
        doc.add_paragraph()


def _add_equivalences(doc: Document, equivalences: list[dict]) -> None:
    if not equivalences:
        return
    doc.add_heading("Équivalences parlantes", level=1)
    intro = doc.add_paragraph()
    run = intro.add_run(
        "Pour mieux visualiser l'impact, voici l'équivalent de vos "
        "émissions annuelles :"
    )
    run.font.italic = True
    run.font.color.rgb = COLOR_MUTED
    intro.paragraph_format.space_after = Pt(8)

    for eq in equivalences:
        label = eq.get("label") or eq.get("fallback_label") or "—"
        value = eq.get("value")
        unit = eq.get("unit") or ""
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(f"{value:,.0f} {unit}".replace(",", " ") if isinstance(value, (int, float)) else str(value))
        run.font.bold = True
        run = p.add_run(f" — {label}")
        run.font.size = Pt(11)


def _add_reduction_plan(doc: Document, actions: list[dict]) -> None:
    if not actions:
        return
    doc.add_heading("Plan de réduction", level=1)
    for a in actions:
        title = a.get("title", "Action")
        desc = a.get("description", "")
        reduction = a.get("estimated_reduction_tco2e")
        cost = a.get("cost_estimate_fcfa")
        timeline = a.get("timeline", "")
        unsourced = a.get("unsourced", True)

        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(str(title))
        run.font.bold = True
        run.font.size = Pt(11)
        if desc:
            run = p.add_run(f" — {desc}")
            run.font.size = Pt(11)
        meta = []
        if reduction is not None:
            meta.append(f"−{reduction} tCO₂e")
        if cost:
            meta.append(f"{cost:,} FCFA".replace(",", " "))
        if timeline:
            meta.append(f"horizon : {timeline}")
        if meta:
            run = p.add_run(f"  ({', '.join(meta)})")
            run.font.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = COLOR_MUTED
        if unsourced:
            run = p.add_run("  · non sourcée")
            run.font.italic = True
            run.font.size = Pt(8)
            run.font.color.rgb = COLOR_WARNING


def _add_sources(doc: Document, sources: list[dict]) -> None:
    doc.add_page_break()
    doc.add_heading("Annexe — Sources et facteurs d'émission", level=1)

    if not sources:
        p = doc.add_paragraph()
        run = p.add_run(
            "Aucune source explicitement citée. Les facteurs proviennent "
            "des bases standards (ADEME Base Carbone v23, IPCC AR6 WG3, "
            "IEA Africa Energy Outlook)."
        )
        run.font.italic = True
        run.font.color.rgb = COLOR_MUTED
        return

    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(["#", "Éditeur", "Titre", "Référence"]):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(h)
        run.font.bold = True
        run.font.size = Pt(10)
    for src in sources:
        cells = table.add_row().cells
        cells[0].text = str(src.get("index", ""))
        cells[1].text = str(src.get("publisher") or "")
        cells[2].text = str(src.get("title") or "")
        url = src.get("url") or src.get("date_publi") or ""
        cells[3].text = str(url)


def _add_methodology(doc: Document) -> None:
    doc.add_heading("Méthodologie", level=1)
    para = doc.add_paragraph()
    para.paragraph_format.line_spacing = 1.4
    run = para.add_run(
        "Le présent bilan carbone est calculé selon la méthode du GHG "
        "Protocol (scopes 1, 2 et 3), adaptée au contexte des PME "
        "africaines (zones UEMOA/CEDEAO). Les facteurs d'émission "
        "proviennent de bases reconnues (ADEME Base Carbone, IPCC AR6, "
        "IEA Africa Energy Outlook), priorisés par pays (Côte d'Ivoire, "
        "Sénégal…) puis fallback global lorsque le pays n'est pas couvert."
    )
    run.font.size = Pt(11)

    para = doc.add_paragraph()
    para.paragraph_format.line_spacing = 1.4
    run = para.add_run(
        "Les équivalences sont calculées sur la base d'hypothèses "
        "standards (1 vol Paris-Dakar ≈ 1,2 tCO₂e, 1 an de conduite "
        "moyenne ≈ 2,4 tCO₂e). Le plan de réduction est généré par "
        "l'agent ESG Mefali à partir des leviers les plus impactants "
        "identifiés dans le bilan."
    )
    run.font.size = Pt(11)


def render_carbon_report_docx(
    *, output_path: Path, context: dict[str, Any]
) -> Path:
    """Générer le rapport carbone au format .docx à partir du contexte."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    for section in doc.sections:
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)

    _add_title_block(
        doc,
        company=context.get("company_name") or "—",
        year=context.get("assessment_year") or 0,
        gen_date=context.get("generation_date") or "",
    )

    _add_total_kpi(
        doc,
        total=float(context.get("total_tco2e") or 0),
        scope1=float(context.get("scope1") or 0),
        scope2=float(context.get("scope2") or 0),
        scope3=float(context.get("scope3") or 0),
    )

    # Rebuild raw categories dict for the pie chart
    raw_cats = {
        row["label"]: row["value"]
        for row in context.get("categories_table") or []
    }
    _add_breakdown(doc, context.get("categories_table") or [], raw_cats)
    _add_equivalences(doc, context.get("equivalences") or [])
    _add_reduction_plan(doc, context.get("reduction_actions") or [])
    _add_methodology(doc)
    _add_sources(doc, context.get("numbered_sources") or [])

    doc.save(str(output_path))
    return output_path
