"""Service métier de l'extension Chrome (F24).

Implémente :
- ``match_url`` : matching d'une URL contre les ``url_patterns`` des Fund
  + Intermediary, sur les Offers ``publication_status='published'`` uniquement.
- ``list_active_applications`` : liste des candidatures actives d'un user.
- ``build_profile_snapshot`` : profil minimal (sector, country) + 3 derniers
  projets actifs.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.application import (
    ApplicationStatus,
    FundApplication,
    STATUS_LABELS,
)
from app.models.company import CompanyProfile
from app.models.financing import Fund, Intermediary
from app.models.offer import Offer
from app.models.project import Project
from app.modules.extension.schemas import (
    ActiveApplicationItem,
    DetectResponse,
    ProfileSnapshot,
    ProjectSnapshotItem,
)

logger = logging.getLogger(__name__)


# Statuts considérés comme « inactifs » pour le dashboard extension.
INACTIVE_STATUSES: set[str] = {
    ApplicationStatus.accepted.value,
    ApplicationStatus.rejected.value,
    "approved",  # statuts hypothétiques mentionnés au contrat
    "disbursed",
    "cancelled",
}

# Statuts éligibles pour la mappe FR (sécurité belt-and-braces).
EXTENSION_STATUS_LABEL_FR: dict[str, str] = {
    "draft": "Brouillon",
    "preparing_documents": "Préparation",
    "preparing": "Préparation",
    "in_progress": "Rédaction en cours",
    "review": "Relecture",
    "ready_for_intermediary": "Prêt pour l'intermédiaire",
    "ready_for_fund": "Prêt pour soumission au fonds",
    "submitted_to_intermediary": "Soumise à l'intermédiaire",
    "under_review_intermediary": "En revue intermédiaire",
    "submitted_to_fund": "Soumise au fonds",
    "under_review_fund": "En revue fonds",
    "under_review": "En cours d'examen",
    "accepted": "Acceptée",
    "rejected": "Rejetée",
}


def _label_fr(status: str) -> str:
    """Retourne le libellé FR pour un statut applicatif."""
    return (
        EXTENSION_STATUS_LABEL_FR.get(status)
        or STATUS_LABELS.get(status)
        or status
    )


def _build_deep_link(application_id: uuid.UUID) -> str:
    """Construit l'URL deep-link vers l'app principale.

    Utilise ``settings.app_public_url`` si défini, sinon fallback localhost.
    """
    base = getattr(settings, "app_public_url", None) or "http://localhost:3000"
    return f"{base.rstrip('/')}/applications/{application_id}"


def _safe_compile(pattern: str) -> re.Pattern[str] | None:
    """Compile un pattern regex, retourne None si invalide (log warning)."""
    try:
        return re.compile(pattern)
    except re.error as exc:
        logger.warning(
            "F24: pattern regex invalide ignoré (pattern=%r, error=%s)",
            pattern,
            exc,
        )
        return None


def _extract_patterns(raw: Any) -> list[str]:
    """Extrait la liste des chaînes de patterns depuis une valeur ``url_patterns``.

    Accepte :
    - ``[]`` (vide)
    - ``[{"pattern": "...", "scope": "..."}]``
    - ``[{"pattern": "..."}]`` (scope optionnel)
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("pattern"), str):
            out.append(item["pattern"])
        elif isinstance(item, str):
            out.append(item)
    return out


