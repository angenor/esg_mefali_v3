"""F18 — Tools LangChain crédit alternatif (lecture seule).

Trois tools exposés au LLM, **lecture seule** (jamais de mutation
catalogue ni création/suppression de données utilisateur — la collecte se
fait via des endpoints REST avec consent gating F05) :

- :func:`get_credit_methodology` : retourne la méthodologie publique v1.2
  (facteurs publiés + sources F01).
- :func:`get_mobile_money_kpis` : retourne les KPIs Mobile Money courants
  de la PME (consent ``mobile_money_analysis`` requis).
- :func:`list_public_data_sources` : retourne les sources publiques
  déclarées (consent ``public_data_analysis`` requis).

Invariants :
- Aucun tool de ce module ne mute le catalogue
  ``CreditMethodologyFactor`` (admin only via back-office).
- Les tools tenant vérifient ``account_id`` + RLS via la session.
"""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import select

from app.core.consent import require_consent
from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


async def _resolve_account_id(db, user_id):
    """Charge le ``account_id`` du user (None si admin sans tenant)."""
    from app.models.user import User

    result = await db.execute(select(User.account_id).where(User.id == user_id))
    return result.scalar_one_or_none()


@tool
async def get_credit_methodology(config: RunnableConfig) -> str:
    """Lit la méthodologie publique du scoring crédit alternatif (v1.2).

    Use when:
    - "comment est calculé mon score crédit ?", "méthodologie scoring".
    - le prospect veut comprendre les pondérations (transparence FR-018).
    Don't use when:
    - le prospect veut SON score (utiliser ``get_credit_score``).
    Exemple: "Comment marche le score crédit ?" -> get_credit_methodology().

    Retourne la liste des facteurs publiés avec poids et catégorie.
    Aucune mutation possible (catalogue admin-only).
    """
    try:
        db, _user_id = get_db_and_user(config)
        from app.modules.credit.alternative.methodology_service import (
            list_published_factors,
            total_weight,
        )

        factors = await list_published_factors(db)
        if not factors:
            return (
                "La méthodologie publique du scoring crédit n'est pas encore "
                "disponible. Réessayez plus tard."
            )
        lines = [
            f"Méthodologie scoring crédit v{factors[0].version} "
            f"({len(factors)} facteurs, poids cumulé {total_weight(factors)}) :",
        ]
        for f in factors:
            lines.append(
                f"- {f.name} ({f.category}) — poids {f.weight} — {f.description}"
            )
        lines.append(
            "\nNote : la catégorie 'public_data' est plafonnée à 10 % du "
            "score combiné (FR-015). Le détail des sources est consultable "
            "sur /credit/methodology."
        )
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("get_credit_methodology_failed")
        return f"Erreur lors de la lecture de la méthodologie : {exc}"


@tool
async def get_mobile_money_kpis(config: RunnableConfig) -> str:
    """Lit les KPIs Mobile Money courants de la PME (consent requis).

    Use when:
    - "quels sont mes KPIs Mobile Money ?", "régularité de mes flux MM".
    - après un upload Mobile Money réussi, communiquer la synthèse.
    Don't use when:
    - aucune donnée Mobile Money chargée (le tool retourne un message clair).
    Exemple: "Que disent mes flux Mobile Money ?" -> get_mobile_money_kpis().

    Vérifie le consentement ``mobile_money_analysis`` au runtime (F05).
    Retourne les 7 KPIs (régularité, volume, croissance, top contre-parties).
    """
    try:
        db, user_id = get_db_and_user(config)
        account_id = await _resolve_account_id(db, user_id)
        if account_id is None:
            return "Aucun compte rattaché : impossible de lire les KPIs."

        # Consent gating F05 — lève HTTPException(403) si absent.
        await require_consent(db, account_id, "mobile_money_analysis")

        from app.models.credit_alternative import MobileMoneyAnalysis

        stmt = (
            select(MobileMoneyAnalysis)
            .where(MobileMoneyAnalysis.account_id == account_id)
            .order_by(MobileMoneyAnalysis.computed_at.desc())
            .limit(1)
        )
        analysis = (await db.execute(stmt)).scalar_one_or_none()
        if analysis is None:
            return (
                "Aucune analyse Mobile Money disponible. Téléversez d'abord "
                "un fichier Wave / Orange Money / MTN / Moov sur "
                "/credit/mobile-money."
            )
        kpis = analysis.kpis or {}
        return (
            f"KPIs Mobile Money (méthodologie v{analysis.methodology_version}) :\n"
            f"- Volume mensuel moyen : {kpis.get('monthly_volume_avg', '0.00')} XOF\n"
            f"- Régularité 30j : {kpis.get('regularity_30d', 0)}\n"
            f"- Croissance 12 mois : {kpis.get('growth_12m', 0)}\n"
            f"- Solde moyen estimé : {kpis.get('avg_balance_estimate', '0.00')} XOF\n"
            f"- {kpis.get('transaction_count', 0)} transactions sur la période\n"
            f"- Top {len(kpis.get('top_counterparties', []))} contre-parties anonymisées."
        )
    except Exception as exc:
        # Cas explicite consent_required (HTTPException 403)
        if "Consentement" in str(exc) or "consent" in str(exc).lower():
            return (
                "Le consentement 'Analyse Mobile Money' n'est pas actif. "
                "Activez-le sur /mes-donnees/consentements pour analyser vos KPIs."
            )
        logger.exception("get_mobile_money_kpis_failed")
        return f"Erreur lors de la lecture des KPIs Mobile Money : {exc}"


