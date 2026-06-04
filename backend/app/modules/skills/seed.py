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
    "skill_match_project_funds",
    "skill_project_esg_assessment",
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
                # F047 bugfix US3 (2026-05-23) : keywords plus spécifiques
                # pour éviter d'activer ce skill F05 (entreprise) quand
                # l'utilisateur demande un rapport projet (F047). « ESG »
                # seul activait trop largement (overlap avec « rapport ESG
                # de mon projet »). On précise « ESG entreprise », « ESG
                # global », etc.
                "intent_keywords": [
                    "ESG entreprise",
                    "ESG global",
                    "ESG de l'entreprise",
                    "diagnostic ESG",
                    "diagnostic entreprise",
                    "score ESG entreprise",
                    "score ESG global",
                    "évaluation ESG entreprise",
                    "rapport ESG entreprise",
                ],
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
                # 051 — Découverte/statut des dossiers (LECTURE SEULE) : ce skill
                # s'active sur /financing /applications, où l'utilisateur peut
                # demander « où en est mon dossier ? ». Sans ces entrées,
                # l'intersection F23 les masque.
                "list_applications",
                "get_application_checklist",
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
                # 051 — Découverte/statut des dossiers (LECTURE SEULE) : un expert
                # dossier DOIT pouvoir lister les dossiers et lire leur checklist
                # (« où en est mon dossier ? »). Sans ces entrées, l'intersection
                # F23 (select_tools_with_skills) les retire alors qu'ils sont
                # exposés par le sélecteur → l'agent répond « tool indisponible ».
                "list_applications",
                "get_application_checklist",
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
        # ---- F045 : skill_match_project_funds (US1-US4) ----
        {
            "name": "skill_match_project_funds",
            "domain": SkillDomain.SCORING_REFERENTIEL.value,
            "prompt_expert": (
                "Tu es un conseiller financement vert spécialisé dans le matching "
                "projet-centric pour les PME africaines francophones (UEMOA/CEDEAO). "
                "Ton rôle est d'orchestrer le cycle de vie complet d'un projet vert "
                "en chat : guider la création du projet (5 attributs critiques : "
                "secteur, taxonomie verte UEMOA, thèmes prioritaires GCF, impact CO2 "
                "estimé, populations vulnérables ciblées), déclencher le matching "
                "via le tool ``match_funds_for_project``, et expliquer les résultats. "
                "Cite systématiquement les sources F01 verified (BCEAO Taxonomie verte "
                "2024, GCF Strategic Plan 2024-2027, GCF Gender Policy 2019, ODD 10). "
                "Distingue ``project_score`` (impact climat) et ``company_score`` "
                "(solidité financière + ESG entreprise) — ce sont 2 scores séparés. "
                "Une PME informelle avec un projet ambitieux peut obtenir un score "
                "projet élevé même si son score entreprise est faible : c'est le "
                "cœur de l'inclusion financière. Visualise les matches avec les "
                "blocs F11 ``match_card_project``."
            ),
            "procedure": (
                "1) Lister les projets actifs de la PME via ``list_projects`` ; "
                "si aucun, guider la création via ``create_project`` + widgets F18.\n"
                "2) Demander/confirmer les 5 attributs critiques projet "
                "(taxonomie UEMOA, thèmes GCF, gender_inclusion, vulnerable_populations, "
                "expected_impact_tco2e) — chacun avec source F01 si applicable.\n"
                "3) Appeler ``match_funds_for_project(project_id, min_score=60, "
                "limit=10)`` pour obtenir la liste triée par project_score DESC.\n"
                "4) Présenter les 3-5 meilleurs matches sous forme de ``match_card_project`` "
                "blocs F11 (fund_name + intermediary + project_score + company_score + "
                "divergence_explanation courte).\n"
                "5) Si l'utilisateur modifie le projet (update_project), relancer "
                "automatiquement le matching et présenter la nouvelle liste.\n"
                "6) Si ``matches_count == 0``, expliquer le ``no_match_reason`` "
                "et proposer 2-3 thèmes à renforcer (citations F01)."
            ),
            "tool_whitelist": [
                # Tools projet F06 (8)
                "create_project",
                "update_project",
                "delete_project",
                "list_projects",
                "get_project",
                "duplicate_project",
                "link_document_to_project",
                "match_funds_for_project",
                # Tools matching F14 reutilises (4)
                "list_matches_for_project",
                "recompute_matches_for_project",
                "get_match_details",
                "compare_offers_for_fund",
                # Tools sourcage F01 globaux (3)
                "cite_source",
                "search_source",
                "flag_unsourced",
                # Tools visualisation F11 (4)
                "show_kpi_card",
                "show_match_card",
                "show_map",
                "show_comparison_table",
                # Tool widget F18 (1)
                "ask_interactive_question",
                # Profil (1)
                "get_company_profile",
            ],
            "sources": [],
            "activation_rules": {
                "page_slugs": ["/financing", "/profile/projects", "/applications"],
                "intent_keywords": [
                    "matching",
                    "financement",
                    "fonds",
                    "bailleur",
                    "GCF",
                    "FEM",
                    "BOAD",
                    "subvention",
                    "projet vert",
                ],
                "min_keyword_matches": 1,
                "requires_active_project": False,
                "active_module": ["financing", "application", "profile_projects"],
                "priority": 80,
            },
            "golden_examples": [
                _golden_example(
                    "match-project-us1",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Je suis une PME informelle au Togo et j'ai un projet d'agroforesterie "
                    "qui va séquestrer 1500 tCO2e/an, aligné taxonomie UEMOA.",
                    "match_funds_for_project",
                ),
                _golden_example(
                    "match-project-us2",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Mets à jour mon projet pour ajouter le thème REDD+ et relance le matching.",
                    "update_project",
                ),
                _golden_example(
                    "match-project-us3",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Mon projet est juste une boutique commerciale classique, "
                    "quels fonds verts puis-je obtenir ?",
                    "match_funds_for_project",
                ),
                _golden_example(
                    "match-project-us4",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Pourquoi mon score projet est de 78% alors que mon score "
                    "entreprise n'est que de 12% pour ce fonds ?",
                    "get_match_details",
                ),
            ],
        },
        # ---- F047 : skill_project_esg_assessment (US1-US4) ----
        {
            "name": "skill_project_esg_assessment",
            "domain": SkillDomain.SCORING_REFERENTIEL.value,
            "prompt_expert": (
                "Tu es un expert ESG-projet pour bailleurs verts (GCF, FEM, BOAD, "
                "AFD). Ton rôle est d'évaluer un projet vert contre un référentiel "
                "officiel (IFC PS / GCF ESS / BOAD ESS), pas d'évaluer l'entreprise "
                "(ce dernier est traité par `skill_esg_diagnostic`). Tu choisis le "
                "référentiel cible en fonction du bailleur visé : GCF→GCF ESS, "
                "BOAD→BOAD ESS, fonds bilateral ou inconnu→IFC PS (universel). "
                "Cite systématiquement les sources F01 (ifc-performance-standards-2012, "
                "gcf-environmental-social-policy-2018, boad-ess-procedures-2023). "
                "Distingue clairement « évaluation ESG entreprise » (F05, /esg) et "
                "« évaluation ESG-projet » (F047, /profile/projects/{id}/esg)."
            ),
            "procedure": (
                "REGLE ABSOLUE — TU DOIS appeler `create_project_esg_assessment` "
                "AVANT tout `ask_interactive_question`. Les widgets F18 servent "
                "UNIQUEMENT à collecter les réponses aux critères, jamais à "
                "orienter l'utilisateur en début d'évaluation.\n\n"
                "1) OBLIGATOIRE — Appeler `list_project_esg_assessments(project_id=...)` "
                "pour vérifier si un `draft` (ou `finalized`) couvre déjà le "
                "référentiel cible. Si un finalized existe et l'utilisateur demande "
                "le rapport, saute directement à l'étape 6.\n"
                "2) OBLIGATOIRE — Si aucun draft ne couvre le référentiel cible, "
                "appeler `create_project_esg_assessment(project_id, referential_id)` "
                "AVANT TOUTE AUTRE ACTION (notamment AVANT `ask_interactive_question`). "
                "Ce tool retourne `applicable_criteria` (liste des critères avec "
                "leurs UUIDs valides) — utilise-la pour l'étape 3, n'invente JAMAIS "
                "un `criterion_id`.\n"
                "3) Pour chaque critère `is_required=true` issu de "
                "`applicable_criteria`, poser une question via "
                "`ask_interactive_question` (qcu/qcm/justification) et persister la "
                "réponse via `save_project_esg_criterion(assessment_id, "
                "criterion_id, response_type, response_value, source_id|unsourced)`. "
                "Chaque réponse DOIT être sourcée (F01) : `source_id` issu de "
                "`cite_source`/`search_source`, ou `flag_unsourced(reason='user_input')`.\n"
                "4) Finaliser via `finalize_project_esg_assessment(assessment_id)` "
                "quand tous les obligatoires sont couverts. Si un 422 « critères "
                "manquants » est retourné, reprends l'étape 3 sur la liste fournie.\n"
                "5) Restituer le résultat via `show_kpi_card` (score) + "
                "`show_comparison_table` (critères couverts vs manquants).\n"
                "6) RAPPORT — Si l'utilisateur demande le rapport ESIA-light, le "
                "dossier bailleur ou le rapport ESG-projet, APPELLE "
                "`generate_project_esg_report(assessment_id=<id du finalized>)`. "
                "Le format de sortie est PDF (volontaire — les bailleurs préfèrent "
                "ce format au .docx). NE PAS appeler `generate_esg_report` qui est "
                "le rapport ESG ENTREPRISE F05 (différent et inadapté ici).\n\n"
                "ANTI-HALLUCINATION — N'AFFIRME JAMAIS « le rapport ESIA-light a "
                "été généré » dans une réponse texte tant que "
                "`generate_project_esg_report` n'a pas été APPELÉ et n'a pas "
                "retourné `ok=true` avec un `file_path` non vide. Si tu doutes du "
                "`assessment_id`, rappelle `list_project_esg_assessments(project_id, "
                "state='finalized')` pour le retrouver, puis appelle le rapport."
            ),
            "tool_whitelist": [
                # Tools ESG-projet F047 (6)
                "create_project_esg_assessment",
                "save_project_esg_criterion",
                "finalize_project_esg_assessment",
                "get_project_esg_assessment",
                "list_project_esg_assessments",
                "generate_project_esg_report",
                # Tools sourçage F01 globaux (3)
                "cite_source",
                "search_source",
                "flag_unsourced",
                # Tools visualisation F11 (3)
                "show_kpi_card",
                "show_comparison_table",
                "show_summary_card",
                # Widget F18 (1)
                "ask_interactive_question",
                # Contexte projets (2)
                "list_projects",
                "get_project",
            ],
            "sources": [],
            "activation_rules": {
                # Fiche projet (avec ou sans suffixe `/esg`) : le LLM doit
                # piloter l'évaluation ESG-projet F047 dès que l'utilisateur
                # est sur la fiche d'un projet. Les gabarits `[id]` sont
                # interprétés par `_slug_matches_page` (skill_loader) qui
                # convertit `[id]` en regex `[^/]+`.
                "page_slugs": [
                    "/profile/projects/[id]/esg",
                    "/profile/projects/[id]",
                ],
                "intent_keywords": [
                    # Référentiels et concepts F047
                    "ESG projet",
                    "ESG-projet",
                    "IFC PS",
                    "IFC Performance Standards",
                    "GCF ESS",
                    "BOAD ESS",
                    "ESIA",
                    "ESIA-light",
                    "Performance Standards",
                    # Phrases utilisateur courantes (bugfix US3 2026-05-23)
                    "évaluation projet",
                    "evaluation projet",
                    "rapport projet",
                    "rapport ESG projet",
                    "rapport ESG de mon projet",
                    "rapport ESG du projet",
                    "rapport ESG pour mon projet",
                    "rapport pour mon projet",
                    "score de mon projet",
                    "scorer mon projet",
                    "évaluer mon projet",
                    "evaluer mon projet",
                    "finaliser mon projet",
                    "dossier bailleur",
                    "dossier GCF",
                    "dossier BOAD",
                    "dossier IFC",
                    "dossier AFD",
                    "mon projet",  # ancre faible pour matcher fréquemment
                ],
                "min_keyword_matches": 1,
                "requires_active_project": True,
                "active_module": ["esg_scoring", "profile_projects", "chat"],
                "priority": 85,
            },
            "golden_examples": [
                _golden_example(
                    "project-esg-us1",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Je veux évaluer mon projet d'agroforesterie contre IFC PS.",
                    "create_project_esg_assessment",
                ),
                _golden_example(
                    "project-esg-us2",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Mon score ESG-projet contre GCF ESS, pour postuler au GCF.",
                    "create_project_esg_assessment",
                ),
                _golden_example(
                    "project-esg-us3",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Génère le rapport ESIA-light de mon projet pour la BOAD.",
                    "generate_project_esg_report",
                ),
                _golden_example(
                    "project-esg-us4",
                    SkillDomain.SCORING_REFERENTIEL.value,
                    "Continue l'évaluation projet que j'avais commencée hier.",
                    "list_project_esg_assessments",
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

    # F045 / F047 : skills draft initial (gating eval >= 90% avant publication).
    DRAFT_ONLY: set[str] = {
        "skill_match_project_funds",
        "skill_project_esg_assessment",
    }

    inserted = 0
    for seed in _build_seeds(creator_id):
        if seed["name"] in existing:
            logger.info("[skills.seed] %s déjà présent, skip", seed["name"])
            continue
        status = (
            SkillStatus.DRAFT.value
            if seed["name"] in DRAFT_ONLY
            else SkillStatus.PUBLISHED.value
        )
        skill = Skill(
            **seed,
            status=status,
            created_by=creator_id,
        )
        db.add(skill)
        inserted += 1
        logger.info("[skills.seed] %s insérée (status=%s)", seed["name"], status)
    await db.flush()
    return inserted


async def sync_seed_tool_whitelists(db: AsyncSession) -> int:
    """Aligne le ``tool_whitelist`` des skills seedées DÉJÀ présentes sur les défs
    de seed (``seed_skills`` étant insert-only : il ne met jamais à jour les rows
    existantes).

    Idempotent : ne touche qu'une row dont le whitelist diffère de la déf de seed.
    Utile après ajout de tools à un whitelist (ex. 051 : ``list_applications`` /
    ``get_application_checklist`` sur les skills dossier/financement) sans recréer
    les skills ni bumper de version. Retourne le nombre de rows mises à jour.
    """
    # ``creator_id`` est sans effet ici (aucune insertion) — uuid factice.
    desired = {s["name"]: list(s["tool_whitelist"]) for s in _build_seeds(uuid.uuid4())}
    rows = (
        await db.execute(select(Skill).where(Skill.name.in_(desired)))
    ).scalars().all()
    updated = 0
    for skill in rows:
        want = desired.get(skill.name)
        if want is not None and list(skill.tool_whitelist or []) != want:
            skill.tool_whitelist = want
            updated += 1
            logger.info("[skills.seed] tool_whitelist resynchronisé pour %s", skill.name)
    await db.flush()
    return updated
