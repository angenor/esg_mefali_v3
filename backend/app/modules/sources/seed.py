"""Seed initial des 30+ sources verifiees du catalogue (F01).

Crée :
- Deux users systeme (system-curator et system-validator) en role ADMIN
  si non existants.
- 30+ sources `verified` couvrant les principaux organismes :
  ADEME, IPCC, IEA, UEMOA, BCEAO, GCF, IFC, BOAD, Gold Standard, Verra, ODD ONU.

Idempotent : ON CONFLICT DO NOTHING sur l'URL.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.security import hash_password
from app.models.source import Source, VerificationStatus
from app.models.user import User

logger = logging.getLogger(__name__)


# 30+ sources verifiees a seeder.
SEED_SOURCES: list[dict] = [
    # --- ADEME (energie, transport, dechets, facteurs d'emission) ---
    {
        "url": "https://base-empreinte.ademe.fr/donnees/jeu-donnees",
        "title": "ADEME Base Carbone v23",
        "publisher": "ADEME",
        "version": "v23",
        "date_publi": date(2024, 1, 15),
        "section": "Facteurs d'emission",
    },
    {
        "url": "https://librairie.ademe.fr/changement-climatique-et-energie/electricite-mix",
        "title": "ADEME Mix electrique national 2023",
        "publisher": "ADEME",
        "version": "2023",
        "date_publi": date(2023, 12, 1),
    },
    # --- IPCC ---
    {
        "url": "https://www.ipcc.ch/report/ar6/wg3/",
        "title": "IPCC AR6 Working Group III - Mitigation",
        "publisher": "IPCC",
        "version": "AR6",
        "date_publi": date(2022, 4, 4),
    },
    {
        "url": "https://www.ipcc.ch/report/ar6/syr/",
        "title": "IPCC AR6 Synthesis Report",
        "publisher": "IPCC",
        "version": "AR6",
        "date_publi": date(2023, 3, 20),
    },
    # --- IEA ---
    {
        "url": "https://www.iea.org/reports/africa-energy-outlook-2024",
        "title": "IEA Africa Energy Outlook 2024",
        "publisher": "IEA",
        "version": "2024",
        "date_publi": date(2024, 6, 15),
    },
    # --- UEMOA ---
    {
        "url": "https://www.bceao.int/sites/default/files/2024-01/taxonomie-verte-uemoa.pdf",
        "title": "Taxonomie verte UEMOA",
        "publisher": "UEMOA",
        "version": "2024",
        "date_publi": date(2024, 1, 1),
    },
    {
        "url": "https://www.uemoa.int/sites/default/files/bibliotheque/reglementation-pme.pdf",
        "title": "Definition PME UEMOA - Reglementation 2023",
        "publisher": "UEMOA",
        "version": "2023",
        "date_publi": date(2023, 6, 1),
    },
    # --- BCEAO ---
    {
        "url": "https://www.bceao.int/fr/publications/circulaire-002-2024-finance-durable",
        "title": "Circulaire BCEAO 002-2024 Finance durable",
        "publisher": "BCEAO",
        "version": "002-2024",
        "date_publi": date(2024, 3, 15),
    },
    {
        "url": "https://www.bceao.int/fr/publications/banque-mobile-money",
        "title": "BCEAO Etudes Mobile Money 2023",
        "publisher": "BCEAO",
        "version": "2023",
        "date_publi": date(2023, 11, 1),
    },
    # --- GCF (Green Climate Fund) ---
    {
        "url": "https://www.greenclimate.fund/about/governance/policies-strategies/investment-framework",
        "title": "GCF Investment Framework",
        "publisher": "GCF",
        "version": "2024",
        "date_publi": date(2024, 4, 1),
    },
    # --- IFC ---
    {
        "url": "https://www.ifc.org/wps/wcm/connect/topics_ext_content/ifc_external_corporate_site/sustainability-at-ifc/policies-standards/performance-standards",
        "title": "IFC Performance Standards 2012",
        "publisher": "IFC",
        "version": "2012",
        "date_publi": date(2012, 1, 1),
    },
    # --- BOAD ---
    {
        "url": "https://www.boad.org/politique-environnementale-sociale",
        "title": "BOAD Politique Sectorielle ESS",
        "publisher": "BOAD",
        "version": "2023",
        "date_publi": date(2023, 9, 1),
    },
    {
        "url": "https://www.boad.org/programmes-financement-pme",
        "title": "BOAD Programme PME 2024",
        "publisher": "BOAD",
        "version": "2024",
        "date_publi": date(2024, 2, 1),
    },
    # --- Gold Standard ---
    {
        "url": "https://www.goldstandard.org/our-impact/sectors-impacts/programmes",
        "title": "Gold Standard Programme Reglementaire",
        "publisher": "Gold Standard",
        "version": "v1.2",
        "date_publi": date(2023, 5, 1),
    },
    # --- Verra ---
    {
        "url": "https://verra.org/programs/verified-carbon-standard/",
        "title": "Verra VCS Standard v4.7",
        "publisher": "Verra",
        "version": "v4.7",
        "date_publi": date(2023, 9, 1),
    },
    # --- ODD ONU ---
    {
        "url": "https://www.un.org/sustainabledevelopment/decent-work-and-economic-growth/",
        "title": "ODD 8 - Travail decent et croissance economique",
        "publisher": "ODD ONU",
        "version": "2030",
        "date_publi": date(2015, 9, 25),
    },
    {
        "url": "https://www.un.org/sustainabledevelopment/innovation/",
        "title": "ODD 9 - Industrie, innovation et infrastructure",
        "publisher": "ODD ONU",
        "version": "2030",
        "date_publi": date(2015, 9, 25),
    },
    {
        "url": "https://www.un.org/sustainabledevelopment/inequality/",
        "title": "ODD 10 - Inegalites reduites",
        "publisher": "ODD ONU",
        "version": "2030",
        "date_publi": date(2015, 9, 25),
    },
    {
        "url": "https://www.un.org/sustainabledevelopment/sustainable-consumption-production/",
        "title": "ODD 12 - Consommation et production responsables",
        "publisher": "ODD ONU",
        "version": "2030",
        "date_publi": date(2015, 9, 25),
    },
    {
        "url": "https://www.un.org/sustainabledevelopment/climate-change/",
        "title": "ODD 13 - Mesures relatives a la lutte contre les changements climatiques",
        "publisher": "ODD ONU",
        "version": "2030",
        "date_publi": date(2015, 9, 25),
    },
    {
        "url": "https://www.un.org/sustainabledevelopment/globalpartnerships/",
        "title": "ODD 17 - Partenariats pour la realisation des objectifs",
        "publisher": "ODD ONU",
        "version": "2030",
        "date_publi": date(2015, 9, 25),
    },
    # --- GRI ---
    {
        "url": "https://www.globalreporting.org/standards/",
        "title": "GRI Universal Standards 2021",
        "publisher": "GRI",
        "version": "2021",
        "date_publi": date(2021, 10, 5),
    },
    # --- ISO references (utilises par les indicators) ---
    {
        "url": "https://www.iso.org/standard/60857.html",
        "title": "ISO 26000 Lignes directrices Responsabilite societale",
        "publisher": "ISO",
        "version": "2010",
        "date_publi": date(2010, 11, 1),
    },
    {
        "url": "https://www.iso.org/standard/60570.html",
        "title": "ISO 14064-1 Inventaire GES organisationnel",
        "publisher": "ISO",
        "version": "2018",
        "date_publi": date(2018, 12, 19),
    },
    # --- ADEME complementaires ---
    {
        "url": "https://www.ademe.fr/expertises/changement-climatique/methodologies-bilan-emissions",
        "title": "ADEME Methode Bilan Carbone",
        "publisher": "ADEME",
        "version": "v8",
        "date_publi": date(2023, 3, 1),
    },
    # --- World Bank ---
    {
        "url": "https://www.worldbank.org/en/topic/climatechange/brief/climate-finance",
        "title": "World Bank Climate Finance Tracking",
        "publisher": "World Bank",
        "version": "2023",
        "date_publi": date(2023, 10, 1),
    },
    # --- AfDB ---
    {
        "url": "https://www.afdb.org/en/topics-and-sectors/sectors/agriculture-agro-industries",
        "title": "AfDB Politique Agriculture Verte",
        "publisher": "AfDB",
        "version": "2023",
        "date_publi": date(2023, 7, 1),
    },
    # --- CEDEAO ---
    {
        "url": "https://www.ecowas.int/specialised-agencies/ercc/",
        "title": "CEDEAO Plan Climat 2024",
        "publisher": "CEDEAO",
        "version": "2024",
        "date_publi": date(2024, 1, 15),
    },
    # --- IRENA ---
    {
        "url": "https://www.irena.org/Publications/2024/Africa-Renewable-Energy",
        "title": "IRENA Africa Renewable Energy 2024",
        "publisher": "IRENA",
        "version": "2024",
        "date_publi": date(2024, 5, 1),
    },
    # --- ITU/UN connectivity ---
    {
        "url": "https://www.itu.int/en/ITU-D/Statistics/Pages/stat/default.aspx",
        "title": "ITU Connectivity Statistics 2023",
        "publisher": "ITU",
        "version": "2023",
        "date_publi": date(2023, 12, 1),
    },
    # --- ILO ---
    {
        "url": "https://www.ilo.org/africa/areas-of-work/decent-work",
        "title": "ILO Travail Decent Afrique 2023",
        "publisher": "ILO",
        "version": "2023",
        "date_publi": date(2023, 11, 1),
    },
]


SYSTEM_CURATOR_EMAIL = "system-curator@esg-mefali.local"
SYSTEM_VALIDATOR_EMAIL = "system-validator@esg-mefali.local"


async def _ensure_system_user(db: AsyncSession, email: str, name: str) -> User:
    """Garantir l'existence d'un user systeme ADMIN ; le creer si absent."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=email,
        hashed_password=hash_password("__system_only_no_login__"),
        full_name=name,
        company_name="ESG Mefali (Systeme)",
        is_active=False,  # systeme : pas de login interactif
        role=UserRole.ADMIN.value,
        account_id=None,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_sources(db: AsyncSession) -> tuple[int, int]:
    """Seed les 30+ sources `verified` du catalogue.

    Returns:
        (created_count, skipped_count) pour observabilite.
    """
    curator = await _ensure_system_user(
        db, SYSTEM_CURATOR_EMAIL, "Systeme - Curateur Catalogue",
    )
    validator = await _ensure_system_user(
        db, SYSTEM_VALIDATOR_EMAIL, "Systeme - Validateur Catalogue",
    )

    created = 0
    skipped = 0
    for entry in SEED_SOURCES:
        existing = await db.execute(
            select(Source).where(Source.url == entry["url"])
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue
        src = Source(
            url=entry["url"],
            title=entry["title"],
            publisher=entry["publisher"],
            version=entry["version"],
            date_publi=entry["date_publi"],
            section=entry.get("section"),
            captured_by=curator.id,
            verified_by=validator.id,
            verification_status=VerificationStatus.VERIFIED.value,
            verified_at=datetime.now(timezone.utc),
            created_by_user_id=curator.id,
        )
        db.add(src)
        created += 1
    await db.flush()
    logger.info("seed_sources : %d crees, %d ignores", created, skipped)
    return created, skipped


async def get_source_id_by_publisher(
    db: AsyncSession, publisher: str,
) -> UUID | None:
    """Helper pour resoudre la 1ere source `verified` d'un publisher."""
    result = await db.execute(
        select(Source.id).where(
            Source.publisher == publisher,
            Source.verification_status == VerificationStatus.VERIFIED.value,
        ).limit(1)
    )
    return result.scalar_one_or_none()
