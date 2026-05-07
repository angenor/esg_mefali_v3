"""Tools LangChain pour le noeud scoring credit vert.

Trois tools exposes au LLM :
- generate_credit_score : calculer le score de credit vert
- get_credit_score : consulter le dernier score
- generate_credit_certificate : generer une attestation verifiable signee Ed25519 (F08)
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import select

from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


async def _resolve_account_id(db, user_id):
    """Charge le ``account_id`` du user (None si admin sans tenant)."""
    from app.models.user import User

    result = await db.execute(select(User.account_id).where(User.id == user_id))
    return result.scalar_one_or_none()


@tool
async def generate_credit_score(config: RunnableConfig) -> str:
    """Calculer le score de credit vert alternatif de l'utilisateur.

    Utilise cet outil quand l'utilisateur demande a calculer ou recalculer
    son score de credit vert. Le score combine solvabilite et impact vert
    a partir des donnees non-conventionnelles (profil, ESG, carbone).
    N'estime JAMAIS un score manuellement — appelle toujours ce tool.
    """
    from app.modules.credit.service import generate_credit_score as gen_score

    try:
        db, user_id = get_db_and_user(config)

        score = await gen_score(db=db, user_id=user_id)

        return (
            f"Score de credit vert calcule avec succes !\n"
            f"- Score combine : {score.combined_score}/100\n"
            f"- Solvabilite : {score.solvability_score}/100\n"
            f"- Impact vert : {score.green_impact_score}/100\n"
            f"- Niveau de risque : {score.risk_level}\n"
            f"- Version : {score.version}\n\n"
            f"Le score est visible sur la page /credit-score."
        )
    except Exception as e:
        logger.exception("Erreur lors du calcul du score de credit")
        return f"Erreur lors du calcul du score de credit : {e}"


@tool
async def get_credit_score(config: RunnableConfig) -> str:
    """Consulter le dernier score de credit vert de l'utilisateur.

    Utilise cet outil quand l'utilisateur demande son score de credit vert actuel,
    son niveau de risque, ou sa solvabilite.
    """
    from app.modules.credit.service import get_latest_score

    try:
        db, user_id = get_db_and_user(config)

        score = await get_latest_score(db=db, user_id=user_id)

        if score is None:
            return (
                "Aucun score de credit vert calcule. "
                "Proposez a l'utilisateur de calculer son score en utilisant "
                "le tool generate_credit_score."
            )

        return (
            f"Score de credit vert actuel :\n"
            f"- Score combine : {score.combined_score}/100\n"
            f"- Solvabilite : {score.solvability_score}/100\n"
            f"- Impact vert : {score.green_impact_score}/100\n"
            f"- Niveau de risque : {score.risk_level}\n"
            f"- Version : {score.version}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la consultation du score de credit")
        return f"Erreur lors de la consultation du score : {e}"


@tool
async def generate_credit_certificate(config: RunnableConfig) -> str:
    """Generer une attestation verifiable signee Ed25519 du score de credit vert (F08).

    Utilise cet outil quand l'utilisateur demande un certificat, une attestation
    ou un document officiel de son score de credit vert. Le service appele
    genere reellement un PDF signe Ed25519 avec QR code et URL de verification
    publique. Le tool retourne l'URL de verification que tu DOIS communiquer
    a l'utilisateur dans ta reponse texte.
    """
    from app.core.audit_context import source_of_change_scope
    from app.modules.attestations.service import (
        AttestationError,
        CreditScoreMissingError,
        EsgAssessmentMissingError,
        PdfGenerationError,
        generate_attestation,
    )

    try:
        db, user_id = get_db_and_user(config)
        account_id = await _resolve_account_id(db, user_id)
        if account_id is None:
            return (
                "Erreur : votre compte n'est pas lié à un tenant. Contactez le support "
                "pour finaliser la création de votre espace."
            )

        with source_of_change_scope("llm"):
            attestation = await generate_attestation(
                db,
                account_id=account_id,
                user_id=user_id,
                attestation_type="credit_score",
                source_of_change="llm",
            )

        return (
            f"Attestation vérifiable générée avec succès !\n"
            f"- Identifiant : {attestation.display_id}\n"
            f"- URL de vérification publique : {attestation.verification_url}\n"
            f"- Hash SHA-256 du PDF : {attestation.pdf_hash_sha256}\n\n"
            f"Vous pouvez télécharger le PDF depuis votre espace /attestations "
            f"et partager l'URL de vérification avec un partenaire fonds. "
            f"Le QR code embarqué dans le PDF mène à cette même URL."
        )
    except CreditScoreMissingError as exc:
        logger.info("generate_credit_certificate sans score credit : %s", exc)
        return (
            "Aucun score de crédit calculé. Veuillez d'abord finaliser le scoring "
            "crédit en utilisant le tool generate_credit_score."
        )
    except EsgAssessmentMissingError as exc:
        logger.info("generate_credit_certificate sans evaluation ESG : %s", exc)
        return (
            "Aucune évaluation ESG finalisée. Veuillez d'abord compléter votre "
            "évaluation ESG."
        )
    except PdfGenerationError as exc:
        logger.exception("Echec generation PDF attestation")
        return f"Erreur lors de la génération du PDF : {exc}"
    except AttestationError as exc:
        logger.exception("Erreur metier attestation")
        return f"Erreur lors de la génération de l'attestation : {exc}"
    except Exception as e:  # noqa: BLE001
        logger.exception("Erreur inattendue lors de la generation de l'attestation")
        return f"Erreur lors de la génération de l'attestation : {e}"


CREDIT_TOOLS = [generate_credit_score, get_credit_score, generate_credit_certificate]
