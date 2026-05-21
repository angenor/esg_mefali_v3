"""Router parent `/api/admin/catalog` (F25, feature 044).

Concentre les endpoints transverses du catalogue admin :
- ``GET /summary`` — compteurs des 4 onglets,
- ``GET /export`` — export CSV streamé (US3).

et inclut les sous-routers spécialisés (``fund-intermediaries``).

Authentification ADMIN : héritée du router parent ``admin/router.py``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.financing import Fund, FundIntermediary, Intermediary
from app.models.offer import Offer
from app.models.user import User
from app.modules.admin.catalog_export_service import stream_csv
from app.modules.admin.fund_intermediaries_router import (
    router as fund_intermediaries_router,
)
from app.schemas.admin_catalog import (
    CatalogFundIntermediariesCounts,
    CatalogSummary,
    CatalogTabCounts,
)

router = APIRouter(dependencies=[Depends(get_current_admin)])

router.include_router(
    fund_intermediaries_router,
    prefix="/fund-intermediaries",
    tags=["admin-catalog-fund-intermediaries"],
)


async def _counts_by_status(
    db: AsyncSession,
    *,
    table_cls,
    status_col,
) -> CatalogTabCounts:
    """`SELECT count(*) GROUP BY publication_status` pour une entité catalogue."""
    stmt = select(status_col, func.count()).group_by(status_col)
    rows = (await db.execute(stmt)).all()
    by_status: dict[str, int] = {}
    total = 0
    for row in rows:
        key = row[0] if row[0] is not None else "unknown"
        value = int(row[1])
        by_status[str(key)] = value
        total += value
    return CatalogTabCounts(total=total, by_status=by_status)


@router.get("/summary", response_model=CatalogSummary, status_code=status.HTTP_200_OK)
async def get_catalog_summary(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> CatalogSummary:
    """Résumé global (compteurs des 4 onglets).

    D4 research : 4 COUNT(*) GROUP BY + 1 COUNT actif/expiré ; un seul aller-retour.
    """
    funds_counts = await _counts_by_status(
        db, table_cls=Fund, status_col=Fund.publication_status,
    )
    inter_counts = await _counts_by_status(
        db, table_cls=Intermediary, status_col=Intermediary.publication_status,
    )
    offers_counts = await _counts_by_status(
        db, table_cls=Offer, status_col=Offer.publication_status,
    )

    today = date.today()
    fi_stmt = select(
        func.count().label("total"),
        func.sum(
            case(
                (
                    (FundIntermediary.accredited_to.is_(None))
                    | (FundIntermediary.accredited_to >= today),
                    1,
                ),
                else_=0,
            )
        ).label("active"),
        func.sum(
            case(
                (FundIntermediary.accredited_to < today, 1),
                else_=0,
            )
        ).label("expired"),
    )
    fi_row = (await db.execute(fi_stmt)).first()
    fi_total = int(fi_row[0] or 0) if fi_row else 0
    fi_active = int(fi_row[1] or 0) if fi_row else 0
    fi_expired = int(fi_row[2] or 0) if fi_row else 0

    return CatalogSummary(
        funds=funds_counts,
        intermediaries=inter_counts,
        offers=offers_counts,
        fund_intermediaries=CatalogFundIntermediariesCounts(
            total=fi_total, active=fi_active, expired=fi_expired,
        ),
    )


# ---------- US3 — Export CSV unifié ----------


CatalogExportTab = Literal["funds", "intermediaries", "offers", "fund_intermediaries"]


def _validate_export_combo(
    tab: CatalogExportTab,
    *,
    publication_status: str | None,
    fund_type: str | None,
    status_filter: str | None,
) -> None:
    """Refuse les combinaisons incompatibles (cohérent avec les contrats)."""
    if tab in {"funds", "intermediaries", "offers"} and status_filter is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Le paramètre `status` ne s'applique qu'à l'onglet "
                "`fund_intermediaries`."
            ),
        )
    if tab != "funds" and fund_type is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="`fund_type` s'applique uniquement à l'onglet `funds`.",
        )
    if tab == "fund_intermediaries" and publication_status is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "`publication_status` ne s'applique pas à l'onglet "
                "`fund_intermediaries`. Utilisez `status`."
            ),
        )


@router.get("/export")
async def export_catalog(
    tab: CatalogExportTab = Query(..., description="Onglet à exporter"),
    q: str | None = Query(default=None),
    publication_status: str | None = Query(default=None),
    fund_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default=None),
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporte un onglet du catalogue au format CSV (UTF-8 + BOM)."""
    _validate_export_combo(
        tab,
        publication_status=publication_status,
        fund_type=fund_type,
        status_filter=status_filter,
    )
    filename = f"catalog-{tab}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        stream_csv(
            db,
            tab=tab,
            q=q,
            publication_status=publication_status,
            fund_type=fund_type,
            status_filter=status_filter,
            sort=sort,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
