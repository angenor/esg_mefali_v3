"""Sous-router admin `/api/admin/catalog/fund-intermediaries` (F25 / feature 044).

Lecture seule. ADMIN only (hérité du router parent). Expose la table
``fund_intermediaries`` (F07) sous deux endpoints :

- ``GET /`` — liste paginée conditionnelle (FR-013a, seuil 2000)
- ``GET /{id}`` — fiche détaillée avec source jointe (id composite
  ``"{fund_id}:{intermediary_id}"``)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.financing import Fund, FundIntermediary, Intermediary
from app.models.source import Source
from app.models.user import User
from app.modules.admin.catalog_helpers import (
    compute_has_incoherence,
    escape_like_pattern,
)
from app.schemas.admin_catalog import (
    FundIntermediaryDetail,
    FundIntermediaryRow,
    PaginatedListResponse,
    SourceRef,
)
from app.core.money import Money

logger = logging.getLogger(__name__)

router = APIRouter()


SortLiteral = Literal[
    "accredited_from_desc",
    "accredited_from_asc",
    "updated_at_desc",
    "updated_at_asc",
]


FULL_LIST_THRESHOLD = 2000


def _parse_composite_id(composite_id: str) -> tuple[UUID, UUID]:
    """Parse ``"{fund_id}:{intermediary_id}"`` ; lève 422 sur format invalide."""
    if ":" not in composite_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identifiant composite invalide : format attendu '<fund_id>:<intermediary_id>'",
        )
    parts = composite_id.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identifiant composite invalide",
        )
    try:
        return UUID(parts[0]), UUID(parts[1])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identifiant composite invalide : UUID mal formé",
        ) from exc


def _derive_updated_at(fi: FundIntermediary) -> datetime:
    """`fund_intermediaries` n'a pas de colonne ``updated_at`` ; on
    dérive un timestamp depuis ``valid_from`` (VersioningMixin) qui
    représente la dernière mise à jour catalogue effective.
    """
    base = fi.valid_from if fi.valid_from is not None else date.today()
    return datetime.combine(base, time.min, tzinfo=timezone.utc)


def _row_to_schema(
    fi: FundIntermediary,
    fund_name: str,
    intermediary_name: str,
) -> FundIntermediaryRow:
    """Sérialise une liaison en `FundIntermediaryRow` (vue liste)."""
    today = date.today()
    is_active = fi.accredited_to is None or fi.accredited_to >= today
    return FundIntermediaryRow(
        id=f"{fi.fund_id}:{fi.intermediary_id}",
        fund_id=fi.fund_id,
        fund_name=fund_name,
        intermediary_id=fi.intermediary_id,
        intermediary_name=intermediary_name,
        accredited_from=fi.accredited_from,
        accredited_to=fi.accredited_to,
        is_active=is_active,
        max_amount_per_fund_money=fi.max_amount_per_fund_money,
        has_source=fi.accreditation_source_id is not None,
        has_incoherence=compute_has_incoherence(fi, "fund_intermediary"),
        updated_at=_derive_updated_at(fi),
    )


@router.get(
    "",
    response_model=PaginatedListResponse[FundIntermediaryRow],
    status_code=status.HTTP_200_OK,
)
async def list_fund_intermediaries(
    q: str | None = Query(default=None, description="Recherche sur nom fonds/intermédiaire"),
    status_filter: Literal["active", "expired", "all"] = Query(
        default="all", alias="status",
    ),
    fund_id: UUID | None = Query(default=None),
    intermediary_id: UUID | None = Query(default=None),
    sort: SortLiteral = Query(default="accredited_from_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=25, le=100),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedListResponse[FundIntermediaryRow]:
    """Liste paginée (ou complète si total<2000) des liaisons fonds × intermédiaires."""
    today = date.today()

    # Jointures pour exposer fund.name + intermediary.name (recherche + affichage).
    base_stmt = (
        select(
            FundIntermediary,
            Fund.name.label("fund_name"),
            Intermediary.name.label("intermediary_name"),
        )
        .join(Fund, FundIntermediary.fund_id == Fund.id)
        .join(Intermediary, FundIntermediary.intermediary_id == Intermediary.id)
    )

    conditions = []
    if fund_id is not None:
        conditions.append(FundIntermediary.fund_id == fund_id)
    if intermediary_id is not None:
        conditions.append(FundIntermediary.intermediary_id == intermediary_id)

    if status_filter == "active":
        conditions.append(
            or_(
                FundIntermediary.accredited_to.is_(None),
                FundIntermediary.accredited_to >= today,
            )
        )
    elif status_filter == "expired":
        conditions.append(FundIntermediary.accredited_to < today)

    if q:
        pattern = f"%{escape_like_pattern(q.lower())}%"
        conditions.append(
            or_(
                func.lower(Fund.name).like(pattern, escape="\\"),
                func.lower(Intermediary.name).like(pattern, escape="\\"),
            )
        )

    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    # Count avant ordering/limit.
    count_stmt = (
        select(func.count())
        .select_from(FundIntermediary)
        .join(Fund, FundIntermediary.fund_id == Fund.id)
        .join(Intermediary, FundIntermediary.intermediary_id == Intermediary.id)
    )
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar_one() or 0

    # Ordering. `fund_intermediaries` n'a pas d'``updated_at`` ; on utilise
    # ``valid_from`` (VersioningMixin) comme proxy temporel.
    if sort == "accredited_from_desc":
        base_stmt = base_stmt.order_by(FundIntermediary.accredited_from.desc())
    elif sort == "accredited_from_asc":
        base_stmt = base_stmt.order_by(FundIntermediary.accredited_from.asc())
    elif sort == "updated_at_desc":
        base_stmt = base_stmt.order_by(FundIntermediary.valid_from.desc())
    else:  # updated_at_asc
        base_stmt = base_stmt.order_by(FundIntermediary.valid_from.asc())

    # Pagination conditionnelle (FR-013a).
    paginated = total >= FULL_LIST_THRESHOLD
    if paginated:
        base_stmt = base_stmt.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(base_stmt)).all()
    items = [_row_to_schema(row[0], row[1], row[2]) for row in rows]

    return PaginatedListResponse[FundIntermediaryRow](
        items=items,
        total=total,
        page=page if paginated else 1,
        page_size=page_size if paginated else max(total, 1),
        paginated=paginated,
    )


@router.get(
    "/{composite_id}",
    response_model=FundIntermediaryDetail,
    status_code=status.HTTP_200_OK,
)
async def get_fund_intermediary(
    composite_id: str,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> FundIntermediaryDetail:
    """Fiche détaillée d'une liaison ``{fund_id}:{intermediary_id}``."""
    fund_uuid, intermediary_uuid = _parse_composite_id(composite_id)

    stmt = (
        select(
            FundIntermediary,
            Fund.name.label("fund_name"),
            Intermediary.name.label("intermediary_name"),
            Source,
        )
        .join(Fund, FundIntermediary.fund_id == Fund.id)
        .join(Intermediary, FundIntermediary.intermediary_id == Intermediary.id)
        .outerjoin(Source, FundIntermediary.accreditation_source_id == Source.id)
        .where(
            and_(
                FundIntermediary.fund_id == fund_uuid,
                FundIntermediary.intermediary_id == intermediary_uuid,
            )
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Liaison introuvable")

    fi: FundIntermediary = row[0]
    fund_name: str = row[1]
    intermediary_name: str = row[2]
    source: Source | None = row[3]

    today = date.today()
    is_active = fi.accredited_to is None or fi.accredited_to >= today

    source_ref: SourceRef | None = None
    if source is not None:
        source_ref = SourceRef(
            id=source.id,
            title=source.title,
            url=source.url,
            status=source.verification_status,  # type: ignore[arg-type]
        )

    return FundIntermediaryDetail(
        id=f"{fi.fund_id}:{fi.intermediary_id}",
        fund_id=fi.fund_id,
        fund_name=fund_name,
        intermediary_id=fi.intermediary_id,
        intermediary_name=intermediary_name,
        accredited_from=fi.accredited_from,
        accredited_to=fi.accredited_to,
        is_active=is_active,
        max_amount_per_fund_money=fi.max_amount_per_fund_money,
        has_source=source is not None,
        has_incoherence=compute_has_incoherence(fi, "fund_intermediary"),
        updated_at=_derive_updated_at(fi),
        accreditation_source=source_ref,
        fund_link=f"/admin/catalog/funds/{fi.fund_id}",
        intermediary_link=f"/admin/catalog/intermediaries/{fi.intermediary_id}",
        created_at=_derive_updated_at(fi),
        version=fi.version if hasattr(fi, "version") else None,
        superseded_by=fi.superseded_by if hasattr(fi, "superseded_by") else None,
    )
