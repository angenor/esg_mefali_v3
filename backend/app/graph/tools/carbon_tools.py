"""Tools LangChain pour le noeud de bilan carbone."""

import json
import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


@tool
async def create_carbon_assessment(year: int, config: RunnableConfig) -> str:
    """Creer un nouveau bilan carbone annuel pour l'utilisateur.

    Utilise le secteur du profil entreprise si disponible.
    Un seul bilan par annee est autorise.

    Args:
        year: Annee du bilan carbone (ex: 2025).
    """
    from app.modules.carbon.service import create_assessment
    from app.modules.company.service import get_profile

    try:
        db, user_id = get_db_and_user(config)
        configurable = (config or {}).get("configurable", {})
        conversation_id = configurable.get("conversation_id")

        # Recuperer le secteur depuis le profil entreprise
        sector = None
        try:
            profile = await get_profile(db, user_id)
            if profile and profile.sector:
                sector = profile.sector
                if hasattr(sector, "value"):
                    sector = sector.value
        except Exception:
            logger.debug("Impossible de recuperer le profil entreprise pour le secteur")

        conv_id = uuid.UUID(str(conversation_id)) if conversation_id else None
        assessment = await create_assessment(
            db=db,
            user_id=user_id,
            year=year,
            sector=sector,
            conversation_id=conv_id,
        )

        return json.dumps({
            "status": "success",
            "assessment_id": str(assessment.id),
            "year": assessment.year,
            "sector": assessment.sector or "non defini",
            "message": f"Bilan carbone {year} cree avec succes.",
        }, ensure_ascii=False)

    except ValueError as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Erreur lors de la creation du bilan carbone")
        return json.dumps({
            "status": "error",
            "message": f"Erreur lors de la creation du bilan : {e}",
        }, ensure_ascii=False)


