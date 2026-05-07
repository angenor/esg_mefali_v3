"""F23 — Service métier des Skills (CRUD + publish + versioning).

Responsabilités :
- CRUD avec validation centralisée (cf. ``validator.py``).
- Publication conditionnée par eval gating (cf. ``eval_runner.py``).
- Versioning F04 : édition d'une skill published crée une nouvelle ligne
  draft (semver patch+1) ; publication de la nouvelle version retire
  l'ancienne (valid_to + superseded_by).
- Soft delete : seules les drafts peuvent être supprimées (valid_to = today).

Référence : ``specs/033-skills-playbooks-metier/data-model.md``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

import semver
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillStatus
from app.modules.skills.eval_runner import run_skill_eval
from app.modules.skills.exceptions import (
    EvalGatingFailedError,
    InsufficientGoldenExamplesError,
    SkillNotFoundError,
)
from app.modules.skills.schemas import (
    SkillCreate,
    SkillEvalReport,
    SkillUpdate,
)
from app.modules.skills.validator import validate_skill_payload

logger = logging.getLogger(__name__)


MIN_GOLDEN_EXAMPLES_FOR_PUBLISH: int = 5


def _payload_to_db_dict(payload: SkillCreate | SkillUpdate) -> dict[str, Any]:
    """Convertit un Pydantic en dict SQLAlchemy-friendly (UUIDs en str)."""
    raw = payload.model_dump(exclude_unset=True, mode="python")
    if "sources" in raw and raw["sources"] is not None:
        raw["sources"] = [str(s) for s in raw["sources"]]
    if "activation_rules" in raw and raw["activation_rules"] is not None:
        # Pydantic model → dict
        ar = raw["activation_rules"]
        if hasattr(ar, "model_dump"):
            raw["activation_rules"] = ar.model_dump(mode="python")
    if "golden_examples" in raw and raw["golden_examples"] is not None:
        cleaned = []
        for ex in raw["golden_examples"]:
            if hasattr(ex, "model_dump"):
                cleaned.append(ex.model_dump(mode="python"))
            else:
                cleaned.append(ex)
        raw["golden_examples"] = cleaned
    if "domain" in raw and hasattr(raw["domain"], "value"):
        raw["domain"] = raw["domain"].value
    return raw


def _bump_patch(version: str) -> str:
    """Incrémente la version semver patch+1 (1.0.0 → 1.0.1)."""
    try:
        return str(semver.Version.parse(version).bump_patch())
    except (ValueError, TypeError):
        # Fallback safe si version non semver complète (ex: "1.0").
        return f"{version}.1" if "." in version and version.count(".") < 2 else "1.0.1"


class SkillService:
    """Service applicatif pour les Skills."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read

    async def get_skill(self, skill_id: uuid.UUID) -> Skill:
        stmt = select(Skill).where(Skill.id == skill_id)
        result = await self.db.execute(stmt)
        skill = result.scalar_one_or_none()
        if skill is None:
            raise SkillNotFoundError(skill_id)
        return skill

    async def list_skills(
        self,
        *,
        domain: str | None = None,
        status: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Skill], int]:
        from sqlalchemy import func

        stmt = select(Skill)
        count_stmt = select(func.count()).select_from(Skill)
        if domain:
            stmt = stmt.where(Skill.domain == domain)
            count_stmt = count_stmt.where(Skill.domain == domain)
        if status:
            stmt = stmt.where(Skill.status == status)
            count_stmt = count_stmt.where(Skill.status == status)
        if q:
            ilike = f"%{q}%"
            stmt = stmt.where(Skill.name.ilike(ilike))
            count_stmt = count_stmt.where(Skill.name.ilike(ilike))

        offset = max(0, (page - 1) * limit)
        stmt = stmt.order_by(Skill.created_at.desc()).offset(offset).limit(limit)

        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())
        total_res = await self.db.execute(count_stmt)
        total = int(total_res.scalar_one() or 0)
        return items, total

    async def query_skills_matching(
        self,
        *,
        domain: str | None = None,
    ) -> list[Skill]:
        """Retourne les Skills publiées non expirées (utilisé par le loader)."""
        today = date.today()
        stmt = (
            select(Skill)
            .where(Skill.status == SkillStatus.PUBLISHED.value)
            .where(or_(Skill.valid_to.is_(None), Skill.valid_to > today))
        )
        if domain:
            stmt = stmt.where(Skill.domain == domain)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write

    async def create_skill(
        self,
        payload: SkillCreate,
        *,
        creator_id: uuid.UUID,
    ) -> Skill:
        await validate_skill_payload(payload, self.db)
        body = _payload_to_db_dict(payload)
        skill = Skill(
            **body,
            created_by=creator_id,
            status=SkillStatus.DRAFT.value,
        )
        self.db.add(skill)
        await self.db.flush()
        logger.info("[skills.service] created skill name=%s id=%s", skill.name, skill.id)
        return skill

    async def update_skill(
        self,
        skill_id: uuid.UUID,
        payload: SkillUpdate,
        *,
        updater_id: uuid.UUID,
    ) -> Skill:
        skill = await self.get_skill(skill_id)
        await validate_skill_payload(payload, self.db)

        if skill.status == SkillStatus.PUBLISHED.value:
            return await self._create_new_version(skill, payload, updater_id)

        # In-place update (draft).
        body = _payload_to_db_dict(payload)
        for key, value in body.items():
            setattr(skill, key, value)
        await self.db.flush()
        return skill

    async def _create_new_version(
        self,
        published_skill: Skill,
        payload: SkillUpdate,
        updater_id: uuid.UUID,
    ) -> Skill:
        """Crée une nouvelle version draft basée sur la skill published."""
        body = _payload_to_db_dict(payload)
        new_version_str = _bump_patch(published_skill.version)
        new_skill = Skill(
            name=published_skill.name + f"_v{new_version_str}",
            domain=body.get("domain", published_skill.domain),
            prompt_expert=body.get("prompt_expert", published_skill.prompt_expert),
            procedure=body.get("procedure", published_skill.procedure),
            tool_whitelist=body.get(
                "tool_whitelist", list(published_skill.tool_whitelist or [])
            ),
            sources=body.get("sources", list(published_skill.sources or [])),
            activation_rules=body.get(
                "activation_rules",
                dict(published_skill.activation_rules or {}),
            ),
            golden_examples=body.get(
                "golden_examples", list(published_skill.golden_examples or [])
            ),
            status=SkillStatus.DRAFT.value,
            version=new_version_str,
            created_by=updater_id,
        )
        self.db.add(new_skill)
        await self.db.flush()
        logger.info(
            "[skills.service] created new version %s for parent=%s",
            new_skill.version,
            published_skill.id,
        )
        return new_skill

    async def delete_skill_draft(self, skill_id: uuid.UUID) -> None:
        skill = await self.get_skill(skill_id)
        if skill.status != SkillStatus.DRAFT.value:
            raise ValueError("Only draft skills can be deleted (use unpublish first)")
        skill.valid_to = date.today()
        await self.db.flush()

    async def unpublish_skill(self, skill_id: uuid.UUID) -> Skill:
        skill = await self.get_skill(skill_id)
        if skill.status != SkillStatus.PUBLISHED.value:
            raise ValueError("Skill is not published")
        skill.status = SkillStatus.DRAFT.value
        await self.db.flush()
        return skill

    async def publish_skill(
        self,
        skill_id: uuid.UUID,
        publisher_id: uuid.UUID,
    ) -> tuple[Skill, SkillEvalReport]:
        """Publie une skill draft après gating eval (≥ 90 % de réussite)."""
        skill = await self.get_skill(skill_id)
        if skill.status != SkillStatus.DRAFT.value:
            raise ValueError("Only draft skills can be published")

        n_examples = len(skill.golden_examples or [])
        if n_examples < MIN_GOLDEN_EXAMPLES_FOR_PUBLISH:
            raise InsufficientGoldenExamplesError(
                actual=n_examples,
                minimum=MIN_GOLDEN_EXAMPLES_FOR_PUBLISH,
            )

        report = await run_skill_eval(skill_id, self.db)
        if not report.gate_passed:
            raise EvalGatingFailedError(report)

        skill.status = SkillStatus.PUBLISHED.value
        if skill.verified_by is None and publisher_id != skill.created_by:
            skill.verified_by = publisher_id
        await self.db.flush()
        logger.info(
            "[skills.service] published skill name=%s id=%s success_rate=%.2f",
            skill.name,
            skill.id,
            report.success_rate,
        )
        return skill, report
