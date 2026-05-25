"""[DEPRECATED] Generation de rapports ESG au format Word (.docx).

Conservé pour rétro-compatibilité et tests legacy. La génération de
rapports passe désormais par :mod:`app.modules.reports.pdf_renderer`
(pipeline Jinja2 + WeasyPrint partagé avec F047/F21).

À supprimer dans une prochaine release une fois la confiance dans le
pipeline PDF acquise en production.
"""

from __future__ import annotations

import io
import logging
import re
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
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _bar_chart_png(criteria: list[dict], pillar_label: str) -> bytes:
    """Bar chart des critères d'un pilier en PNG bytes."""
    if not criteria:
        return b""
    codes = [c.get("code", "?") for c in criteria]
    scores = [c.get("score", 0) for c in criteria]
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=120)
    bars = ax.bar(codes, scores, color="#3b82f6", edgecolor="#1e40af", linewidth=0.5)
    ax.set_ylim(0, 10)
    ax.set_ylabel("Score / 10", fontsize=10)
    ax.set_title(f"Pilier {pillar_label} — Scores par critère", fontsize=12)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, score in zip(bars, scores, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2, score + 0.2,
            f"{score}", ha="center", va="bottom", fontsize=9, fontweight="bold",
        )
    fig.tight_layout()
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
    """En-tête du rapport : titre + sous-titre + date."""
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(4)
    run = title.add_run("Rapport d'Évaluation ESG")
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = COLOR_HEADER

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(2)
    run = subtitle.add_run(f"{company_name}")
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = COLOR_HEADER

    sector_p = doc.add_paragraph()
    sector_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sector_p.paragraph_format.space_after = Pt(2)
    run = sector_p.add_run(f"Secteur : {sector_label}")
    run.font.size = Pt(12)
    run.font.color.rgb = COLOR_MUTED

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p.paragraph_format.space_after = Pt(12)
    run = date_p.add_run(f"Généré le {generation_date}")
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
    """Tableau synthèse des 4 scores (global + 3 piliers)."""
    doc.add_heading("Scores globaux", level=1)
    table = doc.add_table(rows=2, cols=4)
    table.style = "Light Grid Accent 1"
    table.autofit = True
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
        run.font.size = Pt(11)
    for i, (v, color) in enumerate(zip(values, colors, strict=False)):
        cell = table.rows[1].cells[i]
        cell.text = ""
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(f"{v:.1f}")
        run.font.size = Pt(20)
        run.font.bold = True
        run.font.color.rgb = color
        run2 = p.add_run(" / 100")
        run2.font.size = Pt(11)
        run2.font.color.rgb = COLOR_MUTED
    # Espace après le tableau
    doc.add_paragraph()


_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
_BULLET_PATTERN = re.compile(r"^[-*]\s+(.+)$")


def _add_markdown_paragraph(doc: Document, text: str, base_size: int = 11) -> None:
    """Ajouter un paragraphe en interprétant le markdown minimal **gras** *italique*.

    Bypass : le LLM retourne parfois du markdown brut (# titres, **gras**) ; on
    le rend proprement au lieu d'afficher les caractères de balisage.
    """
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.4

    # Tokeniser pour gérer **gras** et *italique* dans le même paragraphe.
    # Stratégie : scanner les **...** d'abord (priorité), puis les *...* dans
    # les fragments non encore marqués.
    cursor = 0
    for match in _BOLD_PATTERN.finditer(text):
        if match.start() > cursor:
            run = p.add_run(text[cursor:match.start()])
            run.font.size = Pt(base_size)
        run = p.add_run(match.group(1))
        run.font.bold = True
        run.font.size = Pt(base_size)
        cursor = match.end()
    if cursor < len(text):
        tail = text[cursor:]
        # Italique dans la queue
        sub_cursor = 0
        for m2 in _ITALIC_PATTERN.finditer(tail):
            if m2.start() > sub_cursor:
                run = p.add_run(tail[sub_cursor:m2.start()])
                run.font.size = Pt(base_size)
            run = p.add_run(m2.group(1))
            run.font.italic = True
            run.font.size = Pt(base_size)
            sub_cursor = m2.end()
        if sub_cursor < len(tail):
            run = p.add_run(tail[sub_cursor:])
            run.font.size = Pt(base_size)


