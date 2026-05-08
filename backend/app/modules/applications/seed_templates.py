"""F15 — Seed des templates de dossier MVP.

Insère idempotemment :
- 1 source seed F01 ``system://mefali/catalogue-templates`` si absente.
- 4 templates fallback ``published`` (un par instrument FR principal) +
  1 template EN GCF Direct Access. Chaque template référence
  ``skill_dossier_gcf_via_boad`` ou ``skill_esg_diagnostic`` (existantes
  via le seed F23) selon le domaine.

L'idempotence est garantie par ``name`` (UNIQUE).

Usage :
    from app.modules.applications.seed_templates import seed_templates
    inserted = await seed_templates(db, admin_id, verifier_id)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill
from app.models.source import Source
from app.models.template_dossier import (
    TemplateDossier,
    TemplateInstrumentType,
    TemplateLanguage,
    TemplateStatus,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedResult:
    """Bilan d'un appel à :func:`seed_templates`."""

    inserted_templates: int
    inserted_source: bool
    total_in_db: int


SEED_SOURCE_URI = "system://mefali/catalogue-templates"


def _default_sections_fr() -> list[dict[str, Any]]:
    return [
        {
            "key": "executive_summary",
            "title": "Résumé exécutif",
            "instructions": (
                "Résumer en 200-300 mots le projet, son alignement ESG et le "
                "montant demandé. Citer le secteur, le pays et le CA de la PME."
            ),
            "target_length": 300,
            "required": True,
        },
        {
            "key": "company_presentation",
            "title": "Présentation de l'entreprise",
            "instructions": (
                "Décrire l'entreprise : raison sociale, secteur, effectif, "
                "ancienneté, gouvernance. Citer une source vérifiée pour "
                "chaque chiffre clé."
            ),
            "target_length": 500,
            "required": True,
        },
        {
            "key": "project_description",
            "title": "Description du projet",
            "instructions": (
                "Présenter le projet : objectifs, périmètre, calendrier, "
                "bénéficiaires, indicateurs d'impact ESG."
            ),
            "target_length": 700,
            "required": True,
        },
        {
            "key": "financial_plan",
            "title": "Plan financier",
            "instructions": (
                "Détailler le budget total, la répartition par poste, les "
                "co-financements, le ROI attendu et le calendrier de "
                "décaissement."
            ),
            "target_length": 500,
            "required": True,
        },
        {
            "key": "esg_impact",
            "title": "Impact ESG attendu",
            "instructions": (
                "Lister les indicateurs ESG (tCO2e évitées, emplois créés, "
                "femmes formées, hectares restaurés). Citer la méthodologie "
                "(IPCC AR6, GHG Protocol)."
            ),
            "target_length": 600,
            "required": True,
        },
    ]


def _default_sections_en() -> list[dict[str, Any]]:
    return [
        {
            "key": "executive_summary",
            "title": "Executive Summary",
            "instructions": (
                "Summarize the project in 200-300 words, its ESG alignment "
                "and the requested amount. Cite the SME's sector, country "
                "and revenue."
            ),
            "target_length": 300,
            "required": True,
        },
        {
            "key": "company_presentation",
            "title": "Company Overview",
            "instructions": (
                "Describe the company: legal form, sector, headcount, "
                "history, governance. Cite a verified source for each key "
                "figure."
            ),
            "target_length": 500,
            "required": True,
        },
        {
            "key": "project_description",
            "title": "Project Description",
            "instructions": (
                "Present the project: objectives, scope, timeline, "
                "beneficiaries, ESG impact indicators."
            ),
            "target_length": 700,
            "required": True,
        },
        {
            "key": "financial_plan",
            "title": "Financial Plan",
            "instructions": (
                "Detail total budget, breakdown by item, co-financing, "
                "expected ROI and disbursement schedule."
            ),
            "target_length": 500,
            "required": True,
        },
        {
            "key": "esg_impact",
            "title": "Expected ESG Impact",
            "instructions": (
                "List ESG indicators (tCO2e avoided, jobs created, women "
                "trained, hectares restored). Cite methodology (IPCC AR6, "
                "GHG Protocol)."
            ),
            "target_length": 600,
            "required": True,
        },
    ]


def _default_required_documents() -> list[dict[str, Any]]:
    return [
        {"title": "Business plan", "mandatory": True, "origin": "template"},
        {
            "title": "États financiers (3 dernières années)",
            "mandatory": True,
            "origin": "template",
        },
        {"title": "Étude d'impact ESG", "mandatory": True, "origin": "template"},
        {"title": "Statuts de la société", "mandatory": True, "origin": "template"},
        {"title": "Lettre de motivation", "mandatory": False, "origin": "template"},
    ]


