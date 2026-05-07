"""Tools LangChain pour le noeud de financement vert.

Quatre tools exposes au LLM :
- search_compatible_funds : rechercher les fonds compatibles
- save_fund_interest : marquer un interet pour un fonds
- get_fund_details : consulter les details d'un fonds
- create_fund_application : creer une candidature
"""

import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


@tool
async def search_compatible_funds(config: RunnableConfig) -> str:
    """Recherche les fonds verts compatibles avec le profil (matching multi-criteres).

    Use when:
    - "quels financements ?", "subventions GCF/FEM/BOAD", "credit vert".
    - apres ESG/carbone, proposer des matches qualifies au prospect.
    Don't use when:
    - fond precis demande (utiliser `get_fund_details`).
    - candidature directe (utiliser `create_fund_application`).
    Exemple: "Quels fonds matchent mon entreprise ?" -> search_compatible_funds().
    Anti: "Detail du GCF" -> NE PAS appeler (utiliser `get_fund_details`).
    """
    from app.modules.company.service import get_profile
    from app.modules.financing.service import get_fund_matches

    try:
        db, user_id = get_db_and_user(config)

        # Recuperer le profil pour le matching
        profile = await get_profile(db, user_id)

        sector = None
        revenue = None
        country = None
        city = None
        if profile:
            sector = profile.sector
            if hasattr(sector, "value"):
                sector = sector.value
            revenue = profile.annual_revenue_xof
            country = profile.country
            city = profile.city

        matches = await get_fund_matches(
            db=db,
            user_id=user_id,
            company_sector=sector,
            company_revenue=revenue,
            company_country=country,
            company_city=city,
        )

        if not matches:
            return (
                "Aucun fonds compatible trouve. "
                "Completez votre profil entreprise et realisez une evaluation ESG "
                "pour ameliorer le matching."
            )

        lines: list[str] = [f"{len(matches)} fonds compatibles trouves :"]
        for m in matches[:5]:
            fund = m.fund
            fund_type = fund.fund_type.value if hasattr(fund.fund_type, "value") else fund.fund_type
            min_amt = f"{fund.min_amount_xof:,}" if fund.min_amount_xof else "N/A"
            max_amt = f"{fund.max_amount_xof:,}" if fund.max_amount_xof else "N/A"
            access = fund.access_type.value if hasattr(fund.access_type, "value") else fund.access_type
            lines.append(
                f"- {fund.name} ({fund_type}) — "
                f"score compatibilite : {m.compatibility_score}% — "
                f"montant : {min_amt}-{max_amt} FCFA — "
                f"acces : {access} — id={fund.id}"
            )

        if len(matches) > 5:
            lines.append(f"  ... et {len(matches) - 5} autres fonds.")

        return "\n".join(lines)

    except Exception as e:
        logger.exception("Erreur lors de la recherche de fonds compatibles")
        return f"Erreur lors de la recherche de fonds : {e}"


@tool
async def save_fund_interest(fund_id: str, config: RunnableConfig) -> str:
    """Enregistre l'interet de l'utilisateur pour un fonds (statut interested).

    Use when:
    - apres `search_compatible_funds`, l'utilisateur dit "ce fonds m'interesse".
    - tracking de l'engagement avant candidature.
    Don't use when:
    - candidature deja creee (utiliser `create_fund_application`).
    - simple consultation (utiliser `get_fund_details`).
    Exemple: "Le GCF m'interesse" -> save_fund_interest(fund_id=...).
    Anti: "Donne-moi les details du GCF" -> NE PAS appeler (utiliser `get_fund_details`).

    Args:
        fund_id: Identifiant UUID du fonds.
    """
    from app.modules.financing.service import get_match_by_fund, update_match_status

    try:
        db, user_id = get_db_and_user(config)

        match = await get_match_by_fund(db=db, user_id=user_id, fund_id=uuid.UUID(fund_id))

        if match is None:
            return (
                f"Aucun matching trouve pour le fonds {fund_id}. "
                "Lancez d'abord une recherche de fonds compatibles."
            )

        from app.models.financing import MatchStatus
        updated = await update_match_status(db=db, match=match, new_status=MatchStatus.interested)

        fund_name = match.fund.name if match.fund else fund_id

        return (
            f"Interet enregistre pour le fonds '{fund_name}'.\n"
            f"Vous pouvez maintenant creer un dossier de candidature "
            f"ou consulter les details de ce fonds."
        )

    except Exception as e:
        logger.exception("Erreur lors de l'enregistrement de l'interet pour le fonds %s", fund_id)
        return f"Erreur lors de l'enregistrement de l'interet : {e}"


