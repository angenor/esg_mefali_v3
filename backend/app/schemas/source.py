"""Schemas Pydantic v2 pour le catalogue de Sources (F01)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SourceBase(BaseModel):
    """Champs communs Source."""

    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    date_publi: date
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=200)


class SourceCreate(SourceBase):
    """Payload de creation d'une Source (admin only)."""

    pass


class SourceUpdate(BaseModel):
    """Payload de modification d'une Source en draft."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    publisher: str | None = Field(default=None, min_length=1, max_length=100)
    version: str | None = Field(default=None, min_length=1, max_length=50)
    date_publi: date | None = None
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=200)


class SourceVerify(BaseModel):
    """Payload de validation 4-yeux : aucun champ requis (signature implicite)."""

    pass


class SourceMarkOutdated(BaseModel):
    """Payload pour marquer une source obsolete avec raison."""

    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La raison ne peut pas etre vide")
        return v


class Source(SourceBase):
    """Reponse complete Source."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    captured_at: datetime
    captured_by: UUID
    verified_by: UUID | None = None
    verification_status: str
    verified_at: datetime | None = None
    outdated_reason: str | None = None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    @field_validator("url", mode="before")
    @classmethod
    def _coerce_url(cls, v: object) -> object:
        # Accepter un URL deja stocke en string depuis la BDD.
        return str(v) if v is not None else v


class SourceListItem(BaseModel):
    """Item compact pour la liste paginee."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    title: str
    publisher: str
    version: str
    date_publi: date
    page: int | None = None
    section: str | None = None
    verification_status: str


class SourceCitation(BaseModel):
    """Forme compacte renvoyee par cite_source / search_source au LLM."""

    id: UUID
    title: str
    publisher: str
    version: str
    url: str
    page: int | None = None
    section: str | None = None
    date_publi: date


class PaginatedSources(BaseModel):
    """Reponse paginee."""

    items: list[SourceListItem]
    total: int
    page: int
    page_size: int
