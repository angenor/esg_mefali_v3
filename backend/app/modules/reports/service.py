"""Service de generation de rapports ESG PDF.

Orchestre la collecte de donnees, generation de graphiques SVG,
appel LLM pour le resume executif, rendu template Jinja2 et
conversion HTML -> PDF via WeasyPrint.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.esg import ESGAssessment, ESGStatusEnum
from app.models.report import Report, ReportStatusEnum, ReportTypeEnum
from app.models.user import User
from app.modules.reports.charts import (
    generate_bar_chart_svg,
    generate_benchmark_chart_svg,
    generate_radar_chart_svg,
)
from app.prompts.esg_report import ESG_REPORT_EXECUTIVE_SUMMARY_PROMPT

logger = logging.getLogger(__name__)

# Chemins
TEMPLATES_DIR = Path(__file__).parent / "templates"
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "reports"

# Mapping secteur -> label francais
SECTOR_LABELS = {
    "agriculture": "Agriculture",
    "energy": "Energie",
    "recycling": "Recyclage",
    "transport": "Transport",
    "manufacturing": "Industrie manufacturiere",
    "services": "Services",
    "construction": "Construction / BTP",
    "commerce": "Commerce",
    "mining": "Exploitation miniere",
    "fishing": "Peche",
    "tourism": "Tourisme",
    "tech": "Technologie",
    "finance": "Finance",
    "health": "Sante",
    "education": "Education",
}

BENCHMARK_POSITION_LABELS = {
    "above_average": "Au-dessus de la moyenne sectorielle",
    "average": "Dans la moyenne sectorielle",
    "below_average": "En dessous de la moyenne sectorielle",
}


async def generate_executive_summary(
    company_name: str,
    sector: str,
    overall_score: float,
    environment_score: float,
    social_score: float,
    governance_score: float,
    strengths: list[dict],
    gaps: list[dict],
    benchmark_position: str,
) -> str:
    """Generer le resume executif via LLM (Claude via OpenRouter)."""
    strengths_text = "\n".join(
        f"- {s.get('title', 'N/A')} ({s.get('score', 0)}/10)" for s in (strengths or [])
    ) or "Aucun point fort identifie"

    gaps_text = "\n".join(
        f"- {g.get('title', 'N/A')} ({g.get('score', 0)}/10)" for g in (gaps or [])
    ) or "Aucun axe d'amelioration identifie"

    prompt_text = ESG_REPORT_EXECUTIVE_SUMMARY_PROMPT.format(
        company_name=company_name,
        sector=SECTOR_LABELS.get(sector, sector),
        overall_score=overall_score,
        environment_score=environment_score,
        social_score=social_score,
        governance_score=governance_score,
        strengths_text=strengths_text,
        gaps_text=gaps_text,
        benchmark_position=BENCHMARK_POSITION_LABELS.get(benchmark_position, benchmark_position),
    )

    llm = ChatOpenAI(
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        temperature=0.3,
    )

    response = await llm.ainvoke([
        SystemMessage(content="Tu es un consultant ESG senior."),
        HumanMessage(content=prompt_text),
    ])

    return response.content.strip()


def _extract_criteria_by_pillar(assessment_data: dict) -> dict[str, list[dict]]:
    """Extraire les scores par critere groupes par pilier."""
    criteria_scores = assessment_data.get("criteria_scores", {})
    pillar_criteria: dict[str, list[dict]] = {
        "environment": [],
        "social": [],
        "governance": [],
    }

    pillar_prefixes = {"E": "environment", "S": "social", "G": "governance"}

    for code, detail in criteria_scores.items():
        prefix = code[0].upper() if code else ""
        pillar = pillar_prefixes.get(prefix)
        if pillar:
            pillar_criteria[pillar].append({
                "code": code,
                "label": code,
                "score": detail.get("score", 0),
                "max": 10,
            })

    # Trier par code
    for pillar in pillar_criteria:
        pillar_criteria[pillar].sort(key=lambda c: c["code"])

    return pillar_criteria


def _render_html(
    assessment: ESGAssessment,
    user: User,
    executive_summary: str,
    radar_svg: str,
    pillar_bar_charts: dict[str, str],
    benchmark_svg: str | None,
    pillar_criteria: dict[str, list[dict]],
    mobilized_sources: list[dict] | None = None,
) -> str:
    """Rendre le template HTML du rapport avec les donnees.

    F01 - mobilized_sources : liste des sources citees par l'agent durant la
    generation (lookup via tool_call_logs filtre par cite_source).
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("esg_report.html")

    css_path = TEMPLATES_DIR / "esg_report.css"
    css_content = css_path.read_text(encoding="utf-8")

    sector = assessment.sector or "unknown"
    benchmark = assessment.sector_benchmark or {}

    return template.render(
        css=css_content,
        company_name=user.company_name,
        sector_label=SECTOR_LABELS.get(sector, sector),
        overall_score=assessment.overall_score or 0,
        environment_score=assessment.environment_score or 0,
        social_score=assessment.social_score or 0,
        governance_score=assessment.governance_score or 0,
        executive_summary=executive_summary,
        generation_date=datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        radar_chart_svg=radar_svg,
        pillar_bar_charts=pillar_bar_charts,
        pillar_criteria=pillar_criteria,
        strengths=assessment.strengths or [],
        gaps=assessment.gaps or [],
        recommendations=assessment.recommendations or [],
        benchmark_chart_svg=benchmark_svg,
        benchmark_position=benchmark.get("position"),
        benchmark_position_label=BENCHMARK_POSITION_LABELS.get(
            benchmark.get("position", ""), ""
        ),
        mobilized_sources=mobilized_sources or [],
    )


