"""F20 — Schémas Pydantic v2 pour le module Resources."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.resource import (
    ResourceLanguage,
    ResourcePublicationStatus,
    ResourceType,
)

# Whitelist providers vidéo (FR-034).
VIDEO_PROVIDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^https://(www\.)?youtube\.com/embed/[\w\-]+"),
    re.compile(r"^https://(www\.)?youtu\.be/[\w\-]+"),
    re.compile(r"^https://(www\.)?vimeo\.com/\d+"),
    re.compile(r"^https://player\.vimeo\.com/video/\d+"),
    re.compile(r"^/uploads/videos/[\w\-./]+\.(mp4|webm)$"),
)

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_CONTENT_MD_CHARS = 50_000


def _validate_video_url(url: str) -> str:
    """Vérifie que l'URL vidéo est dans la whitelist."""
    if not any(p.match(url) for p in VIDEO_PROVIDER_PATTERNS):
        raise ValueError(
            "video_url must be a YouTube/Vimeo embed URL or a /uploads/videos/ path"
        )
    return url


class ResourceBase(BaseModel):
    """Champs communs aux schemas Create/Update/Read."""

    type: ResourceType
    title: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=500)
    content_md: str | None = Field(default=None, max_length=MAX_CONTENT_MD_CHARS)
    file_url: str | None = Field(default=None, max_length=500)
    video_url: str | None = Field(default=None, max_length=500)
    duration_seconds: int | None = Field(default=None, ge=0)
    category: list[str] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    language: ResourceLanguage = ResourceLanguage.FR
    source_id: UUID
    intermediary_id: UUID | None = None

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with hyphens (e.g. 'guide-esg-uemoa')"
            )
        return v

    @field_validator("video_url")
    @classmethod
    def _video_url_whitelist(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_video_url(v)

    @field_validator("target_audience")
    @classmethod
    def _audience_whitelist(cls, v: list[str]) -> list[str]:
        allowed = {"pme_micro", "pme_small", "pme_medium"}
        bad = [a for a in v if a not in allowed]
        if bad:
            raise ValueError(
                f"target_audience values must be in {sorted(allowed)}; got {bad}"
            )
        return v

    @model_validator(mode="after")
    def _type_field_consistency(self) -> "ResourceBase":
        # intermediary_guide ↔ intermediary_id
        if self.type == ResourceType.INTERMEDIARY_GUIDE:
            if self.intermediary_id is None:
                raise ValueError(
                    "intermediary_id is required for type='intermediary_guide'"
                )
        else:
            if self.intermediary_id is not None:
                raise ValueError(
                    "intermediary_id must be NULL for non-intermediary_guide types"
                )

        if self.type == ResourceType.TEMPLATE_DOC and not self.file_url:
            raise ValueError("file_url is required for type='template_doc'")

        if self.type == ResourceType.VIDEO and not self.video_url:
            raise ValueError("video_url is required for type='video'")

        return self


class ResourceCreateAdmin(ResourceBase):
    """Payload de création par un admin."""


class ResourceUpdateAdmin(BaseModel):
    """Payload de mise à jour partielle par un admin."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    content_md: str | None = Field(default=None, max_length=MAX_CONTENT_MD_CHARS)
    file_url: str | None = Field(default=None, max_length=500)
    video_url: str | None = Field(default=None, max_length=500)
    duration_seconds: int | None = Field(default=None, ge=0)
    category: list[str] | None = None
    target_audience: list[str] | None = None
    language: ResourceLanguage | None = None
    source_id: UUID | None = None

    @field_validator("video_url")
    @classmethod
    def _video_url_whitelist(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_video_url(v)

    @field_validator("target_audience")
    @classmethod
    def _audience_whitelist(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        allowed = {"pme_micro", "pme_small", "pme_medium"}
        bad = [a for a in v if a not in allowed]
        if bad:
            raise ValueError(
                f"target_audience values must be in {sorted(allowed)}; got {bad}"
            )
        return v


class SourceLite(BaseModel):
    """Forme compacte d'une source liée pour l'affichage public."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    publisher: str
    url: str | None = None
    version: str | None = None


class ResourceReadPublic(BaseModel):
    """Représentation publique d'une ressource."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: ResourceType
    title: str
    slug: str
    description: str
    content_md: str | None
    file_url: str | None
    video_url: str | None
    duration_seconds: int | None
    category: list[str]
    target_audience: list[str]
    language: ResourceLanguage
    source_id: UUID
    intermediary_id: UUID | None
    version: str
    valid_from: date | None
    valid_to: date | None
    publication_status: ResourcePublicationStatus
    view_count: int
    created_at: datetime
    updated_at: datetime


class ResourceReadAdmin(ResourceReadPublic):
    """Représentation admin (avec créateur/validateur)."""

    created_by: UUID
    verified_by: UUID | None
    superseded_by: UUID | None


class ResourceListItem(BaseModel):
    """Forme légère d'une ressource pour les listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: ResourceType
    title: str
    slug: str
    description: str
    category: list[str]
    target_audience: list[str]
    language: ResourceLanguage
    duration_seconds: int | None
    intermediary_id: UUID | None
    version: str
    publication_status: ResourcePublicationStatus
    view_count: int
    updated_at: datetime


class ResourceListResponse(BaseModel):
    """Réponse paginée."""

    items: list[ResourceListItem]
    total: int
    page: int
    limit: int


class ViewCountResponse(BaseModel):
    """Réponse à un POST /view : compteur incrémenté."""

    slug: str
    view_count: int


class RecommendedResourceItem(BaseModel):
    """Item retourné par le tool recommend_resources_for_user."""

    slug: str
    title: str
    type: ResourceType
    score: float
    why: str