def _add_executive_summary(doc: Document, summary: str) -> None:
    """Section résumé exécutif (texte LLM, markdown interprété)."""
    doc.add_heading("Résumé exécutif", level=1)
    if not summary or not summary.strip():
        p = doc.add_paragraph()
        run = p.add_run("Aucun résumé disponible.")
        run.font.italic = True
        run.font.color.rgb = COLOR_MUTED
        return

    for paragraph in summary.split("\n\n"):
        para = paragraph.strip()
        if not para:
            continue

        # Heading markdown -> on saute (le LLM répète parfois "# Résumé
        # Exécutif" alors qu'on a déjà le heading Word).
        if _HEADING_PATTERN.match(para):
            continue

        # Bullet markdown -> List Bullet style
        bullet = _BULLET_PATTERN.match(para)
        if bullet:
            p = doc.add_paragraph(style="List Bullet")
            # On parse encore le markdown inline dans l'item bullet
            text = bullet.group(1)
            cursor = 0
            for match in _BOLD_PATTERN.finditer(text):
                if match.start() > cursor:
                    p.add_run(text[cursor:match.start()])
                run = p.add_run(match.group(1))
                run.font.bold = True
                cursor = match.end()
            if cursor < len(text):
                p.add_run(text[cursor:])
            continue

        _add_markdown_paragraph(doc, para, base_size=11)


def _add_pillar_section(
    doc: Document,
    pillar_key: str,
    pillar_label: str,
    score: float,
    criteria: list[dict],
) -> None:
    """Section détaillée pour un pilier : score + tableau critères."""
    doc.add_heading(f"Pilier {pillar_label}", level=1)

    score_p = doc.add_paragraph()
    score_p.paragraph_format.space_after = Pt(8)
    run = score_p.add_run(f"Score : {score:.1f} / 100")
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.color.rgb = PILLAR_COLORS.get(pillar_key, COLOR_HEADER)

    if not criteria:
        p = doc.add_paragraph()
        run = p.add_run("Aucun critère évalué pour ce pilier.")
        run.font.italic = True
        run.font.color.rgb = COLOR_MUTED
        return

    # Graphique en barres centré
    try:
        png = _bar_chart_png(criteria, pillar_label)
        if png:
            doc.add_picture(io.BytesIO(png), width=Cm(15))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        logger.debug("Bar chart pilier %s ignoré (erreur matplotlib)",
                     pillar_key, exc_info=True)

    # Tableau des critères avec largeurs explicites
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light List Accent 1"
    table.autofit = False
    widths = (Cm(2.5), Cm(2.5), Cm(12))
    for i, w in enumerate(widths):
        table.columns[i].width = w

    hdr = table.rows[0].cells
    for i, h in enumerate(["Code", "Score", "Justification"]):
        hdr[i].text = ""
        hdr[i].width = widths[i]
        p = hdr[i].paragraphs[0]
        if i < 2:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.bold = True
        run.font.size = Pt(10)

    for crit in criteria:
        row = table.add_row().cells
        for i, w in enumerate(widths):
            row[i].width = w
        # Code
        p_code = row[0].paragraphs[0]
        p_code.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_code.add_run(str(crit.get("code", "")))
        run.font.bold = True
        # Score
        score_val = crit.get("score", 0)
        p_score = row[1].paragraphs[0]
        p_score.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_score.add_run(f"{score_val} / 10")
        run.font.bold = True
        # Couleur du score selon niveau
        if score_val >= 7:
            run.font.color.rgb = COLOR_PILLAR_E
        elif score_val >= 4:
            run.font.color.rgb = COLOR_OVERALL
        else:
            run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)  # red-600
        # Justification
        row[2].text = str(crit.get("justification", "") or "")

    # Espace après le tableau
    doc.add_paragraph()


