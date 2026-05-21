"""F25 — Service d'export CSV streamé pour `/api/admin/catalog/export`.

D3 research : streaming ligne-par-ligne avec BOM UTF-8 pour compatibilité
Excel FR. Un seul endpoint paramétrable (tab=funds|intermediaries|offers|
fund_intermediaries) ; les colonnes sont mappées par onglet.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from datetime import date
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financing import Fund, FundIntermediary, Intermediary
from app.models.offer import Offer
from app.modules.admin.catalog_helpers import escape_like_pattern

ExportTab = Literal["funds", "intermediaries", "offers", "fund_intermediaries"]

# BOM UTF-8 pour préfixer le flux et permettre à Excel FR de détecter l'encodage.
UTF8_BOM = b"\xef\xbb\xbf"


# Définitions des colonnes par onglet (clé = chemin, valeur = libellé).
FUNDS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("name", "name"),
    ("organization", "organization"),
    ("fund_type", "fund_type"),
    ("publication_status", "publication_status"),
    ("version", "version"),
    ("valid_from", "valid_from"),
    ("valid_to", "valid_to"),
    ("superseded_by", "superseded_by"),
    ("source_id", "source_id"),
)

INTERMEDIARIES_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("name", "name"),
    ("intermediary_type", "intermediary_type"),
    ("organization_type", "organization_type"),
    ("country", "country"),
    ("publication_status", "publication_status"),
    ("version", "version"),
    ("valid_from", "valid_from"),
    ("valid_to", "valid_to"),
    ("superseded_by", "superseded_by"),
    ("source_id", "source_id"),
)

OFFERS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("name", "name"),
    ("fund_id", "fund_id"),
    ("intermediary_id", "intermediary_id"),
    ("publication_status", "publication_status"),
    ("version", "version"),
    ("valid_from", "valid_from"),
    ("valid_to", "valid_to"),
    ("superseded_by", "superseded_by"),
    ("source_id", "source_id"),
)

FUND_INTERMEDIARIES_COLUMNS: tuple[tuple[str, str], ...] = (
    ("composite_id", "id"),
    ("fund_id", "fund_id"),
    ("fund_name", "fund_name"),
    ("intermediary_id", "intermediary_id"),
    ("intermediary_name", "intermediary_name"),
    ("accredited_from", "accredited_from"),
    ("accredited_to", "accredited_to"),
    ("is_active", "is_active"),
    ("max_amount_per_fund", "max_amount_per_fund"),
    ("accreditation_source_id", "accreditation_source_id"),
    ("version", "version"),
    ("valid_from", "valid_from"),
    ("valid_to", "valid_to"),
    ("superseded_by", "superseded_by"),
)


def _coerce(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):  # enum
        return str(value.value)
    return str(value)


def _format_row(row: dict[str, Any], columns: tuple[tuple[str, str], ...]) -> list[str]:
    return [_coerce(row.get(key)) for key, _ in columns]


def _headers(columns: tuple[tuple[str, str], ...]) -> list[str]:
    return [label for _, label in columns]


def _serialize_csv_row(values: list[str]) -> bytes:
    """Sérialise une ligne via le module csv (gestion correcte des guillemets)."""
    buf = io.StringIO()
    csv.writer(buf).writerow(values)
    return buf.getvalue().encode("utf-8")


async def _stream_funds(
    db: AsyncSession,
    *,
    q: str | None,
    publication_status: str | None,
    fund_type: str | None,
    sort: str | None = None,
) -> AsyncIterator[bytes]:
    yield UTF8_BOM
    yield _serialize_csv_row(_headers(FUNDS_COLUMNS))

    stmt = select(Fund)
    if q:
        pattern = f"%{escape_like_pattern(q.lower())}%"
        stmt = stmt.where(func.lower(Fund.name).like(pattern, escape="\\"))
    if publication_status:
        stmt = stmt.where(Fund.publication_status == publication_status)
    if fund_type:
        stmt = stmt.where(Fund.fund_type == fund_type)
    stmt = stmt.order_by(Fund.created_at.desc())

    result = await db.stream(stmt)
    async for row in result:
        fund: Fund = row[0]
        data = {
            "id": fund.id,
            "name": fund.name,
            "organization": getattr(fund, "organization", None),
            "fund_type": (
                fund.fund_type.value if hasattr(fund.fund_type, "value") else str(fund.fund_type)
            ) if fund.fund_type is not None else None,
            "publication_status": fund.publication_status,
            "version": getattr(fund, "version", None),
            "valid_from": getattr(fund, "valid_from", None),
            "valid_to": getattr(fund, "valid_to", None),
            "superseded_by": getattr(fund, "superseded_by", None),
            "source_id": getattr(fund, "source_id", None),
        }
        yield _serialize_csv_row(_format_row(data, FUNDS_COLUMNS))


async def _stream_intermediaries(
    db: AsyncSession,
    *,
    q: str | None,
    publication_status: str | None,
    sort: str | None = None,
) -> AsyncIterator[bytes]:
    yield UTF8_BOM
    yield _serialize_csv_row(_headers(INTERMEDIARIES_COLUMNS))

    stmt = select(Intermediary)
    if q:
        pattern = f"%{escape_like_pattern(q.lower())}%"
        stmt = stmt.where(func.lower(Intermediary.name).like(pattern, escape="\\"))
    if publication_status:
        stmt = stmt.where(Intermediary.publication_status == publication_status)
    stmt = stmt.order_by(Intermediary.created_at.desc())

    result = await db.stream(stmt)
    async for row in result:
        inter: Intermediary = row[0]
        data = {
            "id": inter.id,
            "name": inter.name,
            "intermediary_type": (
                inter.intermediary_type.value
                if hasattr(inter.intermediary_type, "value")
                else str(inter.intermediary_type)
            ) if inter.intermediary_type is not None else None,
            "organization_type": (
                inter.organization_type.value
                if hasattr(inter.organization_type, "value")
                else str(inter.organization_type)
            ) if inter.organization_type is not None else None,
            "country": inter.country,
            "publication_status": inter.publication_status,
            "version": getattr(inter, "version", None),
            "valid_from": getattr(inter, "valid_from", None),
            "valid_to": getattr(inter, "valid_to", None),
            "superseded_by": getattr(inter, "superseded_by", None),
            "source_id": getattr(inter, "source_id", None),
        }
        yield _serialize_csv_row(_format_row(data, INTERMEDIARIES_COLUMNS))


async def _stream_offers(
    db: AsyncSession,
    *,
    q: str | None,
    publication_status: str | None,
    sort: str | None = None,
) -> AsyncIterator[bytes]:
    yield UTF8_BOM
    yield _serialize_csv_row(_headers(OFFERS_COLUMNS))

    stmt = select(Offer)
    if publication_status:
        stmt = stmt.where(Offer.publication_status == publication_status)
    # Pas de recherche q côté offer (pas de name indexé pour MVP).
    stmt = stmt.order_by(Offer.created_at.desc())

    result = await db.stream(stmt)
    async for row in result:
        offer: Offer = row[0]
        data = {
            "id": offer.id,
            "name": getattr(offer, "name", None),
            "fund_id": offer.fund_id,
            "intermediary_id": offer.intermediary_id,
            "publication_status": offer.publication_status,
            "version": getattr(offer, "version", None),
            "valid_from": getattr(offer, "valid_from", None),
            "valid_to": getattr(offer, "valid_to", None),
            "superseded_by": getattr(offer, "superseded_by", None),
            "source_id": getattr(offer, "source_id", None),
        }
        yield _serialize_csv_row(_format_row(data, OFFERS_COLUMNS))


async def _stream_fund_intermediaries(
    db: AsyncSession,
    *,
    q: str | None,
    status_filter: str | None,
    sort: str | None = None,
) -> AsyncIterator[bytes]:
    today = date.today()
    yield UTF8_BOM
    yield _serialize_csv_row(_headers(FUND_INTERMEDIARIES_COLUMNS))

    stmt = (
        select(
            FundIntermediary,
            Fund.name.label("fund_name"),
            Intermediary.name.label("intermediary_name"),
        )
        .join(Fund, FundIntermediary.fund_id == Fund.id)
        .join(Intermediary, FundIntermediary.intermediary_id == Intermediary.id)
    )
    conditions = []
    if q:
        pattern = f"%{escape_like_pattern(q.lower())}%"
        conditions.append(
            or_(
                func.lower(Fund.name).like(pattern, escape="\\"),
                func.lower(Intermediary.name).like(pattern, escape="\\"),
            )
        )
    if status_filter == "active":
        conditions.append(
            or_(
                FundIntermediary.accredited_to.is_(None),
                FundIntermediary.accredited_to >= today,
            )
        )
    elif status_filter == "expired":
        conditions.append(FundIntermediary.accredited_to < today)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(FundIntermediary.accredited_from.desc())

    result = await db.stream(stmt)
    async for row in result:
        fi: FundIntermediary = row[0]
        fund_name = row[1]
        inter_name = row[2]
        is_active = fi.accredited_to is None or fi.accredited_to >= today
        money = fi.max_amount_per_fund_money
        data = {
            "composite_id": f"{fi.fund_id}:{fi.intermediary_id}",
            "fund_id": fi.fund_id,
            "fund_name": fund_name,
            "intermediary_id": fi.intermediary_id,
            "intermediary_name": inter_name,
            "accredited_from": fi.accredited_from,
            "accredited_to": fi.accredited_to,
            "is_active": "true" if is_active else "false",
            "max_amount_per_fund": (
                f"{money.amount} {money.currency}" if money else ""
            ),
            "accreditation_source_id": fi.accreditation_source_id,
            "version": getattr(fi, "version", None),
            "valid_from": getattr(fi, "valid_from", None),
            "valid_to": getattr(fi, "valid_to", None),
            "superseded_by": getattr(fi, "superseded_by", None),
        }
        yield _serialize_csv_row(_format_row(data, FUND_INTERMEDIARIES_COLUMNS))


async def stream_csv(
    db: AsyncSession,
    *,
    tab: ExportTab,
    q: str | None = None,
    publication_status: str | None = None,
    fund_type: str | None = None,
    status_filter: str | None = None,
    sort: str | None = None,
) -> AsyncIterator[bytes]:
    """Point d'entrée du service. Retourne un async iterator de bytes UTF-8."""
    if tab == "funds":
        async for chunk in _stream_funds(
            db,
            q=q,
            publication_status=publication_status,
            fund_type=fund_type,
            sort=sort,
        ):
            yield chunk
    elif tab == "intermediaries":
        async for chunk in _stream_intermediaries(
            db, q=q, publication_status=publication_status, sort=sort,
        ):
            yield chunk
    elif tab == "offers":
        async for chunk in _stream_offers(
            db, q=q, publication_status=publication_status, sort=sort,
        ):
            yield chunk
    elif tab == "fund_intermediaries":
        async for chunk in _stream_fund_intermediaries(
            db, q=q, status_filter=status_filter, sort=sort,
        ):
            yield chunk
    else:
        raise ValueError(f"Onglet invalide : {tab}")
