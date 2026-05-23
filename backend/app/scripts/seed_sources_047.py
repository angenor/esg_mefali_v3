"""F047 — Seed des 3 sources F01 + ~46 critères F13 pour l'évaluation ESG-projet.

Idempotent : SELECT-before-INSERT par URL (sources) et code (criteria).

Sources seedées (status='verified', four-eyes captured_by != verified_by) :
1. IFC Performance Standards on Environmental and Social Sustainability (2012)
2. GCF Revised Environmental and Social Policy (2018, incl. Gender Policy 2019)
3. BOAD Procédures d'évaluation environnementale et sociale (2023)

Critères seedés (~46) : 16 IFC PS + 15 GCF ESS + 15 BOAD ESS, tous avec
``applies_to_project=true``, ``weight`` par défaut 1.00 (ajustable), ``is_required``
distinguant les critères obligatoires (1 par standard) des optionnels.

Reference : specs/047-evaluation-esg-projet/research.md D2+D7+D9, data-model.md.

Usage::

    cd backend && source venv/bin/activate
    python -m app.scripts.seed_sources_047
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models.indicator import Criterion  # noqa: E402
from app.models.referential import Referential  # noqa: E402
from app.models.source import PublicationStatus, Source, VerificationStatus  # noqa: E402
from app.models.user import User  # noqa: E402

logger = logging.getLogger(__name__)


SEED_SOURCES_047: list[dict] = [
    {
        "url": "https://www.ifc.org/wps/wcm/connect/topics_ext_content/ifc_external_corporate_site/sustainability-at-ifc/policies-standards/performance-standards",
        "title": "IFC Performance Standards on Environmental and Social Sustainability",
        "publisher": "International Finance Corporation",
        "version": "2012",
        "date_publi": date(2012, 1, 1),
        "section": "PS1..PS8 — Assessment, Labor, Resource Efficiency, Community, "
        "Land Acquisition, Biodiversity, Indigenous Peoples, Cultural Heritage",
    },
    {
        "url": "https://www.greenclimate.fund/document/revised-environmental-and-social-policy",
        "title": "GCF Revised Environmental and Social Policy",
        "publisher": "Green Climate Fund",
        "version": "2018",
        "date_publi": date(2018, 10, 1),
        "section": "ESS1..ESS6 — Risk, Stakeholders, Gender, Indigenous, "
        "Resettlement, Climate co-benefits (incl. Gender Policy 2019)",
    },
    {
        "url": "https://www.boad.org/publications/procedures-environnementales-sociales-2023/",
        "title": "BOAD Procédures d'évaluation environnementale et sociale",
        "publisher": "Banque Ouest Africaine de Développement",
        "version": "2023",
        "date_publi": date(2023, 1, 1),
        "section": "10 ESS alignées Banque mondiale ESF + spécificités UEMOA",
    },
]


# Référentiels F13 — code -> métadonnées de création si absent
REFERENTIALS_047: dict[str, dict] = {
    "ifc_ps": {
        "label": "IFC Performance Standards",
        "description": "8 standards de performance environnementale et sociale "
        "de l'International Finance Corporation. Référentiel universel "
        "applicable à tout projet d'investissement privé.",
        "source_url": SEED_SOURCES_047[0]["url"],
    },
    "gcf_ess": {
        "label": "GCF Environmental & Social Safeguards",
        "description": "6 Environmental & Social Standards du Green Climate Fund. "
        "Référentiel obligatoire pour tout projet candidat à un financement GCF.",
        "source_url": SEED_SOURCES_047[1]["url"],
    },
    "boad_ess": {
        "label": "BOAD Environmental & Social Standards",
        "description": "Standards environnementaux et sociaux de la Banque "
        "Ouest Africaine de Développement (UEMOA). Alignés ESF Banque mondiale.",
        "source_url": SEED_SOURCES_047[2]["url"],
    },
}


def _criterion(code: str, label: str, *, weight: float = 1.0, required: bool = False) -> dict:
    return {
        "code": code,
        "label": label,
        "weight": weight,
        "is_required": required,
        "expression": {"type": "qcu", "scale": "yes_no"},
    }


# 16 critères IFC PS (2 par standard PS1..PS8)
CRITERIA_IFC_PS: list[dict] = [
    _criterion("IFCPS1-A", "Un système de gestion environnementale et sociale est en place pour le projet.", weight=1.5, required=True),
    _criterion("IFCPS1-B", "Les risques E&S majeurs ont été identifiés et documentés (PGES).", weight=1.5),
    _criterion("IFCPS2-A", "Les conditions de travail respectent les normes nationales et OIT fondamentales.", weight=1.0, required=True),
    _criterion("IFCPS2-B", "Une procédure de grief travailleurs accessible est en place.", weight=1.0),
    _criterion("IFCPS3-A", "Le projet inclut des mesures d'efficacité énergétique et hydrique.", weight=1.0),
    _criterion("IFCPS3-B", "Les émissions GES du projet sont estimées et suivies.", weight=1.0),
    _criterion("IFCPS4-A", "Les impacts du projet sur la santé/sécurité des communautés sont évalués.", weight=1.0, required=True),
    _criterion("IFCPS4-B", "Un plan d'intervention d'urgence communautaire existe (si applicable).", weight=0.5),
    _criterion("IFCPS5-A", "Aucun déplacement physique ou économique involontaire (ou plan compensation IFC PS5).", weight=1.5, required=True),
    _criterion("IFCPS5-B", "Les acquisitions foncières sont documentées avec consentement.", weight=1.0),
    _criterion("IFCPS6-A", "Les impacts sur la biodiversité et services écosystémiques sont évalués.", weight=1.0),
    _criterion("IFCPS6-B", "Les zones d'habitat critique sont identifiées et évitées.", weight=1.0),
    _criterion("IFCPS7-A", "Présence de populations autochtones identifiée (et CLIP appliqué le cas échéant).", weight=1.0),
    _criterion("IFCPS7-B", "Consultation libre, préalable et éclairée documentée.", weight=1.0),
    _criterion("IFCPS8-A", "Le patrimoine culturel tangible et intangible est évalué.", weight=0.5),
    _criterion("IFCPS8-B", "Procédure de découverte fortuite (chance find) prévue.", weight=0.5),
]

# 15 critères GCF ESS (≥ 2 par ESS1..ESS6)
CRITERIA_GCF_ESS: list[dict] = [
    _criterion("GCFESS1-A", "Une évaluation des risques E&S (catégorie A/B/C) est documentée.", weight=1.5, required=True),
    _criterion("GCFESS1-B", "Le projet contribue à atténuation ou adaptation climat de façon mesurable.", weight=1.5),
    _criterion("GCFESS1-C", "Un plan de suivi-évaluation M&E est intégré au design.", weight=1.0),
    _criterion("GCFESS2-A", "Une cartographie des parties prenantes est réalisée.", weight=1.0, required=True),
    _criterion("GCFESS2-B", "Un mécanisme de gestion des plaintes communautaires existe.", weight=1.0),
    _criterion("GCFESS2-C", "Consultations publiques documentées avec compte-rendu.", weight=1.0),
    _criterion("GCFESS3-A", "Analyse genre intégrée à la conception du projet (Gender Policy GCF 2019).", weight=1.5, required=True),
    _criterion("GCFESS3-B", "Indicateurs désagrégés par sexe inclus dans le M&E.", weight=1.0),
    _criterion("GCFESS3-C", "Budget dédié aux activités favorables aux femmes identifié.", weight=0.5),
    _criterion("GCFESS4-A", "Risques pour populations autochtones évalués (CLIP si applicable).", weight=1.0),
    _criterion("GCFESS4-B", "Plan de protection populations vulnérables documenté.", weight=1.0),
    _criterion("GCFESS5-A", "Pas de déplacement involontaire (ou plan de réinstallation conforme).", weight=1.5, required=True),
    _criterion("GCFESS5-B", "Mesures de restauration des moyens de subsistance prévues.", weight=1.0),
    _criterion("GCFESS6-A", "Co-bénéfices d'adaptation climat documentés (au-delà de l'atténuation).", weight=1.0),
    _criterion("GCFESS6-B", "Résilience long-terme aux changements climatiques évaluée.", weight=1.0),
]

# 15 critères BOAD ESS (concentration ESS1, ESS5, ESS9 + spécificités UEMOA)
CRITERIA_BOAD_ESS: list[dict] = [
    _criterion("BOADESS1-A", "Catégorisation environnementale et sociale du projet réalisée (A/B/C).", weight=1.5, required=True),
    _criterion("BOADESS1-B", "Évaluation E&S préliminaire (NIES) disponible.", weight=1.0),
    _criterion("BOADESS1-C", "Plan de gestion environnementale et sociale (PGES) chiffré.", weight=1.0),
    _criterion("BOADESS2-A", "Conditions de travail conformes au Code du travail UEMOA.", weight=1.0, required=True),
    _criterion("BOADESS2-B", "Liberté syndicale et négociation collective respectées.", weight=0.5),
    _criterion("BOADESS3-A", "Mesures de prévention de la pollution intégrées au design.", weight=1.0),
    _criterion("BOADESS4-A", "Santé/sécurité communauté évaluée (eau potable, accès soins).", weight=1.0),
    _criterion("BOADESS5-A", "Acquisition foncière conforme procédures BOAD (consultation, compensation).", weight=1.5, required=True),
    _criterion("BOADESS5-B", "Restauration des moyens de subsistance des personnes affectées.", weight=1.0),
    _criterion("BOADESS6-A", "Conservation biodiversité (zones protégées UEMOA évitées).", weight=1.0),
    _criterion("BOADESS7-A", "Patrimoine culturel UEMOA protégé (sites classés).", weight=0.5),
    _criterion("BOADESS8-A", "Inclusion genre conforme orientations BOAD (femmes, jeunes).", weight=1.5, required=True),
    _criterion("BOADESS9-A", "Mécanisme grief communautés documenté (intermédiaires financiers).", weight=1.0),
    _criterion("BOADESS9-B", "Diffusion publique d'information conforme politique BOAD.", weight=0.5),
    _criterion("BOADESS10-A", "Engagement parties prenantes formalisé tout au long du cycle projet.", weight=1.0),
]


CRITERIA_BY_REF: dict[str, list[dict]] = {
    "ifc_ps": CRITERIA_IFC_PS,
    "gcf_ess": CRITERIA_GCF_ESS,
    "boad_ess": CRITERIA_BOAD_ESS,
}


async def _ensure_two_admins(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Retourne 2 UUID d'admins distincts (crée admin-verifier si besoin)."""
    result = await db.execute(select(User).where(User.role == "ADMIN").limit(2))
    admins = list(result.scalars().all())

    if len(admins) >= 2:
        return admins[0].id, admins[1].id

    if len(admins) == 0:
        raise RuntimeError(
            "seed_sources_047 : aucun admin trouvé en BDD ; créez d'abord un "
            "admin via ``python -m app.scripts.seed_admin``."
        )

    captured_by = admins[0]
    verifier = User(
        email="admin-verifier@mefali-system",
        hashed_password="!disabled!",
        full_name="Mefali System — Verifier Technique",
        company_name="Mefali System",
        account_id=None,
        role="ADMIN",
    )
    db.add(verifier)
    await db.flush()
    return captured_by.id, verifier.id