async def match_url(db: AsyncSession, url: str) -> DetectResponse | None:
    """Cherche une offre publiée dont un url_pattern (fund OU intermediary) matche.

    Logique :
    1. Charge toutes les Offers ``publication_status='published'``.
    2. Pour chaque offre, concatène ``fund.url_patterns`` ∪
       ``intermediary.url_patterns``.
    3. Compile + teste contre l'URL fournie.
    4. Si plusieurs offres matchent : priorité à intermediary.code='DIRECT',
       puis tri par created_at croissant pour déterminisme.
    5. Renvoie ``DetectResponse(confidence=1.0)`` ou ``None``.
    """
    stmt = (
        select(Offer)
        .options(
            selectinload(Offer.fund),
            selectinload(Offer.intermediary),
        )
        .where(Offer.publication_status == "published")
        .where(Offer.is_active.is_(True))
    )
    result = await db.execute(stmt)
    offers = list(result.scalars().all())

    candidates: list[Offer] = []
    for offer in offers:
        fund_patterns = _extract_patterns(
            offer.fund.url_patterns if offer.fund else None
        )
        inter_patterns = _extract_patterns(
            offer.intermediary.url_patterns if offer.intermediary else None
        )
        all_patterns = fund_patterns + inter_patterns
        for raw in all_patterns:
            compiled = _safe_compile(raw)
            if compiled is None:
                continue
            if compiled.search(url):
                candidates.append(offer)
                break  # un match suffit pour cette offre

    if not candidates:
        return None

    # Priorité 1 : intermediary.code='DIRECT'
    direct_candidates = [
        o for o in candidates if (o.intermediary and o.intermediary.code == "DIRECT")
    ]
    if direct_candidates:
        winner = sorted(direct_candidates, key=lambda o: o.created_at)[0]
    else:
        winner = sorted(candidates, key=lambda o: o.created_at)[0]

    return DetectResponse(
        offer_id=winner.id,
        offer_name=winner.name,
        source_id=winner.source_id,
        confidence=1.0,
    )


async def list_active_applications(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ActiveApplicationItem]:
    """Liste les candidatures actives (statuts non finaux) d'un utilisateur.

    Filtre : statut hors ``INACTIVE_STATUSES``. Tri ``updated_at DESC``,
    limite 50. Mapping ``status_label_fr`` via ``EXTENSION_STATUS_LABEL_FR``.

    Sécurité multi-tenant F02 : la RLS PostgreSQL filtre par ``account_id``
    en amont (cf. dépendance ``get_current_user``). Le filtre Python sur
    ``user_id`` est une défense en profondeur supplémentaire.
    """
    stmt = (
        select(FundApplication)
        .options(selectinload(FundApplication.fund))
        .where(FundApplication.user_id == user_id)
        .order_by(FundApplication.updated_at.desc())
        .limit(200)  # marge avant filtrage statuts inactifs
    )
    result = await db.execute(stmt)
    apps = list(result.scalars().all())

    items: list[ActiveApplicationItem] = []
    for app in apps:
        status_value = (
            app.status.value if hasattr(app.status, "value") else str(app.status)
        )
        if status_value in INACTIVE_STATUSES:
            continue
        offer_name = app.fund.name if app.fund else "Offre inconnue"
        items.append(
            ActiveApplicationItem(
                id=app.id,
                offer_name=offer_name,
                status=status_value,
                status_label_fr=_label_fr(status_value),
                updated_at=app.updated_at,
                deep_link=_build_deep_link(app.id),
            )
        )
        if len(items) >= 50:
            break
    return items


async def build_profile_snapshot(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID | None
) -> ProfileSnapshot:
    """Construit le snapshot profil entreprise + 3 derniers projets actifs."""
    sector: str | None = None
    country: str | None = None

    if account_id is not None:
        stmt = (
            select(CompanyProfile)
            .where(CompanyProfile.account_id == account_id)
            .limit(1)
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is not None:
            sector_raw = getattr(profile, "sector", None)
            sector = (
                sector_raw.value
                if sector_raw is not None and hasattr(sector_raw, "value")
                else sector_raw
            )
            country = getattr(profile, "country", None)

    # 3 derniers projets actifs (statut hors cancelled/closed).
    projects: list[Project] = []
    if account_id is not None:
        proj_stmt = (
            select(Project)
            .where(Project.account_id == account_id)
            .where(Project.status.notin_(["cancelled", "closed"]))
            .order_by(Project.updated_at.desc())
            .limit(3)
        )
        result = await db.execute(proj_stmt)
        projects = list(result.scalars().all())

    return ProfileSnapshot(
        sector=sector,
        country=country,
        projects=[
            ProjectSnapshotItem(
                id=p.id,
                name=p.name,
                status=(p.status.value if hasattr(p.status, "value") else str(p.status)),
            )
            for p in projects
        ],
    )
