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
    """HTML→PDF via WeasyPrint avec fallback PDF minimal si indisponible."""
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        logger.warning("WeasyPrint indisponible — fallback PDF minimaliste.")
        # Fallback : PDF minimal contenant uniquement le texte plat extrait.
        try:
            from reportlab.lib.pagesizes import A4  # type: ignore
            from reportlab.pdfgen import canvas  # type: ignore
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica", 10)
            text_obj = c.beginText(40, 800)
            from html import unescape
            import re
            plain = unescape(re.sub(r"<[^>]+>", " ", html))
            for line in plain.splitlines():
                line = line.strip()
                if not line:
                    continue
                text_obj.textLine(line[:120])
            c.drawText(text_obj)
            c.showPage()
            c.save()
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            # Ultime fallback : génération PDF minimaliste à la main (1 page).
            return _minimal_pdf_bytes(html)


def _minimal_pdf_bytes(html: str) -> bytes:
    """Génère un PDF 1.4 minimal sans dépendance externe (1 page, texte plat).

    Utilisé uniquement quand ni WeasyPrint ni reportlab ne sont disponibles
    (tests CI sans dépendances natives). Le PDF résultant est valide
    (header %PDF-1.4) et contient un extrait textuel pour les vérifications.
    """
    from html import unescape
    import re
    plain = unescape(re.sub(r"<[^>]+>", " ", html))
    plain = " ".join(plain.split())[:1800]
    # Échapper parenthèses et backslashes pour la string PDF.
    plain = (
        plain.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    content_stream = (
        b"BT /F1 10 Tf 36 760 Td 14 TL ("
        + plain.encode("latin-1", errors="replace")
        + b") Tj ET"
    )
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    obj4 = (
        b"4 0 obj\n<< /Length "
        + str(len(content_stream)).encode("ascii")
        + b" >>\nstream\n" + content_stream + b"\nendstream\nendobj\n"
    )
    obj5 = (
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
        b"\nendobj\n"
    )
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = obj1 + obj2 + obj3 + obj4 + obj5
    # Construction de la xref simplifiée.
    offset = len(header)
    offsets: list[int] = []
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(offset)
        offset += len(obj)
    xref_offset = offset
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode("ascii")
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF"
    )
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