def _add_sources_appendix(
    doc: Document, mobilized_sources: list[dict]
) -> None:
    """Annexe : liste des sources mobilisées pendant la génération (F01)."""
    doc.add_page_break()
    doc.add_heading("Annexe — Sources et références", level=1)

    intro = doc.add_paragraph()
    run = intro.add_run(
        "Conformément à l'invariant méthodologique de sourçage de la "
        "plateforme ESG Mefali (F01), l'ensemble des facteurs, seuils et "
        "référentiels mobilisés au cours de la génération du présent "
        "rapport est listé ci-dessous, par éditeur."
    )
    run.font.size = Pt(10)
    run.font.italic = True
    run.font.color.rgb = COLOR_MUTED
    intro.paragraph_format.space_after = Pt(12)

    if not mobilized_sources:
        p = doc.add_paragraph()
        run = p.add_run(
            "Aucune source n'a été explicitement citée par l'agent "
            "conversationnel durant cette génération. Les scores et "
            "constats reposent sur la grille ESG interne Mefali "
            "(référentiel propriétaire)."
        )
        run.font.italic = True
        run.font.color.rgb = COLOR_MUTED
        return

    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    table.autofit = False
    widths = (Cm(3), Cm(7), Cm(1.5), Cm(5.5))
    for i, w in enumerate(widths):
        table.columns[i].width = w

    hdr = table.rows[0].cells
    for i, h in enumerate(["Éditeur", "Titre", "Année", "Référence"]):
        hdr[i].text = ""
        hdr[i].width = widths[i]
        run = hdr[i].paragraphs[0].add_run(h)
        run.font.bold = True
        run.font.size = Pt(10)

    for src in mobilized_sources:
        row = table.add_row().cells
        for i, w in enumerate(widths):
            row[i].width = w
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

    # Forces / Lacunes / Recommandations (formatage propre des dicts)
    if assessment.strengths:
        doc.add_heading("Points forts identifiés", level=1)
        for s in assessment.strengths:
            _add_finding_bullet(doc, s)
    if assessment.gaps:
        doc.add_heading("Lacunes à combler", level=1)
        for g in assessment.gaps:
            _add_finding_bullet(doc, g)
    if assessment.recommendations:
        doc.add_heading("Recommandations stratégiques", level=1)
        for r in assessment.recommendations:
            _add_finding_bullet(doc, r)

    # Méthodologie (toujours présente, professionnalisme)
    _add_methodology_section(doc)

    # Annexe sources F01
    _add_sources_appendix(doc, mobilized_sources or [])

    # Mentions légales (dernière page)
    _add_legal_notice(doc)

    # Pied de page : pagination
    _add_footer_with_page_numbers(doc, user.company_name or "Entreprise")

    doc.save(str(output_path))
    return output_path


def _add_finding_bullet(doc: Document, item) -> None:
    """Rendre un point fort, une lacune ou une recommandation en bullet propre.

    Accepte soit une chaîne, soit un dict structuré
    ``{title, description, score, pillar, criteria_code, ...}``. Évite
    d'afficher le repr() Python brut.
    """
    if isinstance(item, str):
        doc.add_paragraph(item, style="List Bullet")
        return

    if not isinstance(item, dict):
        doc.add_paragraph(str(item), style="List Bullet")
        return

    # Composer un libellé lisible : Titre — description (score X/10)
    title = item.get("title") or item.get("name") or ""
    description = item.get("description") or ""
    score = item.get("score")
    code = item.get("criteria_code") or item.get("code")
    pillar = item.get("pillar") or ""

    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.3

    if title:
        run = p.add_run(str(title))
        run.font.bold = True
        run.font.size = Pt(11)
        if description:
            sep = p.add_run(" — ")
            sep.font.size = Pt(11)
    if description:
        run = p.add_run(str(description))
        run.font.size = Pt(11)

    # Metadata en fin de ligne (score / pilier / code) en italique muted
    meta_parts: list[str] = []
    if score is not None:
        meta_parts.append(f"score : {score}/10")
    if code:
        meta_parts.append(f"critère {code}")
    if pillar:
        pillar_fr = PILLAR_LABELS.get(str(pillar).lower(), str(pillar))
        meta_parts.append(f"pilier {pillar_fr}")
    if meta_parts:
        run = p.add_run(f"  ({', '.join(meta_parts)})")
        run.font.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = COLOR_MUTED


def _add_methodology_section(doc: Document) -> None:
    """Section méthodologie : explique la grille ESG et le scoring."""
    doc.add_heading("Méthodologie d'évaluation", level=1)

    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    run = p.add_run(
        "La présente évaluation repose sur la grille ESG Mefali, déclinée "
        "en 30 critères répartis sur les trois piliers — Environnement, "
        "Social et Gouvernance — adaptée au contexte des PME africaines "
        "francophones (zones UEMOA et CEDEAO)."
    )
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    run = p.add_run(
        "Chaque critère est noté sur une échelle de 0 à 10, puis pondéré "
        "selon le secteur d'activité de l'entreprise. Le score par pilier "
        "(/100) résulte d'une moyenne pondérée des critères du pilier ; "
        "le score global est la moyenne arithmétique des trois piliers."
    )
    run.font.size = Pt(11)

    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    run = p.add_run(
        "Les référentiels mobilisés incluent : Mefali (interne), GCF "
        "(Green Climate Fund), IFC Performance Standards, BOAD ESS, GRI "
        "2021, ainsi que la taxonomie verte UEMOA/BCEAO et les "
        "réglementations CEDEAO en vigueur. Les Objectifs de "
        "Développement Durable visés sont les ODD 8, 9, 10, 12, 13 et 17."
    )
    run.font.size = Pt(11)


