"""F23 — Seed des 3 skills MVP critiques.

Idempotent : check ``SELECT name`` avant chaque insert.

Les 3 skills sont publiées (status=published) directement, sans passer
par le gating eval — les golden_examples sont calibrés mais leur
exécution réelle dépend de l'environnement LLM (cf. ``eval_runner.py``
qui retourne fallback safe en absence de clé OpenRouter).

Cela permet à l'équipe de calibrer manuellement les skills et au loader
de les charger immédiatement après le seed (smoke test admin).

Référence : ``specs/033-skills-playbooks-metier/spec.md`` US7 + plan.md.
"""

from __future__ import annotations

import logging
import uuid
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillDomain, SkillStatus
from app.models.user import User

logger = logging.getLogger(__name__)


SEED_SKILL_NAMES: list[str] = [
    "skill_esg_diagnostic",
    "skill_score_gcf",
    "skill_dossier_gcf_via_boad",
]


def _build_seeds(creator_id: uuid.UUID) -> list[dict]:
    """Retourne les 3 dicts de seed des skills MVP."""
    return [
        {
            "name": "skill_esg_diagnostic",
            "domain": SkillDomain.DIAGNOSTIC_ESG.value,
            "prompt_expert": (
                "Tu es un expert ESG ouest-africain spécialisé dans l'accompagnement "
                "des PME en zone UEMOA. Tu aides à structurer un diagnostic clair et "
                "factuel sur 30 critères E/S/G calibrés pour le contexte africain "
                "(secteur informel, mobile money, énergie solaire). Cite tes sources "
                "(BCEAO, UEMOA, ODD) à chaque affirmation factuelle."
            ),
            "procedure": (
                "1) Demander le secteur d'activité et la taille de l'entreprise.\n"
                "2) Demander les pratiques actuelles sur les 3 dimensions E/S/G.\n"
                "3) Calculer le score sur 30 critères pondérés sectoriellement.\n"
                "4) Restituer le rapport avec recommandations priorisées."
            ),
            "tool_whitelist": [
                "update_company_profile",
                "get_company_profile",
            ],
            "sources": [],
            "activation_rules": {
                "page_slugs": ["/esg"],
                "intent_keywords": ["ESG", "diagnostic", "score"],
                "active_module": ["esg_scoring"],
            },
            "golden_examples": [
                _golden_example(
                    "esg-diag-01",
                    SkillDomain.DIAGNOSTIC_ESG.value,
                    "Je veux faire un diagnostic ESG pour ma PME agricole.",
                    "update_company_profile",
                    {"sector": "agriculture"},
                ),
                _golden_example(
                    "esg-diag-02",
                    SkillDomain.DIAGNOSTIC_ESG.value,
                    "Quel est mon score ESG actuel ?",
                    "get_company_profile",
                ),
                _golden_example(
                    "esg-diag-03",
                    SkillDomain.DIAGNOSTIC_ESG.value,
                    "J'ai 25 employés dans le textile.",
                    "update_company_profile",
                    {"sector": "textile"},
                ),
                _golden_example(
                    "esg-diag-04",
                    SkillDomain.DIAGNOSTIC_ESG.value,
                    "Mon entreprise est dans l'énergie solaire à Dakar.",
                    "update_company_profile",
                    {"sector": "energie"},
                ),
                _golden_example(
                    "esg-diag-05",
                    SkillDomain.DIAGNOSTIC_ESG.value,
                    "Quels critères ESG s'appliquent à mon secteur ?",
                    "get_company_profile",
                ),
            ],
        },
        {
            "name": "skill_score_gcf",
            "domain": SkillDomain.SCORING_REFERENTIEL.value,
            "prompt_expert": (
                "Tu es un expert du Green Climate Fund (GCF) et de ses critères "
                "d'éligibilité projets : additionalité climat, impact mesurable "
                "(tCO2e évitées), portée transformationnelle, alignement Accord "
                "de Paris. Tu aides les PME à pré-évaluer leur projet contre la "
                "grille GCF et à comprendre les attentes en matière de MRV."
            ),
            "procedure": (
                "1) Demander la nature et la taille du projet vert.\n"
                "2) Estimer le potentiel d'évitement carbone (tCO2e/an).\n"
                "3) Évaluer l'additionalité (sans GCF, le projet est-il viable ?).\n"
                "4) Restituer un score sur 100 avec recommandations."
            ),
            "tool_whitelist": [
                "update_company_profile",
                "get_company_profile",
            ],
            "sources": [],
            "activation_rules": {
                "page_slugs": ["/financing", "/applications"],
                "intent_keywords": ["GCF", "Green Climate Fund", "score"],
                "active_module": ["financing"],
            },
            "golden_examples": [
                _golden_example(
                    "gcf-score-01",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Mon projet solaire est-il éligible au GCF ?",
                    "get_company_profile",
                ),
                _golden_example(
                    "gcf-score-02",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Combien de tCO2e mon projet peut-il éviter ?",
                    "get_company_profile",
                ),
                _golden_example(
                    "gcf-score-03",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Quels sont les critères du GCF ?",
                    "get_company_profile",
                ),
                _golden_example(
                    "gcf-score-04",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Score mon projet GCF.",
                    "get_company_profile",
                ),
                _golden_example(
                    "gcf-score-05",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Évalue mon projet d'irrigation contre GCF.",
                    "get_company_profile",
                ),
            ],
        },
        {
            "name": "skill_dossier_gcf_via_boad",
            "domain": SkillDomain.DOSSIER.value,
            "prompt_expert": (
                "Tu es un expert dans le montage de dossiers GCF via BOAD pour "
                "les PME africaines. Tu maîtrises le vocabulaire spécifique : "
                "réplication, additionalité, MRV (Measurement-Reporting-Verification), "
                "co-bénéfices ODD, et la structuration en 8 sections types de la "
                "BOAD. Tu accompagnes pas-à-pas la PME dans la constitution du dossier."
            ),
            "procedure": (
                "1) Vérifier l'éligibilité (secteur, taille, projet vert).\n"
                "2) Initialiser le dossier 8 sections.\n"
                "3) Pré-remplir avec les données entreprise.\n"
                "4) Itérer section par section (impact, MRV, budget, gouvernance).\n"
                "5) Générer le PDF final pour soumission BOAD."
            ),
            "tool_whitelist": [
                "create_fund_application",
                "update_company_profile",
                "get_company_profile",
            ],
            "sources": [],
            "activation_rules": {
                "page_slugs": ["/applications"],
                "intent_keywords": ["dossier", "GCF", "BOAD", "candidature"],
                "active_module": ["application"],
            },
            "golden_examples": [
                _golden_example(
                    "gcf-boad-init-01",
                    SkillDomain.DOSSIER.value,
                    "Je veux préparer mon dossier GCF via BOAD pour mon projet solaire.",
                    "create_fund_application",
                ),
                _golden_example(
                    "gcf-boad-init-02",
                    SkillDomain.DOSSIER.value,
                    "Initialise un dossier BOAD pour le GCF.",
                    "create_fund_application",
                ),
                _golden_example(
                    "gcf-boad-init-03",
                    SkillDomain.DOSSIER.value,
                    "Aide-moi à monter une candidature GCF.",
                    "create_fund_application",
                ),
                _golden_example(
                    "gcf-boad-init-04",
                    SkillDomain.DOSSIER.value,
                    "Je dois soumettre un dossier au BOAD.",
                    "create_fund_application",
                ),
                _golden_example(
                    "gcf-boad-init-05",
                    SkillDomain.DOSSIER.value,
                    "Quelles informations entreprise sont déjà disponibles ?",
                    "get_company_profile",
                ),
            ],
        },
    ]


