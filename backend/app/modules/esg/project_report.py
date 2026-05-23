"""F047 (US3) — Pipeline rapport ESIA-light PDF.

Réutilise le pipeline F06 (WeasyPrint + Jinja2 + matplotlib) avec un template
dédié `_esia_report.html` couvrant 7 sections + annexe sources F01.

Générée à la demande (D4 : pas de génération auto à la finalisation). Refuse
les évaluations `draft` (FR-019). Stocke le binaire sous
`/uploads/reports/esia/{account}/{project}/{assessment}_{timestamp}.pdf`.
"""

from __future__ import annotations

import base64
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator import Criterion
from app.models.project import Project
from app.models.referential import Referential
from app.models.source import Source
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)

logger = logging.getLogger(__name__)


TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "modules" / "reports" / "templates"
)
UPLOADS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "reports" / "esia"
)
TEMPLATE_NAME = "_esia_report.html"
TEMPLATE_VERSION = "esia_v1"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


class _Unprocessable(HTTPException):
    def __init__(self, detail: Any) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class _NotFound(HTTPException):
    def __init__(self, detail: str = "Évaluation introuvable") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _generate_donut_svg(covered: int, missing: int) -> str:
    """Génère un donut SVG (matplotlib) couverts vs manquants.

    Retourne une balise <img src="data:image/png;base64,..."> embeddable
    dans le HTML. Fallback texte si matplotlib indisponible.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        logger.warning("matplotlib indisponible — fallback texte pour le donut.")
        return f"<p>Critères couverts : {covered} — Manquants : {missing}</p>"

    total = max(1, covered + missing)
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    sizes = [covered, missing] if covered + missing > 0 else [1, 0]
    colors = ["#047857", "#fbbf24"]
    wedges, _ = ax.pie(
        sizes,
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 1.5},
    )
    ax.text(0, 0.05, f"{int(round(covered / total * 100))}%",
            ha="center", va="center", fontsize=22, fontweight="bold", color="#065f46")
    ax.text(0, -0.18, "couverts", ha="center", va="center", fontsize=10, color="#4b5563")
    ax.set_aspect("equal")
    ax.set_title("Critères couverts vs manquants", fontsize=11, color="#1f2937", pad=12)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", transparent=True)
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="Donut critères couverts vs manquants" />'


def _human_response_value(rt: str, val: dict[str, Any]) -> str:
    if not val:
        return "—"
    if rt in ("qcu", "qcm", "qcu_justification", "qcm_justification"):
        choice = val.get("choice") or ""
        choices = val.get("choices") or []
        base = choice if choice else ", ".join(str(c) for c in choices)
        if rt.endswith("justification") and val.get("justification"):
            return f"{base} — {val['justification']}"
        return base or "—"
    if rt == "numeric":
        return str(val.get("value", "—"))
    if rt == "money":
        amount = val.get("amount", "—")
        currency = val.get("currency", "")
        return f"{amount} {currency}".strip()
    if rt == "free_text":
        return val.get("text", "—")
    return str(val)


async def _load_finalized_assessment(
    db: AsyncSession, *, account_id: uuid.UUID, assessment_id: uuid.UUID,
) -> ProjectEsgAssessment:
    a = (
        await db.execute(
            select(ProjectEsgAssessment).where(
                ProjectEsgAssessment.id == assessment_id,
                ProjectEsgAssessment.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise _NotFound()
    if a.state != "finalized":
        raise _Unprocessable(
            {
                "error_code": "assessment_not_finalized",
                "message": (
                    "Le rapport ESIA-light ne peut être généré qu'à partir "
                    "d'une évaluation finalisée. Veuillez finaliser "
                    "l'évaluation au préalable."
                ),
            }
        )
    return a


async def _collect_context(
    db: AsyncSession, assessment: ProjectEsgAssessment, *, include_appendix_sources: bool,
) -> tuple[dict[str, Any], int]:
    """Construit le contexte Jinja2 (et retourne `sources_cited` count)."""
    project = (
        await db.execute(select(Project).where(Project.id == assessment.project_id))
    ).scalar_one_or_none()
    ref = (
        await db.execute(
            select(Referential).where(Referential.id == assessment.referential_id),
        )
    ).scalar_one_or_none()
    criteria_rows = (
        await db.execute(
            select(Criterion).where(
                Criterion.referential_id == assessment.referential_id,
                Criterion.applies_to_project.is_(True),
            )
        )
    ).scalars().all()
    by_id: dict[uuid.UUID, Criterion] = {c.id: c for c in criteria_rows}

    responses = (
        await db.execute(
            select(ProjectEsgCriterionResponse).where(
                ProjectEsgCriterionResponse.assessment_id == assessment.id,
            )
        )
    ).scalars().all()
    covered_ids = {r.criterion_id for r in responses}
    missing_required = [
        {"code": c.code, "label": c.label}
        for c in criteria_rows
        if c.is_required and c.id not in covered_ids
    ]

    src_ids = {r.source_id for r in responses if r.source_id is not None}
    sources_by_id: dict[uuid.UUID, Source] = {}
    if src_ids:
        src_rows = (
            await db.execute(select(Source).where(Source.id.in_(src_ids)))
        ).scalars().all()
        sources_by_id = {s.id: s for s in src_rows}

    covered_responses: list[dict[str, Any]] = []
    for r in responses:
        crit = by_id.get(r.criterion_id)
        if crit is None:
            continue
        src = sources_by_id.get(r.source_id) if r.source_id else None
        covered_responses.append({
            "code": crit.code,
            "label": crit.label,
            "value_human": _human_response_value(r.response_type, r.response_value),
            "source_title": src.title if src else None,
        })

    sources_data = [
        {
            "title": s.title,
            "publisher": s.publisher,
            "version": s.version,
            "date_publi": s.date_publi.isoformat() if s.date_publi else "",
            "page": getattr(s, "page", None),
            "section": s.section or "",
            "url": s.url,
            "verification_status": s.verification_status,
        }
        for s in sources_by_id.values()
    ]

    covered_count = len(covered_responses)
    missing_count = len(by_id) - covered_count

    overall = int(assessment.score or 0)
    niveau = (
        "performance solide" if overall >= 70
        else "performance intermédiaire" if overall >= 50
        else "performance encore fragile" if overall >= 30
        else "engagement initial"
    )
    executive_summary = (
        f"Le projet « {project.name if project else 'sans nom'} » affiche un score "
        f"ESG-projet de {overall}/100 contre le référentiel {ref.label if ref else '—'}, "
        f"traduisant une {niveau}. {covered_count} critère(s) ont été couvert(s) "
        f"et {missing_count} restent à documenter pour atteindre une couverture "
        f"complète."
    )

    ctx: dict[str, Any] = {
        "project_name": project.name if project else "",
        "project_description": getattr(project, "description", None),
        "project_country": getattr(project, "location_country", None),
        "project_region": getattr(project, "location_region", None),
        "project_maturity": getattr(project, "maturity", None),
        "project_objectives": list(getattr(project, "objective_env", []) or []),
        "referential_label": ref.label if ref else "—",
        "referential_version": str(getattr(ref, "version", "1.0") or "1.0"),
        "overall_score": overall,
        "covered_count": covered_count,
        "missing_count": missing_count,
        "coverage_rate": float(assessment.coverage_rate or 0),
        "pillar_scores": dict(assessment.pillar_scores or {}),
        "executive_summary": executive_summary,
        "covered_responses": covered_responses,
        "missing_required": missing_required,
        "donut_svg": _generate_donut_svg(covered_count, missing_count),
        "generation_date": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        "sources_data": sources_data,
        "include_appendix_sources": include_appendix_sources,
    }
    return ctx, len(sources_by_id)


def _render_html(ctx: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(**ctx)


def _convert_to_pdf(html: str) -> bytes:
    """HTML→PDF via WeasyPrint avec fallback PDF minimal si indisponible.

    Fallback (bugfix 2026-05-23) : reportlab + extraction texte structurée.
    Le strip HTML retire les tags ET le contenu de ``<style>``/``<script>``/
    ``<title>``, préserve les sauts de ligne implicites des balises de bloc,
    découpe en pages, et met en gras les lignes correspondant aux titres
    de sections F047 (1. Résumé exécutif, etc.) pour rester lisible.
    """
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        logger.warning("WeasyPrint indisponible — fallback PDF reportlab.")
        try:
            return _reportlab_fallback_pdf(html)
        except Exception:  # noqa: BLE001
            return _minimal_pdf_bytes(html)


def _html_to_structured_text(html: str) -> list[tuple[str, str]]:
    """Convertit l'HTML en suite de blocs ``(kind, text)`` exploitables.

    ``kind`` ∈ {``"h1"``, ``"h2"``, ``"h3"``, ``"p"``}. Garantit :
    - retrait du contenu de ``<style>``/``<script>``/``<title>``/
      ``<!--…-->`` (était la cause du PDF illisible) ;
    - préservation des sauts de bloc (h1, h2, h3, p, li, tr, div, br) ;
    - normalisation des espaces.
    """
    import re
    from html import unescape

    cleaned = re.sub(
        r"<(style|script|title)\b[^>]*>.*?</\1>", " ", html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)

    # Marquer les titres avant strip pour les retrouver après.
    cleaned = re.sub(r"<h1\b[^>]*>(.*?)</h1>", r"\nH1\1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<h2\b[^>]*>(.*?)</h2>", r"\nH2\1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<h3\b[^>]*>(.*?)</h3>", r"\nH3\1\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
    # Sauts de ligne implicites pour les balises de bloc.
    cleaned = re.sub(r"</?(p|li|tr|div|section|article|br|hr)\b[^>]*>", "\n", cleaned, flags=re.IGNORECASE)

    # Strip tous les autres tags.
    plain = re.sub(r"<[^>]+>", " ", cleaned)
    plain = unescape(plain)

    blocks: list[tuple[str, str]] = []
    for raw in plain.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line.startswith("H1"):
            blocks.append(("h1", line[len("H1"):].strip()))
        elif line.startswith("H2"):
            blocks.append(("h2", line[len("H2"):].strip()))
        elif line.startswith("H3"):
            blocks.append(("h3", line[len("H3"):].strip()))
        else:
            blocks.append(("p", line))
    return blocks


def _reportlab_fallback_pdf(html: str) -> bytes:
    """Génère un PDF multi-pages lisible quand WeasyPrint n'est pas dispo.

    Mise en page basique : titres H1/H2/H3 en gras (tailles 16/13/11),
    paragraphes en 10pt, gestion des sauts de page, marges A4.
    """
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.pdfbase.pdfmetrics import stringWidth  # type: ignore
    from reportlab.pdfgen import canvas  # type: ignore

    page_w, page_h = A4
    margin_x, margin_y = 50, 50
    usable_w = page_w - 2 * margin_x

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = page_h - margin_y

    def _new_page() -> float:
        c.showPage()
        return page_h - margin_y

    def _wrap(text: str, font: str, size: float) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for w in words:
            candidate = (current + " " + w).strip() if current else w
            if stringWidth(candidate, font, size) <= usable_w:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def _draw_block(text: str, font: str, size: float, leading: float,
                    space_before: float, y_pos: float) -> float:
        y_pos -= space_before
        c.setFont(font, size)
        for line in _wrap(text, font, size):
            if y_pos < margin_y + leading:
                y_pos = _new_page()
                c.setFont(font, size)
            c.drawString(margin_x, y_pos, line)
            y_pos -= leading
        return y_pos

    for kind, text in _html_to_structured_text(html):
        if kind == "h1":
            y = _draw_block(text, "Helvetica-Bold", 16, 20, 14, y)
        elif kind == "h2":
            y = _draw_block(text, "Helvetica-Bold", 13, 17, 12, y)
        elif kind == "h3":
            y = _draw_block(text, "Helvetica-Bold", 11, 14, 8, y)
        else:
            y = _draw_block(text, "Helvetica", 10, 13, 2, y)

    c.save()
    return buf.getvalue()


def _pdf_escape(text: str) -> str:
    """Échappe les caractères spéciaux pour une string PDF entre parenthèses."""
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _minimal_pdf_bytes(html: str) -> bytes:
    """Génère un PDF 1.4 multi-pages sans dépendance externe (bugfix 2026-05-23).

    Utilisé quand ni WeasyPrint ni reportlab ne sont disponibles. Produit
    un rapport structuré (titres H1/H2/H3 en gras + paragraphes wrap), avec
    plusieurs pages. Le contenu CSS de ``<style>`` est correctement filtré
    par :func:`_html_to_structured_text`.
    """
    blocks = _html_to_structured_text(html)

    # Wrap simple à 90 chars (approximation, sans mesure de glyph).
    MAX_LINE_CHARS = 90
    LINE_HEIGHT = 14
    PAGE_TOP = 800  # ~A4 height (842) - top margin (42)
    PAGE_BOTTOM = 50
    LEFT_MARGIN = 40

    def _wrap(text: str, width: int = MAX_LINE_CHARS) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for w in words:
            candidate = (current + " " + w).strip() if current else w
            if len(candidate) <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                # Mot trop long : tronque en morceaux.
                while len(w) > width:
                    lines.append(w[:width])
                    w = w[width:]
                current = w
        if current:
            lines.append(current)
        return lines

    # Construire la liste de pages (chacune = liste d'instructions Td/Tj).
    pages: list[list[tuple[str, str, str, int]]] = []
    current_page: list[tuple[str, str, str, int]] = []
    y = PAGE_TOP

    def _push_line(font: str, size: int, text: str, leading: int,
                   space_before: int) -> None:
        nonlocal y, current_page
        y_after = y - space_before
        if y_after < PAGE_BOTTOM:
            pages.append(current_page)
            current_page = []
            y = PAGE_TOP
            y_after = y - space_before
        # On stocke font, size, text et y_pos calculé.
        current_page.append((font, str(size), text, y_after))
        y = y_after - leading

    # Configurations par niveau (cohérent avec _reportlab_fallback_pdf).
    LEVEL_CONF = {
        "h1": ("F2", 16, 20, 14),
        "h2": ("F2", 13, 17, 12),
        "h3": ("F2", 11, 14, 8),
        "p":  ("F1", 10, 13, 2),
    }
    width_by_size = {16: 55, 13: 70, 11: 80, 10: MAX_LINE_CHARS}

    for kind, text in blocks:
        font, size, leading, space_before = LEVEL_CONF.get(kind, LEVEL_CONF["p"])
        wrap_w = width_by_size.get(size, MAX_LINE_CHARS)
        wrapped = _wrap(text, wrap_w)
        for i, line in enumerate(wrapped):
            sb = space_before if i == 0 else 0
            _push_line(font, size, line, leading, sb)

    if current_page:
        pages.append(current_page)

    if not pages:
        pages.append([("F1", "10", "Rapport ESIA-light — contenu indisponible.", PAGE_TOP)])

    # Construire les objets PDF.
    objects: list[bytes] = []

    def _add_obj(body: bytes) -> int:
        idx = len(objects) + 1
        objects.append(f"{idx} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
        return idx

    # Réserver les fonts globales (F1=Helvetica, F2=Helvetica-Bold).
    f1_idx = _add_obj(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    f2_idx = _add_obj(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )

    # Construire chaque page.
    page_obj_ids: list[int] = []
    for page_lines in pages:
        # Content stream pour cette page.
        stream_parts: list[bytes] = [b"BT\n"]
        for font, size, text, y_pos in page_lines:
            escaped = _pdf_escape(text).encode("latin-1", errors="replace")
            stream_parts.append(
                f"/{font} {size} Tf 1 0 0 1 {LEFT_MARGIN} {y_pos} Tm ".encode("ascii")
                + b"(" + escaped + b") Tj\n"
            )
        stream_parts.append(b"ET")
        content_stream = b"".join(stream_parts)
        content_idx = _add_obj(
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\n"
            b"stream\n" + content_stream + b"\nendstream"
        )
        page_obj_ids.append(content_idx)  # placeholder, on remplace ci-dessous

    # On a besoin de connaître Pages avant de créer les Page individuelles.
    # Construction en 2 passes : générer Page objects référençant un Pages
    # qui sera créé après, mais on connaît son numéro = len(objects)+1 après
    # avoir créé toutes les pages.
    # Approche plus simple : reconstruire en cascadant.

    # Reset objects (sauf fonts).
    objects = objects[:2]  # garde f1, f2

    # Créer les content streams + page objects.
    page_indices: list[int] = []
    content_indices: list[int] = []
    for page_lines in pages:
        stream_parts = [b"BT\n"]
        for font, size, text, y_pos in page_lines:
            escaped = _pdf_escape(text).encode("latin-1", errors="replace")
            stream_parts.append(
                f"/{font} {size} Tf 1 0 0 1 {LEFT_MARGIN} {y_pos} Tm ".encode("ascii")
                + b"(" + escaped + b") Tj\n"
            )
        stream_parts.append(b"ET")
        content_stream = b"".join(stream_parts)
        content_idx = _add_obj(
            b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\n"
            b"stream\n" + content_stream + b"\nendstream"
        )
        content_indices.append(content_idx)

    # Le Pages object sera ajouté en dernier — on connaît son index.
    pages_obj_idx = len(objects) + 1 + len(content_indices)  # placeholder
    # Plus simple : créer Pages d'abord avec un placeholder, puis Page objects,
    # puis remettre Pages à jour. On va plutôt construire dans le bon ordre
    # en sachant que Page.Parent référence Pages — mais PDF accepte des
    # forward references si elles existent (les /Kids référencent les Page
    # qui doivent exister avant le Pages object lui-même n'est pas trivial).
    # Stratégie : on calcule à l'avance les futures positions.

    # Position planifiée : objects actuels + 1 Pages + N Page objects + 1 Catalog.
    next_idx_pages_obj = len(objects) + 1
    next_idx_first_page = next_idx_pages_obj + 1
    # Ajouter le Pages object.
    page_refs = " ".join(
        f"{next_idx_first_page + i} 0 R" for i in range(len(content_indices))
    )
    pages_idx = _add_obj(
        f"<< /Type /Pages /Kids [{page_refs}] /Count {len(content_indices)} >>".encode("ascii")
    )
    # Ajouter les Page objects.
    for content_idx in content_indices:
        page_idx = _add_obj(
            (
                f"<< /Type /Page /Parent {pages_idx} 0 R "
                f"/MediaBox [0 0 595 842] /Contents {content_idx} 0 R "
                f"/Resources << /Font << /F1 {f1_idx} 0 R /F2 {f2_idx} 0 R >> >> >>"
            ).encode("ascii")
        )
        page_indices.append(page_idx)
    # Catalog.
    catalog_idx = _add_obj(
        f"<< /Type /Catalog /Pages {pages_idx} 0 R >>".encode("ascii")
    )

    # Assembler le PDF.
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = b"".join(objects)
    # Calculer les offsets.
    offset = len(header)
    offsets: list[int] = []
    for obj in objects:
        offsets.append(offset)
        offset += len(obj)
    xref_offset = offset
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode("ascii")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_idx} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode("ascii")
    return header + body + xref + trailer


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


async def render_project_esg_html(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    assessment_id: uuid.UUID,
    include_appendix_sources: bool = True,
) -> str:
    """Renvoie le HTML rendu sans générer le PDF (utile pour preview/tests)."""
    a = await _load_finalized_assessment(
        db, account_id=account_id, assessment_id=assessment_id,
    )
    ctx, _ = await _collect_context(
        db, a, include_appendix_sources=include_appendix_sources,
    )
    return _render_html(ctx)


async def generate_project_esg_report(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    assessment_id: uuid.UUID,
    include_appendix_sources: bool = True,
) -> dict[str, Any]:
    """Génère le rapport ESIA-light PDF + stocke localement.

    Returns:
        dict avec ``pdf_bytes``, ``file_path``, ``generated_at``,
        ``template_version``, ``section_count`` (=7), ``chart_count``,
        ``sources_cited``.
    """
    a = await _load_finalized_assessment(
        db, account_id=account_id, assessment_id=assessment_id,
    )
    ctx, sources_cited = await _collect_context(
        db, a, include_appendix_sources=include_appendix_sources,
    )
    html = _render_html(ctx)
    pdf_bytes = _convert_to_pdf(html)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = UPLOADS_DIR / str(account_id) / str(a.project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"esia_{a.id}_{ts}.pdf"
    file_path = out_dir / filename
    try:
        file_path.write_bytes(pdf_bytes)
    except OSError:
        logger.exception("Écriture du rapport ESIA-light sur disque échouée.")
        # On retourne quand même le binaire pour streaming.

    return {
        "pdf_bytes": pdf_bytes,
        "file_path": str(file_path),
        "generated_at": datetime.now(timezone.utc),
        "template_version": TEMPLATE_VERSION,
        "section_count": 7,
        "chart_count": 1,
        "sources_cited": sources_cited,
    }