def _add_legal_notice(doc: Document) -> None:
    """Mentions légales et avertissement (dernière page)."""
    doc.add_page_break()
    doc.add_heading("Avertissement et mentions légales", level=1)

    legal_points = [
        (
            "Confidentialité",
            "Le présent rapport contient des informations confidentielles "
            "relatives à l'entreprise évaluée. Sa diffusion est strictement "
            "réservée à son destinataire et aux tiers autorisés.",
        ),
        (
            "Portée de l'évaluation",
            "Les scores et constats reflètent les déclarations de "
            "l'entreprise au moment de l'évaluation. Ils ne constituent "
            "pas un audit certifié ni une attestation de conformité "
            "réglementaire. Une vérification par un tiers indépendant est "
            "recommandée avant toute utilisation à des fins de financement.",
        ),
        (
            "Limites méthodologiques",
            "La grille Mefali est un outil d'auto-diagnostic. Les "
            "pondérations sectorielles sont calibrées sur les standards "
            "internationaux mais peuvent différer des exigences "
            "spécifiques d'un bailleur de fonds donné.",
        ),
        (
            "Propriété intellectuelle",
            "© ESG Mefali — Tous droits réservés. La grille d'évaluation, "
            "les algorithmes de scoring et le contenu du présent rapport "
            "sont protégés par le droit d'auteur.",
        ),
    ]

    for title, body in legal_points:
        p = doc.add_paragraph()
        run = p.add_run(f"{title}. ")
        run.font.bold = True
        run.font.size = Pt(10)
        run2 = p.add_run(body)
        run2.font.size = Pt(10)
        run2.font.color.rgb = COLOR_MUTED
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.3


def _add_footer_with_page_numbers(doc: Document, company_name: str) -> None:
    """Ajoute un pied de page avec mention société + pagination Word."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    for section in doc.sections:
        footer = section.footer
        # Réinitialiser le pied de page existant
        para = footer.paragraphs[0]
        para.text = ""
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Texte gauche : nom société
        run_left = para.add_run(f"Rapport ESG — {company_name}    |    Page ")
        run_left.font.size = Pt(9)
        run_left.font.color.rgb = COLOR_MUTED

        # Champ Word PAGE (numéro de page courant)
        fld_char_begin = OxmlElement("w:fldChar")
        fld_char_begin.set(qn("w:fldCharType"), "begin")
        instr_text = OxmlElement("w:instrText")
        instr_text.set(qn("xml:space"), "preserve")
        instr_text.text = "PAGE"
        fld_char_end = OxmlElement("w:fldChar")
        fld_char_end.set(qn("w:fldCharType"), "end")

        run_page = para.add_run()
        run_page._r.append(fld_char_begin)
        run_page._r.append(instr_text)
        run_page._r.append(fld_char_end)
        run_page.font.size = Pt(9)
        run_page.font.color.rgb = COLOR_MUTED

        # Séparateur + total
        run_sep = para.add_run(" / ")
        run_sep.font.size = Pt(9)
        run_sep.font.color.rgb = COLOR_MUTED

        fld_total_begin = OxmlElement("w:fldChar")
        fld_total_begin.set(qn("w:fldCharType"), "begin")
        instr_total = OxmlElement("w:instrText")
        instr_total.set(qn("xml:space"), "preserve")
        instr_total.text = "NUMPAGES"
        fld_total_end = OxmlElement("w:fldChar")
        fld_total_end.set(qn("w:fldCharType"), "end")

        run_total = para.add_run()
        run_total._r.append(fld_total_begin)
        run_total._r.append(instr_total)
        run_total._r.append(fld_total_end)
        run_total.font.size = Pt(9)
        run_total.font.color.rgb = COLOR_MUTED
