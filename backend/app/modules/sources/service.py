"""Service applicatif pour le catalogue Source (F01).

CRUD + workflow 4-yeux + recherche full-text/embedding.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source, VerificationStatus
from app.schemas.source import SourceCreate, SourceUpdate

logger = logging.getLogger(__name__)


class FourEyesViolation(Exception):
    """Tentative de validation par le createur de la source."""


class InvalidStateTransition(Exception):
    """Transition d'etat illegale (par ex. valider une source non en pending)."""


class SourceNotFound(Exception):
    """La source n'existe pas dans le catalogue."""


class SourceService:
    """Service applicatif pour les Sources.

    Toutes les methodes mutantes acceptent `current_user_id` pour appliquer
    le workflow 4-yeux et tracer la creation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- Lecture ---------------------------------------------------------

    async def get_by_id(self, source_id: UUID) -> Source | None:
        """Retourner une source par ID, ou None si inexistante."""
        result = await self.db.execute(select(Source).where(Source.id == source_id))
        return result.scalar_one_or_none()

    async def get_verified(self, source_id: UUID) -> Source | None:
        """Retourner une source uniquement si verified, sinon None."""
        result = await self.db.execute(
            select(Source).where(
                Source.id == source_id,
                Source.verification_status == VerificationStatus.VERIFIED.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_verified(
        self,
        *,
        publisher: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Source], int]:
        """Lister les sources verifiees avec filtre publisher + recherche.

        Retourne (items, total).
        """
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        stmt = select(Source).where(
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )
        count_stmt = select(func.count(Source.id)).where(
            Source.verification_status == VerificationStatus.VERIFIED.value,
        )

        if publisher:
            stmt = stmt.where(Source.publisher == publisher)
            count_stmt = count_stmt.where(Source.publisher == publisher)
        if search:
            pattern = f"%{search.lower()}%"
            cond = or_(
                func.lower(Source.title).like(pattern),
                func.lower(Source.publisher).like(pattern),
                func.lower(func.coalesce(Source.section, "")).like(pattern),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        stmt = stmt.order_by(Source.date_publi.desc()).offset(offset).limit(page_size)

        items_result = await self.db.execute(stmt)
        total_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = total_result.scalar_one()
        return items, total

    async def list_admin(
        self,
        *,
        verification_status: str | None = None,
        publisher: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Source], int]:
        """Lister toutes les sources (admin) avec filtre statut + publisher."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        stmt = select(Source)
        count_stmt = select(func.count(Source.id))

        if verification_status:
            stmt = stmt.where(Source.verification_status == verification_status)
            count_stmt = count_stmt.where(
                Source.verification_status == verification_status,
            )
        if publisher:
            stmt = stmt.where(Source.publisher == publisher)
            count_stmt = count_stmt.where(Source.publisher == publisher)

        stmt = stmt.order_by(Source.created_at.desc()).offset(offset).limit(page_size)

        items_result = await self.db.execute(stmt)
        total_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = total_result.scalar_one()
        return items, total

    async def search(
        self,
        query: str,
        *,
        publisher: str | None = None,
        limit: int = 5,
    ) -> list[Source]:
        """Recherche text-based sur les sources verified.

        Limit dur a 5 (FR-010). Retourne les sources triees par pertinence
        (LIKE simple en fallback ; fulltext PostgreSQL/pgvector si dispo).
        """
        limit = max(1, min(5, limit))
        if not query or len(query.strip()) < 2:
            return []
        pattern = f"%{query.strip().lower()}%"
        stmt = select(Source).where(
            Source.verification_status == VerificationStatus.VERIFIED.value,
            or_(
                func.lower(Source.title).like(pattern),
                func.lower(Source.publisher).like(pattern),
                func.lower(func.coalesce(Source.section, "")).like(pattern),
            ),
        )
        if publisher:
            stmt = stmt.where(Source.publisher == publisher)
        stmt = stmt.order_by(Source.date_publi.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # -- Mutations -------------------------------------------------------

    async def create_source(
        self,
        payload: SourceCreate,
        *,
        current_user_id: UUID,
        account_id: UUID | None = None,
    ) -> Source:
        """Creer une source en statut draft.

        Le createur (captured_by) sera ulterieurement empeche de la valider
        (workflow 4-yeux).
        """
        source = Source(
            url=str(payload.url),
            title=payload.title,
            publisher=payload.publisher,
            version=payload.version,
            date_publi=payload.date_publi,
            page=payload.page,
            section=payload.section,
            captured_by=current_user_id,
            created_by_user_id=current_user_id,
            account_id=account_id,
            verification_status=VerificationStatus.DRAFT.value,
        )
        self.db.add(source)
        try:
            await self.db.flush()
        except IntegrityError as exc:  # pragma: no cover - duplicat URL
            await self.db.rollback()
            raise ValueError(
                "Une source avec cette URL existe deja dans le catalogue",
            ) from exc
        return source

    async def request_verification(self, source_id: UUID) -> Source:
        """Transition draft -> pending."""
        source = await self.get_by_id(source_id)
        if source is None:
            raise SourceNotFound(str(source_id))
        if source.verification_status != VerificationStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Impossible de demander la validation : statut actuel "
                f"{source.verification_status}",
            )
        source.verification_status = VerificationStatus.PENDING.value
        await self.db.flush()
        return source

    async def verify_source(
        self, source_id: UUID, *, current_user_id: UUID,
    ) -> Source:
        """Transition pending -> verified avec invariant 4-yeux."""
        source = await self.get_by_id(source_id)
        if source is None:
            raise SourceNotFound(str(source_id))
        if source.verification_status != VerificationStatus.PENDING.value:
            raise InvalidStateTransition(
                f"La source doit etre en statut 'pending' (actuel : "
                f"{source.verification_status})",
            )
        if source.captured_by == current_user_id:
            raise FourEyesViolation(
                "Le createur d'une source ne peut pas la valider lui-meme",
            )
        source.verified_by = current_user_id
        source.verified_at = datetime.now(timezone.utc)
        source.verification_status = VerificationStatus.VERIFIED.value
        await self.db.flush()
        return source

    async def mark_outdated(self, source_id: UUID, reason: str) -> Source:
        """Transition verified -> outdated avec motif obligatoire."""
        if not reason or not reason.strip():
            raise ValueError("La raison d'obsolescence est obligatoire")
        source = await self.get_by_id(source_id)
        if source is None:
            raise SourceNotFound(str(source_id))
        if source.verification_status != VerificationStatus.VERIFIED.value:
            raise InvalidStateTransition(
                f"Seule une source verifiee peut etre marquee obsolete (actuel : "
                f"{source.verification_status})",
            )
        source.outdated_reason = reason.strip()
        source.verification_status = VerificationStatus.OUTDATED.value
        await self.db.flush()
        return source

    async def update_source(
        self, source_id: UUID, payload: SourceUpdate,
    ) -> Source:
        """Modifier une source en statut draft uniquement."""
        source = await self.get_by_id(source_id)
        if source is None:
            raise SourceNotFound(str(source_id))
        if source.verification_status != VerificationStatus.DRAFT.value:
            raise InvalidStateTransition(
                "Seule une source en statut 'draft' peut etre modifiee",
            )
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(source, field, value)
        await self.db.flush()
        return source
