"""F20 — Service métier pour la bibliothèque Resources.

Couvre :
- Lecture publique : list, get_by_slug, get_intermediary_guide, view++.
- Recherche full-text simple (ILIKE sur title + description).
- Recommandations contextuelles (déterministe, sans ML).
- CRUD admin avec versioning F04 + 4-yeux F09.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financing import Intermediary
from app.models.resource import (
    Resource,
    ResourcePublicationStatus,
    ResourceType,
)
from app.models.source import Source, VerificationStatus
from app.modules.resources.exceptions import (
    IntermediaryNotFoundError,
    ResourceFourEyesViolationError,
    ResourceInvalidStatusError,
    ResourceNotFoundError,
    ResourceSlugConflictError,
    ResourceSourceNotVerifiedError,
)
from app.modules.resources.schemas import (
    ResourceCreateAdmin,
    ResourceUpdateAdmin,
)

logger = logging.getLogger(__name__)


def _bump_patch(version: str) -> str:
    """Incrémente la version semver patch+1 (1.0.0 → 1.0.1)."""
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        parts[2] = str(int(parts[2]) + 1)
    except ValueError:
        parts = ["1", "0", "1"]
    return ".".join(parts[:3])


class ResourceService:
    """Service applicatif pour les Resources."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read (public + admin)

    async def list_published(
        self,
        *,
        type_: str | None = None,
        category: str | None = None,
        language: str | None = None,
        intermediary_id: uuid.UUID | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Resource], int]:
        """Liste les ressources publiées, non-supersédées, paginées."""
        stmt = select(Resource).where(
            Resource.publication_status == ResourcePublicationStatus.PUBLISHED.value,
            Resource.superseded_by.is_(None),
        )
        count_stmt = select(func.count()).select_from(Resource).where(
            Resource.publication_status == ResourcePublicationStatus.PUBLISHED.value,
            Resource.superseded_by.is_(None),
        )
        if type_:
            stmt = stmt.where(Resource.type == type_)
            count_stmt = count_stmt.where(Resource.type == type_)
        if language:
            stmt = stmt.where(Resource.language == language)
            count_stmt = count_stmt.where(Resource.language == language)
        if intermediary_id is not None:
            stmt = stmt.where(Resource.intermediary_id == intermediary_id)
            count_stmt = count_stmt.where(Resource.intermediary_id == intermediary_id)
        if q:
            ilike = f"%{q}%"
            stmt = stmt.where(
                or_(Resource.title.ilike(ilike), Resource.description.ilike(ilike))
            )
            count_stmt = count_stmt.where(
                or_(Resource.title.ilike(ilike), Resource.description.ilike(ilike))
            )

        offset = max(0, (page - 1) * limit)
        stmt = stmt.order_by(Resource.updated_at.desc()).offset(offset).limit(limit)

        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())
        total_res = await self.db.execute(count_stmt)
        total = int(total_res.scalar_one() or 0)

        # Filtrage post-DB sur category (JSONB array, fallback portable).
        if category:
            items = [r for r in items if category in (r.category or [])]

        return items, total

    async def get_by_slug(self, slug: str) -> Resource | None:
        """Retourne la ressource publiée pour ce slug (ou None)."""
        stmt = select(Resource).where(
            Resource.slug == slug,
            Resource.publication_status == ResourcePublicationStatus.PUBLISHED.value,
            Resource.superseded_by.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, resource_id: uuid.UUID) -> Resource:
        """Retourne la ressource par id (admin)."""
        stmt = select(Resource).where(Resource.id == resource_id)
        result = await self.db.execute(stmt)
        resource = result.scalar_one_or_none()
        if resource is None:
            raise ResourceNotFoundError(resource_id)
        return resource

    async def get_intermediary_guide(
        self, intermediary_id: uuid.UUID
    ) -> Resource | None:
        """Retourne la fiche pratique publiée pour un intermédiaire."""
        stmt = select(Resource).where(
            Resource.type == ResourceType.INTERMEDIARY_GUIDE.value,
            Resource.intermediary_id == intermediary_id,
            Resource.publication_status == ResourcePublicationStatus.PUBLISHED.value,
            Resource.superseded_by.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_view_count(self, slug: str) -> int:
        """Incrémente atomiquement view_count. Retourne le nouveau compteur."""
        stmt = (
            update(Resource)
            .where(
                Resource.slug == slug,
                Resource.publication_status
                == ResourcePublicationStatus.PUBLISHED.value,
                Resource.superseded_by.is_(None),
            )
            .values(view_count=Resource.view_count + 1)
            .returning(Resource.view_count)
        )
        result = await self.db.execute(stmt)
        new_count = result.scalar_one_or_none()
        if new_count is None:
            raise ResourceNotFoundError(slug)
        await self.db.flush()
        return int(new_count)

    async def search_resources(
        self,
        query: str,
        *,
        type_: str | None = None,
        category: str | None = None,
        limit: int = 10,
    ) -> list[Resource]:
        """Recherche simple par mot-clé pour les tools LangChain."""
        items, _ = await self.list_published(
            type_=type_, category=category, q=query, page=1, limit=limit
        )
        return items

    async def get_related(
        self, resource: Resource, limit: int = 3
    ) -> list[Resource]:
        """Retourne les ressources publiées partageant au moins une catégorie."""
        if not resource.category:
            return []
        items, _ = await self.list_published(page=1, limit=50)
        result: list[Resource] = []
        for r in items:
            if r.id == resource.id:
                continue
            if set(r.category or []) & set(resource.category):
                result.append(r)
            if len(result) >= limit:
                break
        return result

    async def get_recommendations(
        self,
        *,
        scores: dict[str, Any] | None = None,
        active_module: str | None = None,
        company_size: str | None = None,
        language: str = "fr",
        limit: int = 5,
    ) -> list[Resource]:
        """Recommandation déterministe.

        Scoring :
          +3 par catégorie matchant active_module ou pillar bas (< 50).
          +2 par audience matchant company_size.
          +1 × view_count_normalized.
        """
        items, _ = await self.list_published(language=language, page=1, limit=200)
        if not items:
            return []

        target_categories: set[str] = set()
        if active_module:
            target_categories.add(active_module)
        scores = scores or {}
        for pillar in ("environment", "social", "governance"):
            val = scores.get(f"{pillar}_score")
            if isinstance(val, (int, float)) and val < 50:
                target_categories.add(pillar)

        max_views = max((r.view_count for r in items), default=1) or 1

        def score_for(r: Resource) -> float:
            s = 0.0
            cats = set(r.category or [])
            s += 3 * len(cats & target_categories)
            if company_size and company_size in (r.target_audience or []):
                s += 2
            s += (r.view_count or 0) / max_views
            return s

        ranked = sorted(items, key=score_for, reverse=True)
        non_zero = [r for r in ranked if score_for(r) > 0]
        if non_zero:
            return non_zero[:limit]
        # Fallback : top view_count
        return sorted(items, key=lambda r: r.view_count or 0, reverse=True)[: min(3, limit)]

    # ------------------------------------------------------------------
    # Write (admin)

    async def _slug_exists(self, slug: str) -> bool:
        stmt = select(Resource.id).where(Resource.slug == slug).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _ensure_source_verified(self, source_id: uuid.UUID) -> None:
        stmt = select(Source).where(Source.id == source_id)
        result = await self.db.execute(stmt)
        source = result.scalar_one_or_none()
        if source is None:
            raise ResourceSourceNotVerifiedError(source_id, "missing")
        if source.verification_status != VerificationStatus.VERIFIED.value:
            raise ResourceSourceNotVerifiedError(
                source_id, source.verification_status
            )

    async def _ensure_intermediary_exists(
        self, intermediary_id: uuid.UUID
    ) -> None:
        stmt = select(Intermediary.id).where(Intermediary.id == intermediary_id)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise IntermediaryNotFoundError(intermediary_id)

    async def create_resource(
        self,
        payload: ResourceCreateAdmin,
        *,
        creator_id: uuid.UUID,
    ) -> Resource:
        """Crée une ressource en statut draft."""
        if await self._slug_exists(payload.slug):
            raise ResourceSlugConflictError(payload.slug)
        # Source must exist (verification check enforced at publish, soft at create).
        await self._ensure_source_verified(payload.source_id)
        if payload.intermediary_id is not None:
            await self._ensure_intermediary_exists(payload.intermediary_id)

        body = payload.model_dump(mode="python")
        # Normaliser enums en strings DB.
        if hasattr(body.get("type"), "value"):
            body["type"] = body["type"].value
        if hasattr(body.get("language"), "value"):
            body["language"] = body["language"].value

        resource = Resource(
            **body,
            created_by=creator_id,
            publication_status=ResourcePublicationStatus.DRAFT.value,
        )
        self.db.add(resource)
        await self.db.flush()
        logger.info(
            "[resources.service] created resource slug=%s id=%s", resource.slug, resource.id
        )
        return resource

    async def update_resource(
        self,
        resource_id: uuid.UUID,
        payload: ResourceUpdateAdmin,
        *,
        editor_id: uuid.UUID,
    ) -> Resource:
        """Met à jour une ressource.

        - draft → in-place.
        - published → crée une nouvelle version draft (patch+1).
        """
        resource = await self.get_by_id(resource_id)

        if payload.source_id is not None:
            await self._ensure_source_verified(payload.source_id)

        body = payload.model_dump(exclude_unset=True, mode="python")
        if hasattr(body.get("language"), "value"):
            body["language"] = body["language"].value

        if resource.publication_status == ResourcePublicationStatus.PUBLISHED.value:
            return await self._create_new_draft_version(resource, body, editor_id)

        # in-place draft update
        for key, value in body.items():
            setattr(resource, key, value)
        await self.db.flush()
        return resource

    async def _create_new_draft_version(
        self,
        published: Resource,
        body: dict[str, Any],
        editor_id: uuid.UUID,
    ) -> Resource:
        new_version = _bump_patch(published.version)
        # Slug doit rester unique : suffixer par version pour la nouvelle draft.
        new_slug = f"{published.slug}-v{new_version.replace('.', '-')}"
        # Si collision (très improbable), incrémenter encore.
        attempt = 0
        while await self._slug_exists(new_slug) and attempt < 5:
            attempt += 1
            new_slug = f"{new_slug}-{attempt}"

        new_resource = Resource(
            type=published.type,
            title=body.get("title", published.title),
            slug=new_slug,
            description=body.get("description", published.description),
            content_md=body.get("content_md", published.content_md),
            file_url=body.get("file_url", published.file_url),
            video_url=body.get("video_url", published.video_url),
            duration_seconds=body.get("duration_seconds", published.duration_seconds),
            category=body.get("category", list(published.category or [])),
            target_audience=body.get(
                "target_audience", list(published.target_audience or [])
            ),
            language=body.get("language", published.language),
            source_id=body.get("source_id", published.source_id),
            intermediary_id=published.intermediary_id,
            version=new_version,
            publication_status=ResourcePublicationStatus.DRAFT.value,
            created_by=editor_id,
        )
        self.db.add(new_resource)
        await self.db.flush()
        logger.info(
            "[resources.service] created draft version=%s for parent=%s",
            new_version,
            published.id,
        )
        return new_resource

    async def publish_resource(
        self,
        resource_id: uuid.UUID,
        *,
        verifier_id: uuid.UUID,
    ) -> Resource:
        """Publie une ressource draft (4-yeux + source verified)."""
        resource = await self.get_by_id(resource_id)
        if resource.publication_status != ResourcePublicationStatus.DRAFT.value:
            raise ResourceInvalidStatusError(resource.publication_status, "publish")
        if verifier_id == resource.created_by:
            raise ResourceFourEyesViolationError()
        await self._ensure_source_verified(resource.source_id)

        # Si une autre ressource est déjà publiée avec le même slug "logique"
        # (intermediary_guide pour le même intermédiaire), la superseder.
        if resource.type == ResourceType.INTERMEDIARY_GUIDE.value and resource.intermediary_id:
            stmt = select(Resource).where(
                Resource.type == ResourceType.INTERMEDIARY_GUIDE.value,
                Resource.intermediary_id == resource.intermediary_id,
                Resource.publication_status
                == ResourcePublicationStatus.PUBLISHED.value,
                Resource.superseded_by.is_(None),
                Resource.id != resource.id,
            )
            existing = (await self.db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                existing.superseded_by = resource.id
                existing.valid_to = date.today()

        resource.publication_status = ResourcePublicationStatus.PUBLISHED.value
        resource.verified_by = verifier_id
        resource.valid_from = date.today()
        await self.db.flush()
        logger.info(
            "[resources.service] published resource slug=%s id=%s",
            resource.slug,
            resource.id,
        )
        return resource

    async def archive_resource(
        self,
        resource_id: uuid.UUID,
        *,
        editor_id: uuid.UUID,
    ) -> Resource:
        resource = await self.get_by_id(resource_id)
        resource.publication_status = ResourcePublicationStatus.ARCHIVED.value
        resource.valid_to = date.today()
        await self.db.flush()
        return resource

    async def delete_resource(self, resource_id: uuid.UUID) -> None:
        """Hard delete réservé aux drafts."""
        resource = await self.get_by_id(resource_id)
        if resource.publication_status != ResourcePublicationStatus.DRAFT.value:
            raise ResourceInvalidStatusError(
                resource.publication_status, "delete"
            )
        await self.db.delete(resource)
        await self.db.flush()

    # ------------------------------------------------------------------
    # Admin list (no publication filter)

    async def admin_list(
        self,
        *,
        type_: str | None = None,
        status: str | None = None,
        language: str | None = None,
        q: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Resource], int]:
        stmt = select(Resource)
        count_stmt = select(func.count()).select_from(Resource)
        if type_:
            stmt = stmt.where(Resource.type == type_)
            count_stmt = count_stmt.where(Resource.type == type_)
        if status:
            stmt = stmt.where(Resource.publication_status == status)
            count_stmt = count_stmt.where(Resource.publication_status == status)
        if language:
            stmt = stmt.where(Resource.language == language)
            count_stmt = count_stmt.where(Resource.language == language)
        if q:
            ilike = f"%{q}%"
            stmt = stmt.where(
                or_(Resource.title.ilike(ilike), Resource.description.ilike(ilike))
            )
            count_stmt = count_stmt.where(
                or_(Resource.title.ilike(ilike), Resource.description.ilike(ilike))
            )
        offset = max(0, (page - 1) * limit)
        stmt = stmt.order_by(Resource.updated_at.desc()).offset(offset).limit(limit)
        items_res = await self.db.execute(stmt)
        total_res = await self.db.execute(count_stmt)
        return list(items_res.scalars().all()), int(total_res.scalar_one() or 0)