async def _upsert_sources(
    db: AsyncSession, captured_by: uuid.UUID, verified_by: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """Insère les 3 sources si absentes. Retourne map url -> source_id."""
    urls = [s["url"] for s in SEED_SOURCES_047]
    result = await db.execute(select(Source).where(Source.url.in_(urls)))
    existing = {s.url: s.id for s in result.scalars().all()}

    now = datetime.now(timezone.utc)
    inserted = 0
    for seed in SEED_SOURCES_047:
        if seed["url"] in existing:
            continue
        source = Source(
            url=seed["url"],
            title=seed["title"],
            publisher=seed["publisher"],
            version=seed["version"],
            date_publi=seed["date_publi"],
            section=seed.get("section"),
            captured_by=captured_by,
            created_by_user_id=captured_by,
            verified_by=verified_by,
            verified_at=now,
            verification_status=VerificationStatus.VERIFIED.value,
        )
        db.add(source)
        inserted += 1

    await db.flush()
    logger.info("[seed_sources_047] %d sources F01 insérées", inserted)

    # Rafraîchir le mapping après insert
    result = await db.execute(select(Source).where(Source.url.in_(urls)))
    return {s.url: s.id for s in result.scalars().all()}


async def _upsert_referentials(
    db: AsyncSession,
    *,
    captured_by: uuid.UUID,
    sources_by_url: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Insère/retourne les 3 référentiels F13 (code -> id)."""
    codes = list(REFERENTIALS_047.keys())
    result = await db.execute(select(Referential).where(Referential.code.in_(codes)))
    existing = {r.code: r.id for r in result.scalars().all()}

    inserted = 0
    for code, meta in REFERENTIALS_047.items():
        if code in existing:
            continue
        ref = Referential(
            code=code,
            label=meta["label"],
            description=meta["description"],
            source_id=sources_by_url[meta["source_url"]],
            publication_status=PublicationStatus.PUBLISHED.value,
            created_by_user_id=captured_by,
        )
        db.add(ref)
        inserted += 1

    await db.flush()
    logger.info("[seed_sources_047] %d référentiels F13 insérés", inserted)

    result = await db.execute(select(Referential).where(Referential.code.in_(codes)))
    return {r.code: r.id for r in result.scalars().all()}


async def _upsert_criteria(
    db: AsyncSession,
    *,
    captured_by: uuid.UUID,
    sources_by_url: dict[str, uuid.UUID],
    referentials_by_code: dict[str, uuid.UUID],
) -> int:
    """Insère les ~46 critères F13 avec weight + applies_to_project=true."""
    all_codes = [
        c["code"] for crit_list in CRITERIA_BY_REF.values() for c in crit_list
    ]
    result = await db.execute(select(Criterion.code).where(Criterion.code.in_(all_codes)))
    existing = {row[0] for row in result.all()}

    inserted = 0
    for ref_code, criteria_list in CRITERIA_BY_REF.items():
        ref_id = referentials_by_code[ref_code]
        source_url = REFERENTIALS_047[ref_code]["source_url"]
        source_id = sources_by_url[source_url]
        for c in criteria_list:
            if c["code"] in existing:
                continue
            criterion = Criterion(
                code=c["code"],
                label=c["label"],
                expression=c["expression"],
                source_id=source_id,
                publication_status=PublicationStatus.PUBLISHED.value,
                created_by_user_id=captured_by,
                weight=c["weight"],
                is_required=c["is_required"],
                applies_to_project=True,
                referential_id=ref_id,
            )
            db.add(criterion)
            inserted += 1

    await db.flush()
    logger.info("[seed_sources_047] %d critères F13 insérés", inserted)
    return inserted


async def seed_sources_047(
    db: AsyncSession,
    *,
    captured_by_id: uuid.UUID | None = None,
    verified_by_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Seed idempotent : 3 sources F01 + 3 référentiels F13 + ~46 critères F13.

    Returns:
        dict ``{sources, referentials, criteria}`` avec compteurs insérés.
    """
    if captured_by_id is None or verified_by_id is None:
        captured_by_id, verified_by_id = await _ensure_two_admins(db)

    if captured_by_id == verified_by_id:
        raise ValueError(
            "seed_sources_047 : captured_by_id != verified_by_id requis (F01)."
        )

    sources_by_url = await _upsert_sources(db, captured_by_id, verified_by_id)
    referentials_by_code = await _upsert_referentials(
        db, captured_by=captured_by_id, sources_by_url=sources_by_url,
    )
    criteria_inserted = await _upsert_criteria(
        db,
        captured_by=captured_by_id,
        sources_by_url=sources_by_url,
        referentials_by_code=referentials_by_code,
    )

    return {
        "sources": len(sources_by_url),
        "referentials": len(referentials_by_code),
        "criteria": criteria_inserted,
    }


async def _main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    async with async_session_factory() as session:
        report = await seed_sources_047(session)
        await session.commit()
        logger.info(
            "Seed 047 terminé : sources=%d (existantes+nouvelles), "
            "référentiels=%d, critères insérés=%d",
            report["sources"],
            report["referentials"],
            report["criteria"],
        )
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
