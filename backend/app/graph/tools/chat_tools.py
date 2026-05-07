"""Tools LangChain pour le noeud chat (lecture seule).

Quatre tools de consultation pour que le LLM reponde
avec des donnees temps reel depuis la base de donnees.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


@tool
async def get_user_dashboard_summary(config: RunnableConfig) -> str:
    """Obtient le resume du tableau de bord (ESG, carbone, credit, financements).

    Use when:
    - questions generales : "ou j'en suis", "mon dashboard", "ma progression".
    - decider la prochaine etape (matching, plan d'action, evaluation manquante).
    Don't use when:
    - lecture d'un module specifique (utiliser `get_esg_assessment_chat`/`get_carbon_summary_chat`).
    - mise a jour profil (utiliser `update_company_profile`).
    Exemple: "Donne-moi un resume de ma situation" -> get_user_dashboard_summary().
    Anti: "Mon score ESG ?" -> NE PAS appeler (utiliser `get_esg_assessment_chat`).
    """
    from app.modules.dashboard.service import get_dashboard_summary

    try:
        db, user_id = get_db_and_user(config)

        summary = await get_dashboard_summary(db=db, user_id=user_id)

        parts: list[str] = ["Tableau de bord de l'utilisateur :"]

        # ESG
        esg = summary.get("esg")
        if esg:
            parts.append(
                f"- ESG : score global {esg.get('overall_score', 'N/A')}/100 "
                f"(E: {esg.get('environment_score', 'N/A')}, "
                f"S: {esg.get('social_score', 'N/A')}, "
                f"G: {esg.get('governance_score', 'N/A')})"
            )
        else:
            parts.append("- ESG : aucune evaluation realisee")

        # Carbone
        carbon = summary.get("carbon")
        if carbon:
            parts.append(
                f"- Carbone : {carbon.get('total_emissions_tco2e', 'N/A')} tCO2e "
                f"(annee {carbon.get('year', 'N/A')})"
            )
        else:
            parts.append("- Carbone : aucun bilan realise")

        # Credit
        credit = summary.get("credit")
        if credit:
            parts.append(
                f"- Credit vert : score {credit.get('combined_score', 'N/A')}/100 "
                f"(risque : {credit.get('risk_level', 'N/A')})"
            )
        else:
            parts.append("- Credit vert : aucun score calcule")

        # Financement
        financing = summary.get("financing", {})
        matched = financing.get("matched_funds", 0)
        interested = financing.get("interested_funds", 0)
        parts.append(f"- Financements : {matched} fonds matches, {interested} marques d'interet")

        return "\n".join(parts)

    except Exception as e:
        logger.exception("Erreur lors de la recuperation du tableau de bord")
        return f"Erreur lors de la recuperation du tableau de bord : {e}"


@tool
async def get_company_profile_chat(config: RunnableConfig) -> str:
    """Consulte le profil entreprise et son taux de completion (lecture seule).

    Use when:
    - "mon profil", "que sais-tu de mon entreprise", "donnees enregistrees".
    - decider quel module ouvrir (besoin de secteur/taille/pays).
    Don't use when:
    - mise a jour de fait (utiliser `update_company_profile`).
    - score ESG demande (utiliser `get_esg_assessment_chat`).
    Exemple: "Montre mon profil" -> get_company_profile_chat().
    Anti: "Mon CA est 50M FCFA" -> NE PAS appeler (utiliser `update_company_profile`).
    """
    from app.modules.company.service import FIELD_LABELS, compute_completion, get_profile

    try:
        db, user_id = get_db_and_user(config)

        profile = await get_profile(db, user_id)

        if profile is None:
            return (
                "Aucun profil entreprise enregistre. "
                "L'utilisateur doit d'abord partager des informations sur son entreprise."
            )

        completion = compute_completion(profile)

        lines: list[str] = ["Profil entreprise :"]
        for field_name in (completion.identity_fields.filled + completion.esg_fields.filled):
            value = getattr(profile, field_name, None)
            if value is not None:
                display_value = value.value if hasattr(value, "value") else value
                label = FIELD_LABELS.get(field_name, field_name)
                lines.append(f"- {label} : {display_value}")

        lines.append(
            f"\nCompletion : identite {completion.identity_completion}% | "
            f"ESG {completion.esg_completion}% | "
            f"global {completion.overall_completion}%"
        )

        missing_labels = [
            FIELD_LABELS.get(f, f)
            for f in (completion.identity_fields.missing + completion.esg_fields.missing)
        ]
        if missing_labels:
            lines.append(f"Champs manquants : {', '.join(missing_labels)}")

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Erreur lors de la consultation du profil")
        return f"Erreur lors de la consultation du profil : {e}"


@tool
async def get_esg_assessment_chat(
    config: RunnableConfig,
    assessment_id: str | None = None,
) -> str:
    """Consulte l'evaluation ESG la plus recente (score global + scores E/S/G).

    Use when:
    - "mon score ESG", "ma performance E/S/G", "resultats evaluation".
    - apres finalisation, montrer le score a l'utilisateur.
    Don't use when:
    - saisie d'un critere (utiliser `save_esg_criterion_score`/`batch_save_esg_criteria`).
    - cloture (utiliser `finalize_esg_assessment`).
    Exemple: "Mon score ESG ?" -> get_esg_assessment_chat().
    Anti: "Je veux noter mes politiques" -> NE PAS appeler (saisie -> `batch_save_esg_criteria`).

    Args:
        assessment_id: Identifiant UUID de l'evaluation (optionnel, prend la plus recente par defaut).
    """
    import uuid

    from app.modules.esg.service import get_assessment, get_latest_assessment, get_resumable_assessment

    try:
        db, user_id = get_db_and_user(config)

        assessment = None
        if assessment_id:
            assessment = await get_assessment(db=db, assessment_id=uuid.UUID(assessment_id), user_id=user_id)
        else:
            # Chercher d'abord une evaluation en cours, sinon la plus recente (completed)
            assessment = await get_resumable_assessment(db=db, user_id=user_id)
            if assessment is None:
                assessment = await get_latest_assessment(db=db, user_id=user_id)

        if assessment is None:
            return "Aucune evaluation ESG trouvee pour cet utilisateur."

        status = assessment.status.value if hasattr(assessment.status, "value") else assessment.status

        result = (
            f"Evaluation ESG :\n"
            f"- ID : {assessment.id}\n"
            f"- Statut : {status}\n"
            f"- Secteur : {assessment.sector}"
        )

        if status == "completed" and assessment.overall_score is not None:
            result += (
                f"\n- Score global : {assessment.overall_score}/100\n"
                f"- Environnement : {assessment.environment_score}/100\n"
                f"- Social : {assessment.social_score}/100\n"
                f"- Gouvernance : {assessment.governance_score}/100"
            )

        return result

    except Exception as e:
        logger.exception("Erreur lors de la consultation de l'evaluation ESG")
        return f"Erreur lors de la consultation de l'evaluation ESG : {e}"


@tool
async def get_carbon_summary_chat(
    config: RunnableConfig,
    assessment_id: str | None = None,
) -> str:
    """Consulte le bilan carbone le plus recent (emissions tCO2e + secteur + statut).

    Use when:
    - "mon empreinte carbone", "mes emissions", "tCO2e".
    - apres finalisation, communiquer le total a l'utilisateur.
    Don't use when:
    - saisie d'une entree (utiliser `save_emission_entry`).
    - cloture demandee (utiliser `finalize_carbon_assessment`).
    Exemple: "Mon empreinte 2026 ?" -> get_carbon_summary_chat().
    Anti: "200L de diesel" -> NE PAS appeler (saisie -> `save_emission_entry`).

    Args:
        assessment_id: Identifiant UUID du bilan (optionnel, prend le plus recent par defaut).
    """
    import uuid

    from app.modules.carbon.service import get_assessment, get_resumable_assessment

    try:
        db, user_id = get_db_and_user(config)

        assessment = None
        if assessment_id:
            assessment = await get_assessment(db, uuid.UUID(assessment_id), user_id)
        else:
            assessment = await get_resumable_assessment(db, user_id)

        if assessment is None:
            return "Aucun bilan carbone trouve pour cet utilisateur."

        status = assessment.status.value if hasattr(assessment.status, "value") else assessment.status
        total = assessment.total_emissions_tco2e or 0.0

        result = (
            f"Bilan carbone :\n"
            f"- ID : {assessment.id}\n"
            f"- Annee : {assessment.year}\n"
            f"- Statut : {status}\n"
            f"- Emissions totales : {total} tCO2e"
        )

        if assessment.sector:
            result += f"\n- Secteur : {assessment.sector}"

        return result

    except Exception as e:
        logger.exception("Erreur lors de la consultation du bilan carbone")
        return f"Erreur lors de la consultation du bilan carbone : {e}"


CHAT_TOOLS = [
    get_user_dashboard_summary,
    get_company_profile_chat,
    get_esg_assessment_chat,
    get_carbon_summary_chat,
]