@tool
async def get_fund_details(fund_id: str, config: RunnableConfig) -> str:
    """Consulte les details complets d'un fonds (criteres, montants, secteurs cibles).

    Use when:
    - "details du GCF", "criteres FEM", "que finance la BOAD".
    - apres matching, approfondir une fiche fonds avant decision.
    Don't use when:
    - matching demande (utiliser `search_compatible_funds`).
    - candidature directe (utiliser `create_fund_application`).
    Exemple: "Donne-moi les details du fonds GCF" -> get_fund_details(fund_id=...).
    Anti: "Quels fonds pour moi ?" -> NE PAS appeler (utiliser `search_compatible_funds`).

    Args:
        fund_id: Identifiant UUID du fonds.
    """
    from app.modules.financing.service import get_fund_by_id

    try:
        db, _user_id = get_db_and_user(config)

        fund = await get_fund_by_id(db=db, fund_id=uuid.UUID(fund_id))

        if fund is None:
            return f"Fonds introuvable (id={fund_id})."

        fund_type = fund.fund_type.value if hasattr(fund.fund_type, "value") else fund.fund_type
        sectors = ", ".join(fund.sectors_eligible) if fund.sectors_eligible else "Tous secteurs"
        eligibility = fund.eligibility_criteria or {}
        countries_list = eligibility.get("countries", [])
        countries = ", ".join(countries_list) if countries_list else "Tous pays"
        access = fund.access_type.value if hasattr(fund.access_type, "value") else fund.access_type
        status = fund.status.value if hasattr(fund.status, "value") else fund.status

        # Formater les montants
        min_amt = f"{fund.min_amount_xof:,}" if fund.min_amount_xof else "N/A"
        max_amt = f"{fund.max_amount_xof:,}" if fund.max_amount_xof else "N/A"

        # Recuperer les intermediaires lies
        intermediaries_text = ""
        if fund.fund_intermediaries:
            interm_names = []
            for fi in fund.fund_intermediaries:
                if fi.intermediary:
                    interm_names.append(f"{fi.intermediary.name} (id={fi.intermediary.id})")
            if interm_names:
                intermediaries_text = f"- Intermediaires : {', '.join(interm_names)}\n"

        return (
            f"Details du fonds :\n"
            f"- Nom : {fund.name}\n"
            f"- Organisation : {fund.organization}\n"
            f"- Type : {fund_type}\n"
            f"- Description : {fund.description or 'N/A'}\n"
            f"- Montant : {min_amt} - {max_amt} FCFA\n"
            f"- Secteurs : {sectors}\n"
            f"- Pays eligibles : {countries}\n"
            f"- Acces : {access}\n"
            f"{intermediaries_text}"
            f"- Statut : {status}"
        )

    except Exception as e:
        logger.exception("Erreur lors de la consultation du fonds %s", fund_id)
        return f"Erreur lors de la consultation du fonds : {e}"


