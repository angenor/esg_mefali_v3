"""F23 — Router admin REST pour les Skills (Playbooks Métier).

8 endpoints :
- GET    /api/admin/skills                 → liste paginée
- POST   /api/admin/skills                 → création (status=draft)
- GET    /api/admin/skills/{id}            → détail
- PATCH  /api/admin/skills/{id}            → édition (in-place ou nouvelle version)
- POST   /api/admin/skills/{id}/publish    → eval gating + publication
- POST   /api/admin/skills/{id}/test       → eval sans publication
- POST   /api/admin/skills/{id}/unpublish  → rollback published → draft
- DELETE /api/admin/skills/{id}            → soft delete (drafts uniquement)

Tous protégés par ``Depends(get_current_admin)`` (F02).
Mappage erreurs → HTTP codes : cf. ``contracts/admin_skills_endpoints.md``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.user import User
from app.modules.skills.exceptions import (
    EvalGatingFailedError,
    EvalTimeoutError,
    InjectionDetectedError,
    InsufficientGoldenExamplesError,
    SkillNotFoundError,
    SourceNotFoundError,
    SourceNotVerifiedError,
    TokensLimitExceededError,
    UnknownToolError,
)
from app.modules.skills.eval_runner import run_skill_eval
from app.modules.skills.schemas import (
    SkillCreate,
    SkillEvalReport,
    SkillListItem,
    SkillListResponse,
    SkillPublishResponse,
    SkillRead,
    SkillUpdate,
)
from app.modules.skills.service import SkillService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["admin-skills"])


def _http_422(code: str, **fields) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": code, **fields},
    )


def _map_validator_error(exc: Exception) -> HTTPException:
    """Convertit les exceptions du validator/service en HTTPException 422/4xx."""
    if isinstance(exc, InjectionDetectedError):
        return _http_422("detected_patterns", detected_patterns=exc.detected_patterns)
    if isinstance(exc, TokensLimitExceededError):
        return _http_422(
            f"{exc.field}_too_long",
            actual_tokens=exc.actual,
            max_tokens=exc.max_tokens,
        )
    if isinstance(exc, UnknownToolError):
        return _http_422("tool_name_unknown", tool_name=exc.tool_name)
    if isinstance(exc, SourceNotFoundError):
        return _http_422("source_not_found", source_id=str(exc.source_id))
    if isinstance(exc, SourceNotVerifiedError):
        return _http_422(
            "source_must_be_verified",
            source_id=str(exc.source_id),
            current_status=exc.current_status,
        )
    if isinstance(exc, InsufficientGoldenExamplesError):
        return _http_422(
            "insufficient_golden_examples",
            actual=exc.actual,
            minimum=exc.minimum,
        )
    if isinstance(exc, EvalGatingFailedError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "gate_failed",
                "eval_report": exc.report.model_dump(mode="json"),
            },
        )
    if isinstance(exc, EvalTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "eval_timeout",
                "elapsed_seconds": exc.elapsed_seconds,
            },
        )
    if isinstance(exc, SkillNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "skill_not_found", "skill_id": str(exc.skill_id)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "internal_error", "message": str(exc)},
    )


@router.get("", response_model=SkillListResponse)
async def list_skills(
    domain: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillListResponse:
    service = SkillService(db)
    items, total = await service.list_skills(
        domain=domain,
        status=status_filter,
        q=q,
        page=page,
        limit=limit,
    )
    return SkillListResponse(
        items=[SkillListItem.model_validate(s) for s in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillCreate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    service = SkillService(db)
    try:
        skill = await service.create_skill(payload, creator_id=current_admin.id)
        await db.commit()
        await db.refresh(skill)
    except (
        InjectionDetectedError,
        TokensLimitExceededError,
        UnknownToolError,
        SourceNotFoundError,
        SourceNotVerifiedError,
    ) as exc:
        await db.rollback()
        raise _map_validator_error(exc) from exc
    return SkillRead.model_validate(skill)


@router.get("/{skill_id}", response_model=SkillRead)
async def get_skill(
    skill_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    service = SkillService(db)
    try:
        skill = await service.get_skill(skill_id)
    except SkillNotFoundError as exc:
        raise _map_validator_error(exc) from exc
    return SkillRead.model_validate(skill)


@router.patch("/{skill_id}", response_model=SkillRead)
async def update_skill(
    skill_id: uuid.UUID,
    payload: SkillUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    service = SkillService(db)
    try:
        skill = await service.update_skill(
            skill_id, payload, updater_id=current_admin.id
        )
        await db.commit()
        await db.refresh(skill)
    except SkillNotFoundError as exc:
        raise _map_validator_error(exc) from exc
    except (
        InjectionDetectedError,
        TokensLimitExceededError,
        UnknownToolError,
        SourceNotFoundError,
        SourceNotVerifiedError,
    ) as exc:
        await db.rollback()
        raise _map_validator_error(exc) from exc
    return SkillRead.model_validate(skill)


@router.post("/{skill_id}/publish", response_model=SkillPublishResponse)
async def publish_skill(
    skill_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillPublishResponse:
    service = SkillService(db)
    try:
        skill, report = await service.publish_skill(skill_id, current_admin.id)
        await db.commit()
        await db.refresh(skill)
    except SkillNotFoundError as exc:
        raise _map_validator_error(exc) from exc
    except InsufficientGoldenExamplesError as exc:
        await db.rollback()
        raise _map_validator_error(exc) from exc
    except EvalGatingFailedError as exc:
        await db.rollback()
        raise _map_validator_error(exc) from exc
    except EvalTimeoutError as exc:
        await db.rollback()
        raise _map_validator_error(exc) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "already_published", "message": str(exc)},
        ) from exc
    return SkillPublishResponse(
        skill=SkillRead.model_validate(skill),
        eval_report=report,
    )


@router.post("/{skill_id}/test", response_model=SkillEvalReport)
async def test_skill(
    skill_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillEvalReport:
    try:
        report = await run_skill_eval(skill_id, db)
    except SkillNotFoundError as exc:
        raise _map_validator_error(exc) from exc
    except EvalTimeoutError as exc:
        raise _map_validator_error(exc) from exc
    return report


@router.post("/{skill_id}/unpublish", response_model=SkillRead)
async def unpublish_skill(
    skill_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    service = SkillService(db)
    try:
        skill = await service.unpublish_skill(skill_id)
        await db.commit()
        await db.refresh(skill)
    except SkillNotFoundError as exc:
        raise _map_validator_error(exc) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "already_draft", "message": str(exc)},
        ) from exc
    return SkillRead.model_validate(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: uuid.UUID,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = SkillService(db)
    try:
        await service.delete_skill_draft(skill_id)
        await db.commit()
    except SkillNotFoundError as exc:
        raise _map_validator_error(exc) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "cannot_delete_published", "message": str(exc)},
        ) from exc
