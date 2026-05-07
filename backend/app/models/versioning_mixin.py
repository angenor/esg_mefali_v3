"""F04 — Mixin SQLAlchemy pour le versioning catalogue.

Fournit les 4 colonnes ``version``, ``valid_from``, ``valid_to``,
``superseded_by`` à utiliser sur les 13 tables catalogue concernées.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class VersioningMixin:
    """Mixin ajoutant les 4 colonnes versioning F04 (sauf pour ``sources``).

    Pour la table ``sources`` qui possède déjà un champ métier ``version``,
    utiliser :class:`SourceVersioningMixin` qui ajoute ``catalog_version``
    à la place.
    """

    version: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="1.0", default="1.0",
    )
    valid_from: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(),
    )
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    @declared_attr
    def superseded_by(cls) -> Mapped[uuid.UUID | None]:
        """FK self-référentielle ; déclaration tardive pour résoudre __tablename__."""
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey(f"{cls.__tablename__}.id", ondelete="SET NULL"),
            nullable=True,
        )


class SourceVersioningMixin:
    """Variante du mixin pour ``sources`` (utilise ``catalog_version``).

    Le champ ``version`` métier de ``sources`` (ex 'v2.3', 'AR6') reste
    intouché. Le versioning F04 utilise ``catalog_version``.
    """

    catalog_version: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="1.0", default="1.0",
    )
    valid_from: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(),
    )
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    @declared_attr
    def superseded_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey(f"{cls.__tablename__}.id", ondelete="SET NULL"),
            nullable=True,
        )
