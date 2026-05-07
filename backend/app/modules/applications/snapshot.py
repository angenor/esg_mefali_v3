"""F04 — Construction et validation du snapshot immuable d'une candidature.

Le snapshot capture, à la transition ``submitted_*``, l'intégralité des
éléments nécessaires pour reproduire le score d'origine (référentiel,
indicateurs, fonds, intermédiaire, scores, documents requis, sources).

Le format du JSON est documenté dans :file:`research.md` §R-10 et
:file:`data-model.md` §3.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import FundApplication
from app.models.esg import ESGAssessment
from app.models.financing import Fund, Intermediary
from app.models.referential import Referential
from app.models.required_document import RequiredDocument


logger = logging.getLogger(__name__)


SNAPSHOT_SCHEMA_VERSION = "1.0"
# Seuil au-delà duquel le snapshot est loggé en warning (cf. R-3 garde-fou).
SNAPSHOT_WARN_SIZE_BYTES = 100 * 1024  # 100 KB


class SnapshotImmutableError(Exception):
    """Tentative de modification d'un snapshot déjà créé (interdit, FR-012)."""


class SnapshotMissingError(Exception):
    """Le snapshot est requis pour cette opération (FR-014, HTTP 409)."""


def _serialize_fund(fund: Fund) -> dict:
    """Sérialise un Fund (champs publics + Money typed + version)."""
    return {
        "id": str(fund.id),
        "name": fund.name,
        "organization": fund.organization,
        "fund_type": fund.fund_type.value if fund.fund_type else None,
        "version": getattr(fund, "version", "1.0"),
        "valid_from": (
            fund.valid_from.isoformat() if getattr(fund, "valid_from", None) else None
        ),
        "min_amount": (
            str(fund.min_amount) if fund.min_amount is not None else None
        ),
        "min_amount_currency": fund.min_amount_currency,
        "max_amount": (
            str(fund.max_amount) if fund.max_amount is not None else None
        ),
        "max_amount_currency": fund.max_amount_currency,
        "min_amount_xof": fund.min_amount_xof,
        "max_amount_xof": fund.max_amount_xof,
        "esg_requirements": fund.esg_requirements or {},
        "sectors_eligible": fund.sectors_eligible or [],
    }


def _serialize_intermediary(intermediary: Intermediary | None) -> dict | None:
    if intermediary is None:
        return None
    return {
        "id": str(intermediary.id),
        "name": intermediary.name,
        "version": getattr(intermediary, "version", "1.0"),
        "country": intermediary.country,
        "city": intermediary.city,
        "intermediary_type": (
            intermediary.intermediary_type.value
            if intermediary.intermediary_type
            else None
        ),
        "typical_fees": intermediary.typical_fees,
    }


def _serialize_referential(referential: Referential | None) -> dict | None:
    if referential is None:
        return None
    return {
        "id": str(referential.id),
        "code": referential.code,
        "label": referential.label,
        "version": getattr(referential, "version", "1.0"),
        "valid_from": (
            referential.valid_from.isoformat()
            if getattr(referential, "valid_from", None)
            else None
        ),
        "valid_to": (
            referential.valid_to.isoformat()
            if getattr(referential, "valid_to", None)
            else None
        ),
        "indicators": [],  # Voir build_snapshot_data pour la requête détaillée.
        "documents_requis": [],
    }


def _serialize_scores_from_esg(esg: ESGAssessment | None) -> dict:
    """Construit le bloc scores depuis l'ESGAssessment associé (best-effort).

    En l'absence d'évaluation, retourne un dict vide (sera rempli plus tard
    par d'autres scores : carbone, crédit).
    """
    if esg is None:
        return {
            "esg_total": None,
            "esg_breakdown": {},
            "credit_score": None,
            "carbon_total_tco2e": None,
        }
    return {
        "esg_total": esg.overall_score,
        "esg_breakdown": {
            "environment": esg.environment_score,
            "social": esg.social_score,
            "governance": esg.governance_score,
        },
        "credit_score": None,
        "carbon_total_tco2e": None,
    }


async def build_snapshot_data(
    application_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """Construit la structure JSON autoportante du snapshot.

    Lève une exception si la candidature n'existe pas. Retourne un dict
    sérialisable JSON (pas de Decimal/datetime brut).
    """
    application = await session.get(FundApplication, application_id)
    if application is None:
        raise ValueError(f"FundApplication {application_id} not found")

    fund = await session.get(Fund, application.fund_id) if application.fund_id else None
    intermediary = (
        await session.get(Intermediary, application.intermediary_id)
        if application.intermediary_id
        else None
    )

    # Charger l'ESGAssessment de l'utilisateur (best-effort, le plus récent).
    esg_result = await session.execute(
        select(ESGAssessment)
        .where(ESGAssessment.user_id == application.user_id)
        .order_by(ESGAssessment.created_at.desc())
        .limit(1),
    )
    esg = esg_result.scalar_one_or_none()

    # Charger les documents requis associés au fonds.
    docs_result = await session.execute(
        select(RequiredDocument).where(
            RequiredDocument.fund_id == application.fund_id,
        ),
    )
    required_docs = list(docs_result.scalars().all())

    snapshot: dict = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "referential": None,  # Pas de FK directe Referential ↔ Application.
        "fund": _serialize_fund(fund) if fund else None,
        "intermediary": _serialize_intermediary(intermediary),
        "offer": (
            {
                "fund_id": str(fund.id) if fund else None,
                "intermediary_id": (
                    str(intermediary.id) if intermediary else None
                ),
            }
            if fund
            else None
        ),
        "scores": _serialize_scores_from_esg(esg),
        "documents_requis_at_submission": [
            {
                "id": str(d.id),
                "label": d.label,
                "version": getattr(d, "version", "1.0"),
            }
            for d in required_docs
        ],
        "source_ids_cited": [],  # Rempli par le moteur de scoring F01 si dispo
    }
    return snapshot


def validate_immutable(existing: dict | None, new: dict | None) -> None:
    """Refuse toute mutation du snapshot après création.

    Une seule exception : ``existing`` à ``None`` (création initiale autorisée).
    """
    if existing is None:
        return
    if new is None:
        raise SnapshotImmutableError(
            "snapshot_data cannot be reset to None after creation",
        )
    if existing != new:
        raise SnapshotImmutableError(
            "snapshot_data is immutable; "
            "existing snapshot differs from update payload",
        )


def estimate_snapshot_size_bytes(snapshot: dict) -> int:
    """Renvoie la taille approximative en bytes de la sérialisation JSON.

    Utilisée pour le log d'observabilité (T707) et le warning > 100 KB.
    """
    import json

    return len(json.dumps(snapshot, ensure_ascii=False).encode("utf-8"))
