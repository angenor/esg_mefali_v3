"""Seed du singleton DIRECT (intermédiaire représentant la soumission directe).

Le seed est :
- **Idempotent** : 2 appels successifs n'insèrent qu'une seule ligne.
- **Catalogue admin** : pas de filtre RLS par account_id.

Le code unique ``code='DIRECT'`` permet à l'application d'identifier ce
singleton lors du calcul des offres pour les fonds ``access_type='direct'``.

Note : la migration 028 effectue le seed automatique. Cette fonction
runtime est utilisée pour les tests / reseed manuel.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financing import (
    Intermediary,
    IntermediaryType,
    OrganizationType,
)
from app.models.source import Source

logger = logging.getLogger(__name__)


DIRECT_CODE = "DIRECT"
DIRECT_SOURCE_URL = "system://mefali/direct-singleton"


async def seed_direct_intermediary(session: AsyncSession) -> Intermediary:
    """Crée (idempotent) l'intermédiaire singleton ``code='DIRECT'``.

    Si l'intermédiaire existe déjà, le retourne sans modification.
    Crée également la ``Source`` ``system://mefali/direct-singleton`` si absente.
    """
    # 1. Récupérer / créer la Source DIRECT
    src_result = await session.execute(
        select(Source).where(Source.url == DIRECT_SOURCE_URL).limit(1)
    )
    source = src_result.scalar_one_or_none()
    if source is None:
        from app.models.user import User
        # Trouver 2 admins distincts (4-eyes)
        admin_result = await session.execute(
            select(User).where(User.role == "admin").order_by(User.id).limit(2)
        )
        admins = list(admin_result.scalars().all())
        if len(admins) < 2:
            # Fallback : tous les users
            user_result = await session.execute(
                select(User).order_by(User.id).limit(2)
            )
            admins = list(user_result.scalars().all())
        if len(admins) == 0:
            raise RuntimeError(
                "Impossible de seeder DIRECT : aucun user disponible pour captured_by."
            )
        captured_by = admins[0]
        verified_by = admins[1] if len(admins) > 1 else None

        from datetime import datetime, timezone
        source = Source(
            url=DIRECT_SOURCE_URL,
            title="Singleton DIRECT — soumission directe sans intermédiaire",
            publisher="Mefali",
            version="1.0",
            date_publi=date.today(),
            captured_by=captured_by.id,
            created_by_user_id=captured_by.id,
            verified_by=verified_by.id if verified_by else None,
            verified_at=datetime.now(timezone.utc) if verified_by else None,
            verification_status="verified" if verified_by else "draft",
        )
        session.add(source)
        await session.flush()

    # 2. Récupérer / créer l'intermédiaire DIRECT
    interm_result = await session.execute(
        select(Intermediary).where(Intermediary.code == DIRECT_CODE).limit(1)
    )
    intermediary = interm_result.scalar_one_or_none()
    if intermediary is not None:
        # S'assurer que source_id est bien renseigné (cas re-seed après downgrade)
        if intermediary.source_id is None:
            intermediary.source_id = source.id
            await session.flush()
        return intermediary

    intermediary = Intermediary(
        code=DIRECT_CODE,
        name="Direct (sans intermédiaire)",
        intermediary_type=IntermediaryType.accredited_entity,
        organization_type=OrganizationType.un_agency,
        country="ALL",
        city="N/A",
        accreditations=[],
        services_offered={},
        eligibility_for_sme={},
        is_active=True,
        source_id=source.id,
        publication_status="published",
        required_documents=[],
        version="1.0",
        valid_from=date.today(),
    )
    session.add(intermediary)
    await session.flush()
    return intermediary