def _build_seeds() -> list[dict[str, Any]]:
    """Liste des seeds à insérer."""
    return [
        {
            "name": "Template fallback subvention (FR)",
            "instrument_type": TemplateInstrumentType.SUBVENTION.value,
            "language": TemplateLanguage.FR.value,
            "sections": _default_sections_fr(),
            "required_documents": _default_required_documents(),
            "tone": "formel banque",
        },
        {
            "name": "Template fallback prêt concessionnel (FR)",
            "instrument_type": TemplateInstrumentType.PRET_CONCESSIONNEL.value,
            "language": TemplateLanguage.FR.value,
            "sections": _default_sections_fr(),
            "required_documents": _default_required_documents(),
            "tone": "formel banque",
        },
        {
            "name": "Template fallback equity (FR)",
            "instrument_type": TemplateInstrumentType.EQUITY.value,
            "language": TemplateLanguage.FR.value,
            "sections": _default_sections_fr(),
            "required_documents": _default_required_documents(),
            "tone": "narratif investisseur",
        },
        {
            "name": "Template fallback blending (FR)",
            "instrument_type": TemplateInstrumentType.BLENDING.value,
            "language": TemplateLanguage.FR.value,
            "sections": _default_sections_fr(),
            "required_documents": _default_required_documents(),
            "tone": "formel IFI",
        },
        {
            "name": "Template fallback subvention (EN)",
            "instrument_type": TemplateInstrumentType.SUBVENTION.value,
            "language": TemplateLanguage.EN.value,
            "sections": _default_sections_en(),
            "required_documents": _default_required_documents(),
            "tone": "formal IFI",
        },
    ]


async def _ensure_source(
    db: AsyncSession,
    captured_by: uuid.UUID,
    verified_by: uuid.UUID | None,
) -> tuple[uuid.UUID, bool]:
    """Insère la source seed F15 si absente. Retourne (id, inserted)."""
    from datetime import date, datetime, timezone

    stmt = select(Source).where(Source.url == SEED_SOURCE_URI)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing.id, False

    # Pour respecter le CHECK 4-yeux ``verified_by != captured_by``, on
    # privilégie un verifier distinct ; à défaut, on laisse la source en
    # ``pending`` (verification_status='pending') jusqu'à intervention admin.
    use_verified = verified_by is not None and verified_by != captured_by
    src = Source(
        url=SEED_SOURCE_URI,
        title="Mefali — Catalogue interne templates dossier",
        publisher="Mefali",
        version="1.0",
        date_publi=date.today(),
        captured_by=captured_by,
        verified_by=verified_by if use_verified else None,
        verification_status="verified" if use_verified else "pending",
        verified_at=datetime.now(timezone.utc) if use_verified else None,
        created_by_user_id=captured_by,
    )
    db.add(src)
    await db.flush()
    return src.id, True


async def _resolve_default_skill(db: AsyncSession) -> uuid.UUID:
    """Trouve une Skill F23 publiée (préférence ``skill_esg_diagnostic``)."""
    for preferred_name in (
        "skill_dossier_gcf_via_boad",
        "skill_esg_diagnostic",
    ):
        stmt = select(Skill).where(Skill.name == preferred_name)
        skill = (await db.execute(stmt)).scalar_one_or_none()
        if skill is not None:
            return skill.id

    # Fallback : première skill quelle qu'elle soit
    stmt = select(Skill).limit(1)
    skill = (await db.execute(stmt)).scalar_one_or_none()
    if skill is None:
        raise RuntimeError(
            "Aucune Skill F23 disponible — impossible de seeder les templates "
            "F15. Lancer d'abord ``seed_skills``."
        )
    return skill.id


async def seed_templates(
    db: AsyncSession,
    *,
    captured_by: uuid.UUID,
    verified_by: uuid.UUID | None = None,
) -> SeedResult:
    """Insère les templates MVP de manière idempotente.

    Args:
        db: session async.
        captured_by: UUID admin qui crée les drafts.
        verified_by: UUID admin distinct qui vérifie. Si None, les
            templates restent à l'état ``draft``.

    Returns:
        :class:`SeedResult` avec compteurs.
    """
    if verified_by is not None and verified_by == captured_by:
        raise ValueError(
            "captured_by et verified_by doivent être distincts (4-yeux)."
        )

    source_id, src_inserted = await _ensure_source(db, captured_by, verified_by)
    skill_id = await _resolve_default_skill(db)

    inserted = 0
    seeds = _build_seeds()
    for seed in seeds:
        existing = await db.execute(
            select(TemplateDossier).where(TemplateDossier.name == seed["name"])
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("[templates.seed] %s déjà présent, skip", seed["name"])
            continue
        template = TemplateDossier(
            name=seed["name"],
            instrument_type=seed["instrument_type"],
            language=seed["language"],
            sections=seed["sections"],
            required_documents=seed["required_documents"],
            tone=seed["tone"],
            skill_id=skill_id,
            source_id=source_id,
            captured_by=captured_by,
            verified_by=verified_by,
            status=(
                TemplateStatus.PUBLISHED.value
                if verified_by is not None
                else TemplateStatus.DRAFT.value
            ),
        )
        db.add(template)
        inserted += 1
        logger.info("[templates.seed] %s inséré", seed["name"])

    await db.flush()

    total_stmt = select(TemplateDossier)
    total = len((await db.execute(total_stmt)).scalars().all())

    return SeedResult(
        inserted_templates=inserted,
        inserted_source=src_inserted,
        total_in_db=total,
    )
