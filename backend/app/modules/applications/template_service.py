"""F15 — Service métier ``TemplateDossier``.

CRUD léger sur les Templates :
- :func:`list_templates` : liste filtrable (offer_id, instrument, language, status).
- :func:`get_template` : récupération par ID.
- :func:`get_effective_template_for_offer` : résolution offer→template
  (template lié à l'offre prioritaire, fallback générique par instrument).
- :func:`create_template_draft` : création d'un brouillon admin.
- :func:`publish_template` : publication 4-yeux (verified_by ≠ captured_by).
- :func:`unpublish_template` : retour en draft.

Toutes les mutations passent par le router admin et sont auditées via
``AdminAuditContextMiddleware`` (source_of_change=admin). La table est
dans ``EXEMPT_MODELS`` (catalogue admin-only sans account_id, cohérent
F23 ``Skill``).
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template_dossier import (
    TemplateDossier,
    TemplateLanguage,
    TemplateStatus,
)


class TemplateNotFoundError(LookupError):
    """Aucun template ne correspond à la requête."""


class TemplateFourEyesError(ValueError):
    """Violation du principe 4-yeux (verified_by == captured_by)."""


async def list_templates(
    db: AsyncSession,
    *,
    offer_id: uuid.UUID | None = None,
    instrument_type: str | None = None,
    language: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[TemplateDossier], int]:
    """Liste paginée filtrable des templates."""
    stmt = select(TemplateDossier)
    if offer_id is not None:
        stmt = stmt.where(TemplateDossier.offer_id == offer_id)
    if instrument_type:
        stmt = stmt.where(TemplateDossier.instrument_type == instrument_type)
    if language:
        stmt = stmt.where(TemplateDossier.language == language)
    if status:
        stmt = stmt.where(TemplateDossier.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(TemplateDossier.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_template(
    db: AsyncSession, template_id: uuid.UUID,
) -> TemplateDossier | None:
    """Retourne un template par ID (ou None)."""
    return await db.get(TemplateDossier, template_id)


async def get_effective_template_for_offer(
    db: AsyncSession,
    offer_id: uuid.UUID | None,
    instrument_type: str | None,
    language: str = TemplateLanguage.FR.value,
) -> TemplateDossier | None:
    """Résolution du template effectif pour une offre + langue.

    Priorité :
    1. Template ``published`` lié à l'offre + langue exacte.
    2. Fallback générique ``published`` par ``instrument_type`` + langue.
    3. None (la PME doit demander à un admin de publier un template).
    """
    if offer_id is not None:
        stmt = (
            select(TemplateDossier)
            .where(
                and_(
                    TemplateDossier.offer_id == offer_id,
                    TemplateDossier.language == language,
                    TemplateDossier.status == TemplateStatus.PUBLISHED.value,
                    TemplateDossier.valid_to.is_(None),
                )
            )
            .order_by(TemplateDossier.updated_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()
        if template is not None:
            return template

    if instrument_type:
        stmt = (
            select(TemplateDossier)
            .where(
                and_(
                    TemplateDossier.offer_id.is_(None),
                    TemplateDossier.instrument_type == instrument_type,
                    TemplateDossier.language == language,
                    TemplateDossier.status == TemplateStatus.PUBLISHED.value,
                    TemplateDossier.valid_to.is_(None),
                )
            )
            .order_by(TemplateDossier.updated_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    return None


async def create_template_draft(
    db: AsyncSession,
    *,
    name: str,
    instrument_type: str,
    language: str,
    sections: list,
    required_documents: list,
    tone: str,
    skill_id: uuid.UUID,
    source_id: uuid.UUID,
    captured_by: uuid.UUID,
    offer_id: uuid.UUID | None = None,
    vocabulary_hints: dict | None = None,
    anti_patterns: list | None = None,
    version: str = "1.0",
) -> TemplateDossier:
    """Crée un brouillon de template (status=draft)."""
    template = TemplateDossier(
        name=name,
        offer_id=offer_id,
        instrument_type=instrument_type,
        language=language,
        sections=sections,
        required_documents=required_documents,
        tone=tone,
        vocabulary_hints=vocabulary_hints,
        anti_patterns=anti_patterns,
        skill_id=skill_id,
        source_id=source_id,
        version=version,
        status=TemplateStatus.DRAFT.value,
        captured_by=captured_by,
    )
    db.add(template)
    await db.flush()
    return template


async def publish_template(
    db: AsyncSession,
    template: TemplateDossier,
    *,
    verified_by: uuid.UUID,
) -> TemplateDossier:
    """Publie un template après vérification 4-yeux."""
    if verified_by == template.captured_by:
        raise TemplateFourEyesError(
            "Le vérificateur doit être différent de l'auteur du brouillon "
            "(principe 4-yeux F09)."
        )
    template.verified_by = verified_by
    template.status = TemplateStatus.PUBLISHED.value
    await db.flush()
    return template


async def unpublish_template(
    db: AsyncSession, template: TemplateDossier,
) -> TemplateDossier:
    """Retourne un template publié à l'état draft."""
    template.status = TemplateStatus.DRAFT.value
    await db.flush()
    return template