@tool
async def list_public_data_sources(config: RunnableConfig) -> str:
    """Liste les sources publiques déclarées par la PME (consent requis).

    Use when:
    - "quelles sources publiques j'ai déclarées ?".
    - inventaire pour le rapport ESG / scoring crédit.
    Don't use when:
    - le prospect veut DÉCLARER une nouvelle source (utiliser l'endpoint
      REST POST /api/credit/public-data/declare via le widget UI).
    Exemple: "Mes sources publiques ?" -> list_public_data_sources().

    Vérifie le consentement ``public_data_analysis`` au runtime (F05).
    Lecture seule (la mutation passe par les endpoints REST + consent).
    """
    try:
        db, user_id = get_db_and_user(config)
        account_id = await _resolve_account_id(db, user_id)
        if account_id is None:
            return "Aucun compte rattaché : impossible de lister les sources."

        await require_consent(db, account_id, "public_data_analysis")

        from app.models.credit_alternative import PublicDataSource

        stmt = (
            select(PublicDataSource)
            .where(
                PublicDataSource.account_id == account_id,
                PublicDataSource.unused.is_(False),
            )
            .order_by(PublicDataSource.created_at.desc())
        )
        sources = list((await db.execute(stmt)).scalars().all())
        if not sources:
            return (
                "Aucune source publique déclarée. Vous pouvez en ajouter "
                "(Google My Business, Trustpilot, programmes verts) sur "
                "/credit/public-data."
            )
        lines = [f"{len(sources)} source(s) publique(s) déclarée(s) :"]
        for s in sources:
            rating = (
                f"note {s.declared_rating}/5"
                if s.declared_rating is not None
                else "note non déclarée"
            )
            reviews = (
                f", {s.declared_reviews_count} avis"
                if s.declared_reviews_count is not None
                else ""
            )
            lines.append(
                f"- {s.source_type} ({s.url}) — {rating}{reviews} — "
                f"statut {s.status}"
            )
        lines.append(
            "\nLe poids cumulé de ces sources est plafonné à 10 % du score "
            "combiné (badge 'données déclaratives non vérifiées')."
        )
        return "\n".join(lines)
    except Exception as exc:
        if "Consentement" in str(exc) or "consent" in str(exc).lower():
            return (
                "Le consentement 'Données publiques' n'est pas actif. "
                "Activez-le sur /mes-donnees/consentements."
            )
        logger.exception("list_public_data_sources_failed")
        return f"Erreur lors de la lecture des sources publiques : {exc}"


CREDIT_ALTERNATIVE_TOOLS = [
    get_credit_methodology,
    get_mobile_money_kpis,
    list_public_data_sources,
]


__all__ = [
    "get_credit_methodology",
    "get_mobile_money_kpis",
    "list_public_data_sources",
    "CREDIT_ALTERNATIVE_TOOLS",
]