@tool
async def create_fund_application(
    fund_id: str,
    config: RunnableConfig,
    intermediary_id: str | None = None,
) -> str:
    """Cree un dossier de candidature (statut draft) pour un fonds vert (mode legacy financing).

    Use when:
    - "je veux candidater au GCF", "demarrer un dossier".
    - apres `save_fund_interest`, l'utilisateur passe a l'action.
    Don't use when:
    - simple consultation (utiliser `get_fund_details`).
    - simulation financiere (utiliser `simulate_financing`).
    Exemple: "Cree un dossier pour le GCF" -> create_fund_application(fund_id=...).
    Anti: "Detail du fonds" -> NE PAS appeler (utiliser `get_fund_details`).

    Note: ce tool est aussi exporte par ``application_tools.create_fund_application``
    (variante avec ``offer_id``/`project_id``). En cas d'offer_id, preferer la
    version application.

    Args:
        fund_id: Identifiant UUID du fonds cible.
        intermediary_id: Identifiant UUID de l'intermediaire (optionnel).
    """
    from app.modules.applications.service import create_application

    try:
        db, user_id = get_db_and_user(config)

        interm_uuid = uuid.UUID(intermediary_id) if intermediary_id else None

        application = await create_application(
            db=db,
            user_id=user_id,
            fund_id=uuid.UUID(fund_id),
            intermediary_id=interm_uuid,
        )

        return (
            f"Dossier de candidature cree avec succes !\n"
            f"- ID : {application.id}\n"
            f"- Statut : {application.status}\n"
            f"Vous pouvez maintenant generer les sections du dossier."
        )

    except Exception as e:
        logger.exception("Erreur lors de la creation du dossier de candidature")
        return f"Erreur lors de la creation du dossier : {e}"


# --- F07 — Tools Offres (Couple Fonds × Intermédiaire) ---


@tool
async def list_offers(
    config: RunnableConfig,
    fund_id: str | None = None,
    intermediary_id: str | None = None,
    country: str | None = None,
    limit: int = 10,
) -> str:
    """Liste les offres (couples Fonds x Intermediaire) publiees et actives.

    Use when:
    - exploration du catalogue offres (filtres par fonds/intermediaire/pays).
    - presenter une short-list d'offres avant matching personnalise.
    Don't use when:
    - matching personnalise demande (utiliser `search_compatible_funds`).
    - detail d'une offre (utiliser `get_offer`).
    Exemple: "Liste les offres GCF" -> list_offers(fund_id=...).
    Anti: "Quelle offre pour mon profil ?" -> NE PAS appeler (utiliser `search_compatible_funds`).

    Une Offre est l'unite commercialement actionnable cote PME : c'est ce qui
    peut etre candidate. Filtrable par fonds, intermediaire ou pays.

    Args:
        fund_id: Filtre optionnel par UUID de fonds.
        intermediary_id: Filtre optionnel par UUID d'intermediaire.
        country: Filtre optionnel par pays de l'intermediaire.
        limit: Nombre maximum d'offres (defaut 10, max 50).
    """
    from app.modules.offers.service import list_offers as svc_list_offers

    try:
        db, _user_id = get_db_and_user(config)
        fid = uuid.UUID(fund_id) if fund_id else None
        iid = uuid.UUID(intermediary_id) if intermediary_id else None

        offers, total = await svc_list_offers(
            db,
            fund_id=fid,
            intermediary_id=iid,
            country=country,
            include_drafts=False,
            limit=min(limit, 50),
        )
        if not offers:
            return "Aucune offre publiée trouvée pour ces critères."

        lines = [f"{total} offre(s) trouvée(s) (top {len(offers)}) :"]
        for o in offers:
            languages = ",".join(o.accepted_languages or ["FR"])
            proc = (
                f"{o.effective_processing_time_days_min}-"
                f"{o.effective_processing_time_days_max}j"
                if o.effective_processing_time_days_min else "N/A"
            )
            lines.append(
                f"- {o.name} (id={o.id}) — langues={languages}, délai={proc}"
            )
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        logger.exception("Erreur lors de la liste des offres")
        return f"Erreur lors de la liste des offres : {e}"


