"""F20 — Seed des ressources MVP de la bibliothèque.

Seed idempotent :
- 5 guides ESG (gouvernance, taxonomie UEMOA, carbone, ESS, dossier vert).
- 5 fiches intermédiaires (BOAD, PNUD, BAD, FEM/GEF, GCF).
- 3 templates documents (politique anti-corruption, charte ESS, registre risques).
- 2 FAQ contextualisées (scoring ESG, fonds verts).

Total : 15 ressources sourcées F01 vérifiées.

Référence : ``specs/038-bibliotheque-ressources/spec.md`` FR-028.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financing import Intermediary
from app.models.resource import (
    Resource,
    ResourcePublicationStatus,
    ResourceType,
)
from app.models.source import Source, VerificationStatus
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class SeedResult:
    """Résultat d'une exécution du seed."""

    inserted: int
    skipped: int
    total: int


def _build_seeds(
    creator_id: uuid.UUID,
    source_ids: dict[str, uuid.UUID],
    intermediary_ids: dict[str, uuid.UUID],
) -> list[dict]:
    """Construit la liste des dicts de seed (15 ressources)."""
    fallback_source = next(iter(source_ids.values()))

    def src(key: str) -> uuid.UUID:
        return source_ids.get(key, fallback_source)

    seeds: list[dict] = []

    # 5 guides ESG
    seeds.append({
        "type": ResourceType.GUIDE.value,
        "title": "Comprendre la taxonomie verte UEMOA",
        "slug": "comprendre-taxonomie-verte-uemoa",
        "description": (
            "Guide pratique pour identifier si votre activité est éligible "
            "à la taxonomie verte UEMOA (BCEAO 2024)."
        ),
        "content_md": (
            "# Comprendre la taxonomie verte UEMOA\n\n"
            "## Qu'est-ce qu'une activité verte ?\n\n"
            "La taxonomie verte UEMOA classe les activités économiques "
            "selon leur contribution à la transition écologique...\n\n"
            "## 6 objectifs environnementaux\n\n"
            "1. Atténuation du changement climatique\n"
            "2. Adaptation au changement climatique\n"
            "3. Utilisation durable des ressources hydriques\n"
            "4. Transition vers une économie circulaire\n"
            "5. Prévention de la pollution\n"
            "6. Protection de la biodiversité\n"
        ),
        "category": ["governance", "environment"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("uemoa_taxonomie"),
    })
    seeds.append({
        "type": ResourceType.GUIDE.value,
        "title": "Politique anti-corruption pour PME africaine",
        "slug": "politique-anti-corruption-pme",
        "description": (
            "Comment rédiger et déployer une politique anti-corruption efficace "
            "dans une PME ouest-africaine."
        ),
        "content_md": (
            "# Politique anti-corruption\n\n"
            "## Pourquoi une politique anti-corruption ?\n\n"
            "Les bailleurs internationaux (GCF, BAD, BOAD) imposent...\n\n"
            "## Étapes clés\n\n"
            "1. Engagement de la direction\n"
            "2. Cartographie des risques\n"
            "3. Code de conduite signé par tous\n"
            "4. Canal d'alerte confidentiel\n"
            "5. Formation annuelle\n"
        ),
        "category": ["governance"],
        "target_audience": ["pme_micro", "pme_small", "pme_medium"],
        "source_id": src("ifc_ps"),
    })
    seeds.append({
        "type": ResourceType.GUIDE.value,
        "title": "Mesurer son empreinte carbone : guide pratique",
        "slug": "mesurer-empreinte-carbone-pratique",
        "description": (
            "Comment réaliser un premier bilan carbone simplifié "
            "(scopes 1, 2 et 3 essentiels) pour une PME en zone UEMOA."
        ),
        "content_md": (
            "# Mesurer son empreinte carbone\n\n"
            "## Les 3 scopes\n\n"
            "- **Scope 1** : émissions directes (combustion sur site, flotte)\n"
            "- **Scope 2** : émissions liées à l'énergie achetée\n"
            "- **Scope 3** : autres émissions indirectes\n\n"
            "## Facteurs d'émission UEMOA\n\n"
            "Utilisez les facteurs spécifiques par pays (mix électrique 2024).\n"
        ),
        "category": ["environment", "carbon"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("ipcc_ar6"),
    })
    seeds.append({
        "type": ResourceType.GUIDE.value,
        "title": "Critères ESS : ce que les bailleurs attendent",
        "slug": "criteres-ess-bailleurs",
        "description": (
            "Les attentes E/S/G des grands bailleurs (BOAD, BAD, GCF) "
            "expliquées simplement avec exemples concrets."
        ),
        "content_md": (
            "# Critères ESS\n\n"
            "## Environnement\n\n"
            "- Étude d'impact environnemental\n"
            "- Plan de gestion environnementale\n\n"
            "## Social\n\n"
            "- Consultation des parties prenantes\n"
            "- Plan de réinstallation si applicable\n\n"
            "## Gouvernance\n\n"
            "- Politique anti-corruption\n"
            "- Reporting transparent\n"
        ),
        "category": ["governance", "social", "environment"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("boad_ess"),
    })
    seeds.append({
        "type": ResourceType.GUIDE.value,
        "title": "Préparer un dossier de financement vert",
        "slug": "preparer-dossier-financement-vert",
        "description": (
            "Liste des documents et étapes pour monter un dossier solide "
            "auprès des fonds verts (GCF, BOAD, FEM)."
        ),
        "content_md": (
            "# Préparer un dossier de financement vert\n\n"
            "## Documents indispensables\n\n"
            "1. Note conceptuelle (2-3 pages)\n"
            "2. Étude de faisabilité\n"
            "3. Évaluation d'impact climat\n"
            "4. Plan de financement détaillé\n"
            "5. Statuts juridiques + récépissé fiscal\n"
        ),
        "category": ["financing", "governance"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("gcf_invest"),
    })

    # 5 fiches intermédiaires
    intermediary_guide_data = [
        ("boad", "Comment travailler avec la BOAD",
         "fiche-pratique-boad",
         "Process complet de soumission d'un projet à la Banque Ouest Africaine de Développement.",
         "boad_ess"),
        ("pnud", "Comment travailler avec le PNUD",
         "fiche-pratique-pnud",
         "Étapes pour bénéficier d'un appui PNUD sur les projets ODD en Afrique de l'Ouest.",
         "ifc_ps"),
        ("bad", "Comment travailler avec la BAD",
         "fiche-pratique-bad",
         "Guide d'accès aux guichets de la Banque Africaine de Développement.",
         "boad_ess"),
        ("fem", "Comment travailler avec le FEM/GEF",
         "fiche-pratique-fem",
         "Process Fonds pour l'Environnement Mondial : entités d'exécution éligibles.",
         "gcf_invest"),
        ("gcf", "Comment travailler avec le GCF",
         "fiche-pratique-gcf",
         "Guide d'accès au Green Climate Fund via accreditation directe ou intermediaire.",
         "gcf_invest"),
    ]
    for code, title, slug, desc, src_key in intermediary_guide_data:
        if code not in intermediary_ids:
            continue
        seeds.append({
            "type": ResourceType.INTERMEDIARY_GUIDE.value,
            "title": title,
            "slug": slug,
            "description": desc,
            "content_md": (
                f"# {title}\n\n"
                "## Process de soumission\n\n"
                "1. Note conceptuelle\n2. Manifestation d'intérêt\n"
                "3. Dossier complet\n4. Évaluation\n5. Décision\n\n"
                "## Contacts vérifiés\n\n"
                "Email : voir site officiel.\n\n"
                "## Délais typiques\n\n"
                "90 jours en moyenne entre soumission et décision.\n\n"
                "## Conseils gagnants\n\n"
                "- Aligner sur les priorités sectorielles publiées.\n"
                "- Soigner l'évaluation d'impact.\n\n"
                "## Points d'attention\n\n"
                "- Documents en français exigés.\n"
                "- Cofinancement souvent requis (10-30%).\n\n"
                "## FAQ\n\n"
                "### Quelle taille minimale de projet ?\n"
                "Variable selon le guichet.\n"
            ),
            "category": ["financing", "intermediary"],
            "target_audience": ["pme_small", "pme_medium"],
            "intermediary_id": intermediary_ids[code],
            "source_id": src(src_key),
        })

    # 3 templates documents
    seeds.append({
        "type": ResourceType.TEMPLATE_DOC.value,
        "title": "Modèle politique anti-corruption (.docx)",
        "slug": "template-politique-anti-corruption",
        "description": "Modèle Word personnalisable pour PME africaine.",
        "content_md": "Téléchargez le modèle puis personnalisez-le.",
        "file_url": "/uploads/resources/template-politique-anti-corruption.docx",
        "category": ["governance"],
        "target_audience": ["pme_micro", "pme_small", "pme_medium"],
        "source_id": src("ifc_ps"),
    })
    seeds.append({
        "type": ResourceType.TEMPLATE_DOC.value,
        "title": "Modèle charte ESS (.docx)",
        "slug": "template-charte-ess",
        "description": "Modèle de charte Environnement, Social et Sociétal.",
        "content_md": "Téléchargez et adaptez à votre activité.",
        "file_url": "/uploads/resources/template-charte-ess.docx",
        "category": ["governance", "social", "environment"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("boad_ess"),
    })
    seeds.append({
        "type": ResourceType.TEMPLATE_DOC.value,
        "title": "Modèle registre des risques (.xlsx)",
        "slug": "template-registre-risques",
        "description": "Tableau Excel pour cartographier vos risques ESG.",
        "content_md": "Une ligne par risque identifié.",
        "file_url": "/uploads/resources/template-registre-risques.xlsx",
        "category": ["governance"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("ifc_ps"),
    })

    # 2 FAQ
    seeds.append({
        "type": ResourceType.FAQ.value,
        "title": "Questions fréquentes sur le scoring ESG",
        "slug": "faq-scoring-esg",
        "description": "Réponses aux questions courantes sur le calcul du score ESG.",
        "content_md": (
            "# FAQ Scoring ESG\n\n"
            "## Comment est calculé mon score ?\n\n"
            "30 critères pondérés selon votre secteur.\n\n"
            "## Que faire si mon score est bas ?\n\n"
            "Identifiez les critères non renseignés et priorisez l'amélioration.\n"
        ),
        "category": ["governance", "social", "environment"],
        "target_audience": ["pme_micro", "pme_small", "pme_medium"],
        "source_id": src("uemoa_taxonomie"),
    })
    seeds.append({
        "type": ResourceType.FAQ.value,
        "title": "Questions fréquentes sur les fonds verts",
        "slug": "faq-fonds-verts",
        "description": "Tout ce que vous devez savoir avant de candidater.",
        "content_md": (
            "# FAQ Fonds verts\n\n"
            "## Quel est le délai moyen ?\n\n"
            "Entre 6 et 18 mois selon le bailleur.\n\n"
            "## Faut-il un cofinancement ?\n\n"
            "Souvent oui, entre 10% et 50% selon le programme.\n"
        ),
        "category": ["financing"],
        "target_audience": ["pme_small", "pme_medium"],
        "source_id": src("gcf_invest"),
    })

    return seeds


async def _resolve_source_ids(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Mappe les codes seed → UUID de sources F01 verified existantes.

    Stratégie best-effort : on cherche par mots-clés dans publisher/title.
    """
    out: dict[str, uuid.UUID] = {}
    stmt = select(Source).where(Source.verification_status == VerificationStatus.VERIFIED.value)
    result = await db.execute(stmt)
    sources = list(result.scalars().all())
    if not sources:
        return out

    def find(*keywords: str) -> uuid.UUID | None:
        kws = [k.lower() for k in keywords]
        for s in sources:
            blob = f"{s.publisher or ''} {s.title or ''}".lower()
            if any(k in blob for k in kws):
                return s.id
        return None

    candidates = {
        "uemoa_taxonomie": find("uemoa", "taxonomie", "bceao"),
        "ifc_ps": find("ifc", "performance standards"),
        "ipcc_ar6": find("ipcc", "ar6", "ademe"),
        "boad_ess": find("boad", "ess"),
        "gcf_invest": find("gcf", "green climate"),
    }
    for k, v in candidates.items():
        if v is not None:
            out[k] = v
    # Fallback : si certains keys manquent, prendre la première verified.
    if sources:
        fallback = sources[0].id
        for k in ("uemoa_taxonomie", "ifc_ps", "ipcc_ar6", "boad_ess", "gcf_invest"):
            out.setdefault(k, fallback)
    return out


async def _resolve_intermediary_ids(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Mappe les codes seed → UUID d'intermédiaires existants."""
    out: dict[str, uuid.UUID] = {}
    stmt = select(Intermediary)
    result = await db.execute(stmt)
    intermediaries = list(result.scalars().all())
    for it in intermediaries:
        name = (it.name or "").lower()
        code_attr = (getattr(it, "code", "") or "").lower()
        if "boad" in name or code_attr == "boad":
            out.setdefault("boad", it.id)
        if "pnud" in name or "undp" in name or code_attr in ("pnud", "undp"):
            out.setdefault("pnud", it.id)
        if name.startswith("bad") or "banque africaine" in name or code_attr == "bad":
            out.setdefault("bad", it.id)
        if "fem" in name or "gef" in name or code_attr in ("fem", "gef"):
            out.setdefault("fem", it.id)
        if "gcf" in name or "green climate" in name or code_attr == "gcf":
            out.setdefault("gcf", it.id)
    return out


async def seed_resources(
    db: AsyncSession,
    admin_user_id: uuid.UUID,
    *,
    publish: bool = True,
) -> SeedResult:
    """Insère les ressources seed (idempotent par slug).

    Args:
        db: session SQLAlchemy.
        admin_user_id: UUID du créateur (ADMIN).
        publish: si True, marque les ressources comme published (smoke test).

    Returns:
        SeedResult(inserted, skipped, total).
    """
    source_ids = await _resolve_source_ids(db)
    if not source_ids:
        logger.warning("[resources.seed] no verified source available, skipping")
        return SeedResult(0, 0, 0)

    intermediary_ids = await _resolve_intermediary_ids(db)
    seeds = _build_seeds(admin_user_id, source_ids, intermediary_ids)

    # Filter out intermediary_guides without a matching intermediary id (safety).
    seeds = [s for s in seeds if not (s["type"] == ResourceType.INTERMEDIARY_GUIDE.value and s.get("intermediary_id") is None)]

    inserted = 0
    skipped = 0
    for body in seeds:
        slug = body["slug"]
        existing_stmt = select(Resource.id).where(Resource.slug == slug)
        if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
            skipped += 1
            continue
        # Convert enums to strings if any.
        resource = Resource(
            **body,
            created_by=admin_user_id,
            publication_status=(
                ResourcePublicationStatus.PUBLISHED.value
                if publish
                else ResourcePublicationStatus.DRAFT.value
            ),
            valid_from=date.today() if publish else None,
        )
        db.add(resource)
        inserted += 1

    await db.flush()

    total_stmt = select(Resource)
    total_count = len((await db.execute(total_stmt)).scalars().all())
    logger.info(
        "[resources.seed] inserted=%s skipped=%s total=%s",
        inserted,
        skipped,
        total_count,
    )
    return SeedResult(inserted=inserted, skipped=skipped, total=total_count)