async def _collect_mobilized_sources(
    db: AsyncSession,
    assessment: ESGAssessment,
) -> list[dict]:
    """F01 - collecter les sources verifiees citees pour cette evaluation.

    Strategie : on regarde les tool_call_logs liees a la conversation
    associee a l'evaluation (filter tool_name='cite_source'). Pour chaque
    source_id distinct, on recupere les metadonnees (verified only).

    Si aucune conversation n'est associee, retourne une liste vide.
    """
    from app.models.source import Source, VerificationStatus

    # Best-effort : tool_call_logs peut ne pas exister selon la BDD utilisee.
    try:
        from app.models.tool_call_log import ToolCallLog
    except Exception:
        return []

    conversation_id = getattr(assessment, "conversation_id", None)
    if conversation_id is None:
        return []

    result = await db.execute(
        select(ToolCallLog).where(
            ToolCallLog.conversation_id == conversation_id,
            ToolCallLog.tool_name == "cite_source",
        )
    )
    logs = result.scalars().all()

    # Extraire les UUID source_id depuis les arguments
    source_ids: list[uuid.UUID] = []
    for log in logs:
        args = getattr(log, "arguments", None) or {}
        sid = args.get("source_id") if isinstance(args, dict) else None
        if not sid:
            continue
        try:
            source_ids.append(uuid.UUID(sid))
        except (ValueError, TypeError):
            continue

    if not source_ids:
        return []

    # Deduplication en preservant l'ordre d'apparition
    seen: set[uuid.UUID] = set()
    ordered_ids: list[uuid.UUID] = []
    for sid in source_ids:
        if sid not in seen:
            seen.add(sid)
            ordered_ids.append(sid)

    src_result = await db.execute(
        select(Source).where(
            Source.id.in_(ordered_ids),
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
    )
    src_by_id = {s.id: s for s in src_result.scalars().all()}

    mobilized: list[dict] = []
    for index, sid in enumerate(ordered_ids, start=1):
        src = src_by_id.get(sid)
        if src is None:
            continue
        mobilized.append({
            "index": index,
            "title": src.title,
            "publisher": src.publisher,
            "version": src.version,
            "date_publi": src.date_publi.isoformat() if src.date_publi else "",
            "page": src.page,
            "section": src.section or "",
            "url": src.url,
            "verification_status": src.verification_status,
        })
    return mobilized


async def generate_report(
    db: AsyncSession,
    assessment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Report:
    """Generer un rapport PDF a partir d'une evaluation ESG completee.

    Raises:
        ValueError: Si l'evaluation n'existe pas ou n'est pas completee.
    """
    # 1. Charger l'evaluation
    result = await db.execute(
        select(ESGAssessment).where(
            ESGAssessment.id == assessment_id,
            ESGAssessment.user_id == user_id,
        )
    )
    assessment = result.scalar_one_or_none()

    if assessment is None:
        raise ValueError(f"Evaluation ESG introuvable : {assessment_id}")

    if assessment.status != ESGStatusEnum.completed:
        raise ValueError(
            "L'evaluation ESG doit etre au statut 'completed' pour generer un rapport."
        )

    # 1b. Verifier qu'il n'y a pas deja une generation en cours pour cette evaluation
    from sqlalchemy import and_

    existing_generating = await db.execute(
        select(Report).where(
            and_(
                Report.assessment_id == assessment_id,
                Report.status == ReportStatusEnum.generating,
            )
        )
    )
    if existing_generating.scalar_one_or_none() is not None:
        raise ValueError(
            "Une generation de rapport est deja en cours pour cette evaluation."
        )

    # 2. Charger l'utilisateur
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    # 3. Creer l'entree Report (status: generating)
    file_name = f"rapport-esg-{user.company_name.replace(' ', '-').lower()}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}.pdf"
    report = Report(
        user_id=user_id,
        assessment_id=assessment_id,
        report_type=ReportTypeEnum.esg_compliance,
        status=ReportStatusEnum.generating,
        file_path=file_name,
    )
    db.add(report)
    await db.flush()

    try:
        # 4. Generer les graphiques SVG
        pillar_scores = {
            "environment": assessment.environment_score or 0,
            "social": assessment.social_score or 0,
            "governance": assessment.governance_score or 0,
        }
        radar_svg = generate_radar_chart_svg(pillar_scores)

        assessment_data = assessment.assessment_data or {}
        pillar_criteria = _extract_criteria_by_pillar(assessment_data)

        pillar_bar_charts = {}
        pillar_labels = {"environment": "Environnement", "social": "Social", "governance": "Gouvernance"}
        for pillar_key, pillar_label in pillar_labels.items():
            if pillar_criteria[pillar_key]:
                pillar_bar_charts[pillar_key] = generate_bar_chart_svg(
                    pillar_criteria[pillar_key], pillar_label
                )
            else:
                pillar_bar_charts[pillar_key] = ""

        # Benchmark chart
        benchmark_svg = None
        benchmark = assessment.sector_benchmark
        if benchmark and benchmark.get("averages"):
            company_scores = {
                **pillar_scores,
                "overall": assessment.overall_score or 0,
            }
            benchmark_svg = generate_benchmark_chart_svg(
                company_scores,
                benchmark["averages"],
                SECTOR_LABELS.get(assessment.sector, assessment.sector),
            )

        # 5. Generer le resume executif IA
        executive_summary = await generate_executive_summary(
            company_name=user.company_name,
            sector=assessment.sector,
            overall_score=assessment.overall_score or 0,
            environment_score=assessment.environment_score or 0,
            social_score=assessment.social_score or 0,
            governance_score=assessment.governance_score or 0,
            strengths=assessment.strengths or [],
            gaps=assessment.gaps or [],
            benchmark_position=(benchmark or {}).get("position", "unknown"),
        )

        # 6. F01 - collecter les sources mobilisees (cite_source dans tool_call_logs)
        mobilized_sources = await _collect_mobilized_sources(db, assessment)

        # 7. Rendre le template HTML
        html_content = _render_html(
            assessment=assessment,
            user=user,
            executive_summary=executive_summary,
            radar_svg=radar_svg,
            pillar_bar_charts=pillar_bar_charts,
            benchmark_svg=benchmark_svg,
            pillar_criteria=pillar_criteria,
            mobilized_sources=mobilized_sources,
        )

        # 7. Convertir HTML -> PDF via WeasyPrint (import lazy)
        from weasyprint import HTML

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = UPLOADS_DIR / file_name

        html_doc = HTML(string=html_content)
        html_doc.write_pdf(str(pdf_path))

        # 8. Mettre a jour le rapport
        file_size = pdf_path.stat().st_size
        report.status = ReportStatusEnum.completed
        report.file_size = file_size
        report.generated_at = datetime.now(timezone.utc)
        await db.flush()

    except Exception:
        logger.exception("Erreur lors de la generation du rapport PDF")
        report.status = ReportStatusEnum.failed
        await db.flush()
        raise

    return report


async def get_report(
    db: AsyncSession,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Report | None:
    """Recuperer un rapport par ID pour un utilisateur donne."""
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_report_any_user(
    db: AsyncSession,
    report_id: uuid.UUID,
) -> Report | None:
    """Recuperer un rapport par ID sans filtre utilisateur (pour verification ownership)."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def list_reports(
    db: AsyncSession,
    user_id: uuid.UUID,
    assessment_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Report], int]:
    """Lister les rapports d'un utilisateur avec pagination."""
    query = select(Report).where(Report.user_id == user_id)

    if assessment_id:
        query = query.where(Report.assessment_id == assessment_id)

    # Compter le total
    from sqlalchemy import func

    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginer
    query = query.order_by(Report.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    reports = list(result.scalars().all())

    return reports, total
