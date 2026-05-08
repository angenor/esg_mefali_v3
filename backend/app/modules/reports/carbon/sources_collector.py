"""F21 — Collecte des sources F01 mobilisées par le rapport carbone.

Stratégie :
1. Sources rattachées aux ``CarbonEmissionEntry.source_id`` du bilan (F17).
2. Sources rattachées aux ``EmissionFactor.source_id`` des facteurs utilisés.
3. Sources citées par l'agent IA via ``tool_call_logs(tool_name='cite_source')``
   (filtre conversation_id si disponible).

Dédup par ``source_id`` en préservant l'ordre d'apparition. Numérotation
``[1], [2], ...`` stable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class NumberedSource:
    """Source numérotée pour l'annexe « Sources et références »."""

    index: int
    source_id: uuid.UUID
    title: str
    publisher: str | None
    version: str | None
    date_publi: str  # ISO ou ""
    page: int | None
    section: str | None
    url: str | None


async def collect_sources(
    db: AsyncSession,
    assessment_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> list[NumberedSource]:
    """Collecter et numéroter toutes les sources F01 mobilisées.

    Args:
        db: session SQLAlchemy async.
        assessment_id: ID du ``CarbonAssessment``.
        conversation_id: optionnel ; si fourni, ajoute les sources citées
            par l'agent IA durant la conversation associée.
    """
    from app.models.source import Source, VerificationStatus

    ordered_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    def _add(sid: uuid.UUID | str | None) -> None:
        if sid is None:
            return
        try:
            sid_uuid = uuid.UUID(str(sid))
        except (ValueError, TypeError):
            return
        if sid_uuid in seen:
            return
        seen.add(sid_uuid)
        ordered_ids.append(sid_uuid)

    # 1. CarbonEmissionEntry.source_id + factor.source_id (best-effort).
    try:
        from app.models.carbon import CarbonEmissionEntry

        entries_stmt = select(CarbonEmissionEntry).where(
            CarbonEmissionEntry.assessment_id == assessment_id
        )
        result = await db.execute(entries_stmt)
        entries = result.scalars().all()

        factor_ids: list[uuid.UUID] = []
        for entry in entries:
            _add(getattr(entry, "source_id", None))
            fid = getattr(entry, "factor_id", None)
            if fid:
                try:
                    factor_ids.append(uuid.UUID(str(fid)))
                except (ValueError, TypeError):
                    continue

        if factor_ids:
            try:
                from app.models.emission_factor import EmissionFactor  # type: ignore

                ef_result = await db.execute(
                    select(EmissionFactor).where(EmissionFactor.id.in_(factor_ids))
                )
                for ef in ef_result.scalars().all():
                    _add(getattr(ef, "source_id", None))
            except Exception:  # pragma: no cover (modèle optionnel)
                pass
    except Exception:  # pragma: no cover
        pass

    # 2. tool_call_logs(cite_source) liés à la conversation.
    if conversation_id is not None:
        try:
            from app.models.tool_call_log import ToolCallLog

            tcl_stmt = select(ToolCallLog).where(
                ToolCallLog.conversation_id == conversation_id,
                ToolCallLog.tool_name == "cite_source",
            )
            tcl_result = await db.execute(tcl_stmt)
            for log in tcl_result.scalars().all():
                args = getattr(log, "arguments", None) or {}
                if isinstance(args, dict):
                    _add(args.get("source_id"))
        except Exception:  # pragma: no cover
            pass

    if not ordered_ids:
        return []

    # 3. Charger les Source vérifiées et numéroter.
    src_result = await db.execute(
        select(Source).where(
            Source.id.in_(ordered_ids),
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
    )
    by_id = {s.id: s for s in src_result.scalars().all()}

    out: list[NumberedSource] = []
    index = 1
    for sid in ordered_ids:
        src = by_id.get(sid)
        if src is None:
            continue
        out.append(
            NumberedSource(
                index=index,
                source_id=src.id,
                title=src.title,
                publisher=src.publisher,
                version=src.version,
                date_publi=src.date_publi.isoformat() if src.date_publi else "",
                page=src.page,
                section=src.section,
                url=src.url,
            )
        )
        index += 1
    return out


__all__ = ["NumberedSource", "collect_sources"]
