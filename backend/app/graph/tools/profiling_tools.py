"""Tools LangChain pour le noeud de profilage entreprise.

Deux tools exposes au LLM :
- update_company_profile : mise a jour partielle du profil
- get_company_profile : consultation du profil et completion
"""

import json
import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from app.graph.tools.common import get_db_and_user, with_retry
from app.models.company import SectorEnum
from app.modules.company.schemas import CompanyProfileUpdate
from app.modules.company.service import FIELD_LABELS, compute_completion

logger = logging.getLogger(__name__)


class UpdateCompanyProfileArgs(BaseModel):
    """Args strict pour update_company_profile (PATCH partiel)."""

    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(None, min_length=1, max_length=255)
    sector: SectorEnum | None = None
    sub_sector: str | None = Field(None, min_length=1, max_length=255)
    employee_count: int | None = Field(None, ge=0, le=100_000)
    annual_revenue_xof: int | None = Field(None, ge=0, le=10_000_000_000_000)
    city: str | None = Field(None, min_length=1, max_length=100)
    country: str | None = Field(None, min_length=1, max_length=100)
    year_founded: int | None = Field(None, ge=1900, le=2100)
    has_waste_management: bool | None = None
    has_energy_policy: bool | None = None
    has_gender_policy: bool | None = None
    has_training_program: bool | None = None
    has_financial_transparency: bool | None = None
    governance_structure: str | None = Field(None, min_length=1, max_length=2000)
    environmental_practices: str | None = Field(None, min_length=1, max_length=2000)
    social_practices: str | None = Field(None, min_length=1, max_length=2000)


class GetCompanyProfileArgs(BaseModel):
    """Args (vide) pour get_company_profile."""

    model_config = ConfigDict(extra="forbid")


@tool(args_schema=UpdateCompanyProfileArgs)
@with_retry(
    max_retries=1,
    node_name="profiling_node",
    fallback_message=(
        "Je n'arrive pas à formaliser cette mise à jour de profil. "
        "Pouvez-vous me reformuler ?"
    ),
)
async def update_company_profile(
    config: RunnableConfig,
    company_name: str | None = None,
    sector: str | None = None,
    sub_sector: str | None = None,
    employee_count: int | None = None,
    annual_revenue_xof: int | None = None,
    city: str | None = None,
    country: str | None = None,
    year_founded: int | None = None,
    has_waste_management: bool | None = None,
    has_energy_policy: bool | None = None,
    has_gender_policy: bool | None = None,
    has_training_program: bool | None = None,
    has_financial_transparency: bool | None = None,
    governance_structure: str | None = None,
    environmental_practices: str | None = None,
    social_practices: str | None = None,
) -> str:
    """Met a jour le profil entreprise (UPSERT partiel) avec les champs fournis.

    Use when:
    - fait identitaire/ESG fourni (nom, secteur, CA, politique).
    - persister un champ issu de `ask_interactive_question`.
    Don't use when:
    - consultation (utiliser `get_company_profile`).
    - aucun champ (utiliser `ask_interactive_question`).
    Exemple: "Solar Niger, 25 employes" -> update_company_profile(company_name='Solar Niger', employee_count=25).
    Anti: "Mon profil ?" -> NE PAS appeler.
    """
    from app.modules.company import service as company_service

    try:
        db, user_id = get_db_and_user(config)

        raw_updates: dict = {}
        local_vars = {
            "company_name": company_name,
            "sector": sector,
            "sub_sector": sub_sector,
            "employee_count": employee_count,
            "annual_revenue_xof": annual_revenue_xof,
            "city": city,
            "country": country,
            "year_founded": year_founded,
            "has_waste_management": has_waste_management,
            "has_energy_policy": has_energy_policy,
            "has_gender_policy": has_gender_policy,
            "has_training_program": has_training_program,
            "has_financial_transparency": has_financial_transparency,
            "governance_structure": governance_structure,
            "environmental_practices": environmental_practices,
            "social_practices": social_practices,
        }
        for field_name, value in local_vars.items():
            if value is not None:
                raw_updates[field_name] = value

        if not raw_updates:
            return "Aucun champ fourni pour la mise à jour."

        updates = CompanyProfileUpdate(**raw_updates)
        profile = await company_service.get_or_create_profile(db, user_id)
        updated_profile, changed_fields = await company_service.update_profile(
            db, profile, updates,
        )

        if not changed_fields:
            return "Aucun changement détecté (les valeurs sont identiques)."

        completion = compute_completion(updated_profile)

        field_lines = [
            f"- {cf['label']} : {cf['value']}"
            for cf in changed_fields
        ]
        fields_text = "\n".join(field_lines)

        sse_metadata = json.dumps({
            "__sse_profile__": True,
            "changed_fields": changed_fields,
            "completion": {
                "identity_completion": completion.identity_completion,
                "esg_completion": completion.esg_completion,
                "overall_completion": completion.overall_completion,
            },
        })

        return (
            f"Profil mis à jour avec succès :\n{fields_text}\n\n"
            f"Complétion : identité {completion.identity_completion}% | "
            f"ESG {completion.esg_completion}% | "
            f"global {completion.overall_completion}%\n\n"
            f"<!--SSE:{sse_metadata}-->"
        )

    except Exception as e:
        logger.exception("Erreur dans update_company_profile")
        return f"Erreur lors de la mise à jour du profil : {e}"


@tool(args_schema=GetCompanyProfileArgs)
async def get_company_profile(config: RunnableConfig) -> str:
    """Consulte le profil entreprise et son taux de completion (lecture seule).

    Use when:
    - "mon profil", "que manque-t-il".
    - decider du module a ouvrir (besoin secteur/taille).
    Don't use when:
    - nouveaux faits fournis (utiliser `update_company_profile`).
    - score ESG demande (utiliser `get_esg_assessment`).
    Exemple: "Montre mon profil" -> get_company_profile().
    Anti: "Mon CA est 50M FCFA" -> NE PAS appeler.
    """
    from app.modules.company import service as company_service

    try:
        db, user_id = get_db_and_user(config)

        profile = await company_service.get_profile(db, user_id)

        if profile is None:
            return (
                "Aucun profil entreprise trouvé. "
                "Partagez des informations sur votre entreprise pour commencer "
                "(nom, secteur, localisation, nombre d'employés, etc.)."
            )

        completion = compute_completion(profile)

        filled_lines: list[str] = []
        all_filled = completion.identity_fields.filled + completion.esg_fields.filled
        for field_name in all_filled:
            value = getattr(profile, field_name, None)
            if value is not None:
                display_value = value.value if hasattr(value, "value") else value
                label = FIELD_LABELS.get(field_name, field_name)
                filled_lines.append(f"- {label} : {display_value}")

        filled_text = "\n".join(filled_lines) if filled_lines else "Aucun champ rempli."

        all_missing = completion.identity_fields.missing + completion.esg_fields.missing
        missing_labels = [
            FIELD_LABELS.get(f, f) for f in all_missing
        ]
        missing_text = ", ".join(missing_labels) if missing_labels else "Aucun"

        return (
            f"Profil entreprise :\n{filled_text}\n\n"
            f"Complétion : identité {completion.identity_completion}% | "
            f"ESG {completion.esg_completion}% | "
            f"global {completion.overall_completion}%\n\n"
            f"Champs manquants : {missing_text}"
        )

    except Exception as e:
        logger.exception("Erreur dans get_company_profile")
        return f"Erreur lors de la consultation du profil : {e}"


PROFILING_TOOLS = [update_company_profile, get_company_profile]