def _golden_example(
    case_id: str,
    category: str,
    message: str,
    expected_tool: str,
    payload: dict | None = None,
) -> dict:
    return {
        "id": case_id,
        "category": category,
        "context": {
            "current_page": None,
            "active_module": None,
        },
        "user_message": message,
        "expected": {
            "tool_called": expected_tool,
            "payload_contains": payload or {},
        },
    }


async def _existing_names(db: AsyncSession) -> set[str]:
    stmt = select(Skill.name).where(Skill.name.in_(SEED_SKILL_NAMES))
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def seed_skills(
    db: AsyncSession,
    *,
    default_creator_id: uuid.UUID | None = None,
) -> int:
    """Insère les 3 skills MVP en BDD si elles n'existent pas déjà.

    Args:
        db: Session async.
        default_creator_id: UUID du User créateur. Si None, recherche un admin
            quelconque dans la base. Si aucun admin trouvé, lève RuntimeError.

    Returns:
        Nombre de skills effectivement insérées (0 si déjà toutes présentes).
    """
    existing = await _existing_names(db)

    creator_id = default_creator_id
    if creator_id is None:
        admin_stmt = select(User).where(User.role == "ADMIN").limit(1)
        admin = (await db.execute(admin_stmt)).scalar_one_or_none()
        if admin is None:
            raise RuntimeError(
                "seed_skills : aucun admin trouvé en BDD ; passez "
                "``default_creator_id`` ou créez d'abord un admin."
            )
        creator_id = admin.id

    inserted = 0
    for seed in _build_seeds(creator_id):
        if seed["name"] in existing:
            logger.info("[skills.seed] %s déjà présent, skip", seed["name"])
            continue
        skill = Skill(
            **seed,
            status=SkillStatus.PUBLISHED.value,
            created_by=creator_id,
        )
        db.add(skill)
        inserted += 1
        logger.info("[skills.seed] %s insérée", seed["name"])
    await db.flush()
    return inserted