@tool
async def get_offer(offer_id: str, config: RunnableConfig) -> str:
    """Recupere le detail d'une offre (Fonds x Intermediaire) par son UUID.

    Use when:
    - apres `list_offers` ou `compare_offers_for_fund`, approfondir une offre.
    - decider de candidater apres consultation des criteres precis.
    Don't use when:
    - exploration generale (utiliser `list_offers`).
    - candidature directe (utiliser `create_fund_application`).
    Exemple: "Detail de l'offre 8a3f..." -> get_offer(offer_id='8a3f-...').
    Anti: "Quelles offres GCF ?" -> NE PAS appeler (utiliser `list_offers`).

    Args:
        offer_id: UUID de l'offre.
    """
    from app.modules.offers.service import get_offer as svc_get_offer

    try:
        db, _user_id = get_db_and_user(config)
        offer = await svc_get_offer(db, uuid.UUID(offer_id), include_drafts=False)
        if offer is None:
            return f"Offre introuvable ou non publiée (id={offer_id})."

        fund = offer.fund
        intermediary = offer.intermediary
        languages = ",".join(offer.accepted_languages or ["FR"])
        docs_count = len(offer.effective_required_documents or [])
        return (
            f"Détail de l'offre :\n"
            f"- Nom : {offer.name}\n"
            f"- Fonds : {fund.name if fund else 'N/A'}\n"
            f"- Intermédiaire : {intermediary.name if intermediary else 'N/A'} "
            f"({intermediary.country if intermediary else 'N/A'})\n"
            f"- Langues acceptées : {languages}\n"
            f"- Documents requis : {docs_count}\n"
            f"- Délai traitement (jours) : "
            f"{offer.effective_processing_time_days_min}-"
            f"{offer.effective_processing_time_days_max}\n"
            f"- Statut : {offer.publication_status}"
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Erreur lors de la consultation de l'offre %s", offer_id)
        return f"Erreur lors de la consultation de l'offre : {e}"


@tool
async def compare_offers_for_fund(fund_id: str, config: RunnableConfig) -> str:
    """Compare cote-a-cote toutes les offres (Fonds x Intermediaires) publiees pour un fonds.

    Use when:
    - "compare GCF via BOAD vs UNDP", "quel intermediaire choisir".
    - decision sur l'intermediaire optimal pour un fonds donne.
    Don't use when:
    - liste exploratoire (utiliser `list_offers`).
    - detail d'une offre precise (utiliser `get_offer`).
    Exemple: "Compare les offres pour le GCF" -> compare_offers_for_fund(fund_id=...).
    Anti: "Liste des offres" -> NE PAS appeler (utiliser `list_offers`).

    Args:
        fund_id: UUID du fonds.
    """
    from app.modules.offers.service import (
        compare_offers_for_fund as svc_compare,
    )

    try:
        db, _user_id = get_db_and_user(config)
        comparisons = await svc_compare(db, fund_id=uuid.UUID(fund_id))
        if not comparisons:
            return f"Aucune offre publiée pour le fonds {fund_id}."

        lines = [f"{len(comparisons)} offre(s) à comparer pour ce fonds :"]
        for c in comparisons:
            fees_str = "N/A"
            if c.effective_fees_total_min:
                fees_str = (
                    f"{c.effective_fees_total_min.amount} "
                    f"{c.effective_fees_total_min.currency}"
                )
            lines.append(
                f"- {c.name} via {c.intermediary_name} ({c.intermediary_country}) — "
                f"frais {fees_str}, délai {c.effective_processing_time_days_min or '?'}-"
                f"{c.effective_processing_time_days_max or '?'}j, "
                f"docs {c.documents_count}"
            )
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        logger.exception("Erreur lors de la comparaison des offres pour %s", fund_id)
        return f"Erreur lors de la comparaison : {e}"


FINANCING_TOOLS = [
    search_compatible_funds,
    save_fund_interest,
    get_fund_details,
    create_fund_application,
    list_offers,
    get_offer,
    compare_offers_for_fund,
]
