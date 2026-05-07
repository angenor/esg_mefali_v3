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

from app.graph.tools.common import get_db_and_user, with_retry

logger = logging.getLogger(__name__)


async def _resolve_account_id(db, user_id):
    """Charge le ``account_id`` du user (None si admin sans tenant)."""
    from app.models.user import User

    result = await db.execute(select(User.account_id).where(User.id == user_id))
    return result.scalar_one_or_none()


@tool
@with_retry(
    max_retries=1,
    node_name="credit_node",
    fallback_message=(
        "Je n'arrive pas à générer le score de crédit. "
        "Pouvez-vous réessayer dans un instant ?"
    ),
)
async def generate_credit_score(config: RunnableConfig) -> str:
    """Calcule le score de credit vert alternatif (solvabilite + impact ESG/carbone).

    Use when:
    - "calcule mon score credit", "credit vert", "solvabilite verte".
    - apres saisie ESG + carbone, proposer un score combine au prospect.
    Don't use when:
    - simple consultation (utiliser `get_credit_score`).
    - certificat demande (utiliser `generate_credit_certificate` apres
      ce tool).
    Exemple: "Donne-moi mon score credit vert" -> generate_credit_score().
    Anti: "Mon score actuel ?" -> NE PAS appeler (utiliser `get_credit_score`).

    Le score combine donnees non-conventionnelles (profil, ESG, carbone) ;
    aucun chiffre ne doit etre estime manuellement par le LLM.
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
    """Consulte le dernier score de credit vert calcule (lecture seule).

    Use when:
    - "mon score credit", "ma solvabilite verte".
    - apres `generate_credit_score`, communiquer le score.
    Don't use when:
    - score jamais calcule (utiliser `generate_credit_score`).
    - attestation demandee (utiliser `generate_credit_certificate`).
    Exemple: "Mon score credit vert ?" -> get_credit_score().
    Anti: "Recalcule mon score" -> NE PAS appeler (utiliser `generate_credit_score`).
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
@with_retry(
    max_retries=1,
    node_name="credit_node",
    fallback_message=(
        "Je n'arrive pas à émettre l'attestation de crédit. "
        "Pouvez-vous réessayer ou contacter le support ?"
    ),
)
async def generate_credit_certificate(config: RunnableConfig) -> str:
    """Genere une attestation verifiable signee Ed25519 du score de credit vert (F08).

    Use when:
    - "attestation officielle", "certificat verifiable", "document signe".
    - apres `generate_credit_score`, l'utilisateur veut partager son score.
    Don't use when:
    - score non calcule (calculer d'abord via `generate_credit_score`).
    - simple consultation (utiliser `get_credit_score`).
    Exemple: "Donne-moi un certificat de mon score" -> generate_credit_certificate().
    Anti: "Mon score actuel ?" -> NE PAS appeler (utiliser `get_credit_score`).

    Le tool retourne l'URL de verification publique que le LLM DOIT communiquer
    en clair a l'utilisateur dans la reponse texte.
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