@tool
async def save_emission_entry(
    assessment_id: str,
    category: str,
    quantity: float,
    unit: str,
    source_description: str,
    subcategory: str | None = None,
    config: RunnableConfig = None,
) -> str:
    """Enregistrer une entree d'emission dans le bilan carbone.

    F17 — Le facteur d'emission est selectionne automatiquement selon la
    categorie, le pays du profil entreprise et l'annee du bilan. Le facteur
    est cite via la table sources (F01) ; le LLM doit appeler
    ``cite_source(source_id)`` apres ce tool pour respecter l'invariant
    n°1 (sourcage obligatoire).

    Args:
        assessment_id: UUID du bilan carbone.
        category: Categorie d'emission (energy, transport, waste, industrial,
            agriculture, purchases).
        quantity: Quantite consommee (ex: 500 kWh, 200 litres, 50 tonnes).
        unit: Unite de la quantite (kWh, L, kg, t, etc.).
        source_description: Texte libre legacy decrivant la source utilisateur.
        subcategory: Sous-categorie / cle du facteur d'emission (ex:
            ``electricity``, ``electricity_ci_2024``, ``purchases_cement``).

    Returns:
        JSON string avec status, entry, total_emissions_tco2e, factor_used,
        source_id (a citer via cite_source), is_approximate, fallback_reason.
    """
    from app.modules.carbon.emission_factors import compute_emissions_tco2e
    from app.modules.carbon.factor_service import (
        EmissionFactorNotFoundError,
        get_emission_factor,
    )
    from app.modules.carbon.service import add_entries, get_assessment
    from app.modules.company.service import get_profile

    try:
        db, user_id = get_db_and_user(config)

        # Recuperer le bilan.
        assessment = await get_assessment(db, uuid.UUID(assessment_id), user_id)
        if assessment is None:
            return json.dumps({
                "status": "error",
                "message": f"Bilan carbone introuvable (id={assessment_id}).",
            }, ensure_ascii=False)

        # F17 — Resoudre le pays via le profil entreprise.
        country: str | None = None
        try:
            profile = await get_profile(db, user_id)
            if profile and profile.country:
                country = profile.country.strip().upper()
        except Exception:
            logger.debug("Impossible de resoudre le pays via le profil entreprise.")

        # F17 — Resolution facteur via factor_service.
        # Strategie : on essaie d'abord ``subcategory`` (categorie complete
        # ex. ``purchases_cement``, ``electricity``), puis fallback sur ``category``
        # standard (ex. ``energy``).
        lookup_category = subcategory if subcategory else category
        try:
            resolution = await get_emission_factor(
                db,
                category=lookup_category,
                country=country,
                year=assessment.year,
            )
        except EmissionFactorNotFoundError:
            # Tentative fallback : matching par categorie de base si
            # la subcategory exotique echoue.
            if subcategory and subcategory != category:
                try:
                    resolution = await get_emission_factor(
                        db,
                        category=category,
                        country=country,
                        year=assessment.year,
                    )
                except EmissionFactorNotFoundError as exc:
                    return json.dumps({
                        "status": "error",
                        "message": str(exc),
                        "error_code": "factor_not_found",
                    }, ensure_ascii=False)
            else:
                exc = EmissionFactorNotFoundError(
                    lookup_category, country, assessment.year
                )
                return json.dumps({
                    "status": "error",
                    "message": str(exc),
                    "error_code": "factor_not_found",
                }, ensure_ascii=False)

        factor = resolution.factor
        emission_factor_value = float(factor.value)
        emissions_tco2e = compute_emissions_tco2e(quantity, emission_factor_value)

        entry_data = {
            "category": category,
            "subcategory": factor.code,
            "quantity": quantity,
            "unit": unit,
            "emission_factor": emission_factor_value,
            "emissions_tco2e": emissions_tco2e,
            "source_description": source_description,
            # F17 — sourcage et snapshot facteur.
            "source_id": factor.source_id,
            "factor_id": factor.id,
        }

        added_count, total, completed_cats = await add_entries(
            db=db,
            assessment=assessment,
            entries_data=[entry_data],
        )

        return json.dumps({
            "status": "success",
            "entry": {
                "category": category,
                "subcategory": factor.code,
                "quantity": quantity,
                "unit": unit,
                "emission_factor_kgco2e": emission_factor_value,
                "emissions_tco2e": emissions_tco2e,
                "source_description": source_description,
            },
            "factor_used": {
                "code": factor.code,
                "label": factor.label,
                "country": factor.country,
                "year": factor.year,
                "value": emission_factor_value,
                "unit": factor.unit,
            },
            "source_id": str(factor.source_id),
            "is_approximate": resolution.is_approximate,
            "fallback_reason": resolution.fallback_reason,
            "total_emissions_tco2e": total,
            "message": (
                f"Entree enregistree : {quantity} {unit} de {factor.label}"
                f" = {emissions_tco2e} tCO2e. Total actuel : {total} tCO2e."
            ),
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("Erreur lors de l'enregistrement de l'entree d'emission")
        return json.dumps({
            "status": "error",
            "message": f"Erreur lors de l'enregistrement : {e}",
        }, ensure_ascii=False)


@tool
async def finalize_carbon_assessment(
    assessment_id: str,
    config: RunnableConfig,
) -> str:
    """Finaliser un bilan carbone et calculer le total des emissions.

    IMPORTANT : N'appelle ce tool que si l'utilisateur a explicitement confirme
    vouloir finaliser. Demande d'abord confirmation.

    Args:
        assessment_id: UUID du bilan carbone a finaliser.
    """
    from app.modules.carbon.service import complete_assessment, get_assessment

    try:
        db, user_id = get_db_and_user(config)

        assessment = await get_assessment(db, uuid.UUID(assessment_id), user_id)
        if assessment is None:
            return json.dumps({
                "status": "error",
                "message": f"Bilan carbone introuvable (id={assessment_id}).",
            }, ensure_ascii=False)

        if assessment.status.value == "completed":
            return json.dumps({
                "status": "error",
                "message": "Ce bilan est deja finalise.",
            }, ensure_ascii=False)

        completed = await complete_assessment(db=db, assessment=assessment)

        return json.dumps({
            "status": "success",
            "assessment_id": str(completed.id),
            "total_emissions_tco2e": completed.total_emissions_tco2e or 0.0,
            "year": completed.year,
            "message": (
                f"Bilan carbone {completed.year} finalise. "
                f"Total : {completed.total_emissions_tco2e or 0.0} tCO2e."
            ),
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("Erreur lors de la finalisation du bilan carbone")
        return json.dumps({
            "status": "error",
            "message": f"Erreur lors de la finalisation : {e}",
        }, ensure_ascii=False)


@tool
async def get_carbon_summary(
    assessment_id: str | None = None,
    config: RunnableConfig = None,
) -> str:
    """Obtenir le resume complet d'un bilan carbone (emissions, repartition, equivalences, benchmark).

    Si aucun assessment_id n'est fourni, cherche le bilan en cours de l'utilisateur.

    Args:
        assessment_id: UUID du bilan carbone (optionnel).
    """
    from app.modules.carbon.service import (
        get_assessment,
        get_assessment_summary,
        get_latest_assessment,
        get_resumable_assessment,
    )

    try:
        db, user_id = get_db_and_user(config)

        assessment = None
        if assessment_id:
            assessment = await get_assessment(db, uuid.UUID(assessment_id), user_id)
        else:
            # Priorite au bilan in_progress (reprise de questionnaire).
            # Fallback sur le dernier bilan quel que soit son statut pour
            # permettre la consultation d'un bilan completed.
            assessment = await get_resumable_assessment(db, user_id)
            if assessment is None:
                assessment = await get_latest_assessment(db, user_id)

        if assessment is None:
            return json.dumps({
                "status": "error",
                "message": "Aucun bilan carbone trouve.",
            }, ensure_ascii=False)

        summary = await get_assessment_summary(db=db, assessment=assessment)

        return json.dumps({
            "status": "success",
            "summary": summary,
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("Erreur lors de la recuperation du resume carbone")
        return json.dumps({
            "status": "error",
            "message": f"Erreur lors de la recuperation du resume : {e}",
        }, ensure_ascii=False)


CARBON_TOOLS = [
    create_carbon_assessment,
    save_emission_entry,
    finalize_carbon_assessment,
    get_carbon_summary,
]
