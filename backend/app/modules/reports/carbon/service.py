"""F21 — Service de génération du rapport carbone PDF.

Réutilise l'arborescence ``/uploads/reports/`` du module F06.

Workflow asynchrone :
1. Vérifie l'ownership et le statut ``completed`` du bilan (FR-017).
2. Vérifie qu'aucune génération n'est déjà ``generating`` pour ce bilan (FR-018).
3. Crée une ligne ``Report`` (status=generating).
4. Dispatche un BackgroundTask qui rend le PDF puis transite vers ``completed``
   ou ``failed``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report, ReportStatusEnum, ReportTypeEnum
from app.modules.reports.carbon.exceptions import (
    AssessmentNotFinalizedError,
    AssessmentNotFoundError,
    ConcurrentGenerationError,
)

logger = logging.getLogger(__name__)


UPLOADS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "uploads" / "reports"
)


async def _load_assessment(db: AsyncSession, assessment_id: uuid.UUID, user_id: uuid.UUID):
    """Charger un bilan carbone et vérifier l'ownership."""
    from app.models.carbon import CarbonAssessment, CarbonStatusEnum

    result = await db.execute(
        select(CarbonAssessment).where(
            CarbonAssessment.id == assessment_id,
            CarbonAssessment.user_id == user_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise AssessmentNotFoundError(
            f"Bilan carbone introuvable : {assessment_id}"
        )
    if assessment.status != CarbonStatusEnum.completed:
        raise AssessmentNotFinalizedError(
            "Le bilan carbone doit être finalisé avant la génération du rapport."
        )
    return assessment


async def _check_no_concurrent_generation(
    db: AsyncSession, assessment_id: uuid.UUID
) -> None:
    """Refuser la génération si un job ``generating`` existe déjà (FR-018)."""
    existing = await db.execute(
        select(Report).where(
            and_(
                Report.assessment_id == assessment_id,
                Report.report_type == ReportTypeEnum.carbon,
                Report.status == ReportStatusEnum.generating,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConcurrentGenerationError(
            "Une génération de rapport carbone est déjà en cours pour ce bilan."
        )


def _build_context(
    assessment, user, entries: list, numbered_sources: list, equivalences: list
) -> dict:
    """Construire le contexte Jinja2 du rapport carbone."""
    from app.modules.reports.carbon.chart_builder import (
        CATEGORY_LABELS_FR,
        build_breakdown_pie_svg,
    )

    total = float(assessment.total_emissions_tco2e or 0.0)

    # Catégories agrégées.
    categories: dict[str, float] = {}
    scopes: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
    for entry in entries:
        cat = getattr(entry, "category", None) or "unknown"
        val = float(getattr(entry, "emissions_tco2e", 0.0) or 0.0)
        categories[cat] = categories.get(cat, 0.0) + val
        scope = getattr(entry, "scope", None)
        if scope in (1, 2, 3):
            scopes[scope] += val

    categories_table = []
    for k, v in categories.items():
        share = (v / total * 100.0) if total > 0 else 0.0
        categories_table.append(
            {"label": CATEGORY_LABELS_FR.get(k, k), "value": v, "share": share}
        )

    breakdown_pie_svg = build_breakdown_pie_svg(categories) if categories else ""
    sector_comparison_svg = ""  # benchmark optionnel — non bloquant

    # Convertir équivalences en dicts pour Jinja, en attribuant un index source.
    equivalences_ctx = []
    for eq in equivalences:
        source_index = None
        if eq.is_sourced and eq.source_id is not None:
            for src in numbered_sources:
                if src.source_id == eq.source_id:
                    source_index = src.index
                    break
        equivalences_ctx.append(
            {
                "label": eq.label,
                "value": eq.value,
                "unit": eq.unit,
                "is_sourced": eq.is_sourced,
                "source_index": source_index,
                "fallback_label": eq.fallback_label,
            }
        )

    return {
        "company_name": getattr(user, "company_name", "—"),
        "company_country": getattr(user, "country", None) or "UEMOA",
        "assessment_year": assessment.year,
        "generation_date": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        "total_tco2e": total,
        "intensity": round(total / max(1.0, float(getattr(user, "annual_revenue_amount", 0) or 0) / 1_000_000.0), 2) if getattr(user, "annual_revenue_amount", None) else 0.0,
        "scope1": scopes[1],
        "scope2": scopes[2],
        "scope3": scopes[3],
        "breakdown_pie_svg": breakdown_pie_svg,
        "categories_table": categories_table,
        "sector_comparison_svg": sector_comparison_svg,
        "yearly_line_svg": "",  # alimenté si plusieurs bilans (best-effort)
        "reduction_actions": [],  # alimenté depuis assessment.reduction_plan
        "equivalences": equivalences_ctx,
        "methodology_factors": [],
        "numbered_sources": [
            {
                "index": s.index,
                "title": s.title,
                "publisher": s.publisher,
                "version": s.version,
                "date_publi": s.date_publi,
                "page": s.page,
                "section": s.section,
                "url": s.url,
            }
            for s in numbered_sources
        ],
    }


async def _render_pdf_async(
    db_factory,
    report_id: uuid.UUID,
    assessment_id: uuid.UUID,
    user_id: uuid.UUID,
    file_path: str,
) -> None:
    """Job asynchrone : rendu PDF + transition de statut."""
    from app.models.carbon import CarbonEmissionEntry
    from app.models.user import User
    from app.modules.reports.carbon.equivalences import compute_equivalences
    from app.modules.reports.carbon.pdf_renderer import render_carbon_pdf
    from app.modules.reports.carbon.sources_collector import collect_sources

    async with db_factory() as db:
        report = await db.get(Report, report_id)
        if report is None:
            return
        try:
            assessment = await db.get(__import__("app.models.carbon", fromlist=["CarbonAssessment"]).CarbonAssessment, assessment_id)
            user = await db.get(User, user_id)

            entries_result = await db.execute(
                select(CarbonEmissionEntry).where(
                    CarbonEmissionEntry.assessment_id == assessment_id
                )
            )
            entries = list(entries_result.scalars().all())

            numbered = await collect_sources(
                db,
                assessment_id=assessment_id,
                conversation_id=getattr(assessment, "conversation_id", None),
            )
            total = float(getattr(assessment, "total_emissions_tco2e", 0) or 0.0)
            equivalences = compute_equivalences(total, sources=None)

            context = _build_context(assessment, user, entries, numbered, equivalences)

            output_path = UPLOADS_DIR / file_path
            render_carbon_pdf(context, output_path)

            file_size = output_path.stat().st_size
            report.status = ReportStatusEnum.completed
            report.file_size = file_size
            report.generated_at = datetime.now(timezone.utc)
            await db.flush()
            await db.commit()
            logger.info(
                "carbon_report_generated",
                extra={"report_id": str(report_id), "size": file_size},
            )
        except Exception:  # pragma: no cover (best-effort résilience)
            logger.exception("Erreur lors de la génération du rapport carbone")
            report.status = ReportStatusEnum.failed
            await db.flush()
            await db.commit()


async def generate_carbon_report(
    db: AsyncSession,
    assessment_id: uuid.UUID,
    user_id: uuid.UUID,
    source: Literal["manual", "llm"] = "manual",
) -> Report:
    """Démarrer la génération asynchrone d'un rapport carbone PDF.

    Raises:
        AssessmentNotFoundError: bilan introuvable / pas possédé.
        AssessmentNotFinalizedError: bilan non finalisé.
        ConcurrentGenerationError: une génération est déjà en cours.
    """
    from app.models.user import User

    # Validation préalable (lève si non finalisé / introuvable / concurrent).
    await _load_assessment(db, assessment_id, user_id)
    await _check_no_concurrent_generation(db, assessment_id)

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    file_name = (
        f"rapport-carbone-{(user.company_name or 'pme').replace(' ', '-').lower()}"
        f"-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}.pdf"
    )
    report = Report(
        user_id=user_id,
        account_id=getattr(user, "account_id", None),
        assessment_id=assessment_id,
        report_type=ReportTypeEnum.carbon,
        status=ReportStatusEnum.generating,
        file_path=file_name,
    )
    db.add(report)
    await db.flush()
    logger.info(
        "carbon_report_create_pending",
        extra={
            "report_id": str(report.id),
            "assessment_id": str(assessment_id),
            "source_of_change": source,
        },
    )
    return report


async def list_carbon_reports(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Report], int]:
    """Lister les rapports carbone d'un utilisateur."""
    from sqlalchemy import func

    query = select(Report).where(
        Report.user_id == user_id,
        Report.report_type == ReportTypeEnum.carbon,
    )
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.order_by(Report.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(query)
    reports = list(result.scalars().all())
    return reports, total


__all__ = [
    "UPLOADS_DIR",
    "generate_carbon_report",
    "list_carbon_reports",
    "_render_pdf_async",
]
