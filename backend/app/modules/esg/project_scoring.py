"""F047 — Calcul du score 0..100 d'une évaluation ESG-projet.

Formule pondérée (research.md D9) :

    score = round(100 * Σ(normalized_score_i × criterion.weight_i)
                       / Σ(criterion.weight_i))

Tous les critères répondus participent au numérateur et au dénominateur ;
les critères obligatoires manquants sont signalés séparément par le service.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator import Criterion
from app.modules.esg.project_models import (
    ProjectEsgAssessment,
    ProjectEsgCriterionResponse,
)


def normalize_response(response_type: str, response_value: dict[str, Any]) -> Decimal:
    """Convertit une réponse typée en score normalisé [0,1].

    Heuristique MVP — adapté plus finement par référentiel ultérieurement :
    - ``qcu`` / ``qcm`` : "yes"/"true"/"oui" → 1.0 ; "no"/"false"/"non" → 0.0 ;
      sinon 0.5 (réponse partielle).
    - ``qcu_justification`` / ``qcm_justification`` : idem + bonus 0.1 si
      justification ≥ 20 caractères (max 1.0).
    - ``numeric`` : ``value`` ∈ [0,1] direct ; clampé sinon.
    - ``money`` : présence d'un montant > 0 → 1.0 ; sinon 0.0.
    - ``free_text`` : texte ≥ 20 caractères → 0.7 ; sinon 0.3.
    """
    rt = response_type
    val = response_value or {}

    if rt in ("qcu", "qcm", "qcu_justification", "qcm_justification"):
        choice = str(val.get("choice", "")).strip().lower()
        choices = [str(c).strip().lower() for c in val.get("choices", [])]
        all_choices = ([choice] if choice else []) + choices
        positives = {"yes", "true", "oui", "1"}
        negatives = {"no", "false", "non", "0"}
        if any(c in positives for c in all_choices):
            base = Decimal("1.0")
        elif any(c in negatives for c in all_choices):
            base = Decimal("0.0")
        else:
            base = Decimal("0.5") if all_choices else Decimal("0.0")
        if rt.endswith("justification"):
            justification = str(val.get("justification", ""))
            if len(justification) >= 20:
                base = min(Decimal("1.0"), base + Decimal("0.1"))
        return base

    if rt == "numeric":
        try:
            v = Decimal(str(val.get("value", 0)))
        except (TypeError, ValueError):
            return Decimal("0")
        return max(Decimal("0"), min(Decimal("1"), v))

    if rt == "money":
        try:
            amount = Decimal(str(val.get("amount", 0)))
        except (TypeError, ValueError):
            return Decimal("0")
        return Decimal("1.0") if amount > 0 else Decimal("0.0")

    if rt == "free_text":
        text = str(val.get("text", ""))
        return Decimal("0.7") if len(text) >= 20 else Decimal("0.3")

    return Decimal("0")


async def compute_score(
    db: AsyncSession, assessment_id: uuid.UUID,
) -> dict[str, Any]:
    """Agrège les réponses persistées et retourne le score + breakdown.

    Returns:
        ``{score: int 0..100, pillar_scores: dict, covered_criteria: list[UUID],
        missing_criteria: list[UUID], coverage_rate: Decimal 0..1}``
    """
    # 1) Charger l'évaluation + son référentiel
    assessment = (
        await db.execute(
            select(ProjectEsgAssessment).where(ProjectEsgAssessment.id == assessment_id)
        )
    ).scalar_one()

    # 2) Charger tous les critères applicables au référentiel cible
    criteria_rows = (
        await db.execute(
            select(Criterion).where(
                Criterion.referential_id == assessment.referential_id,
                Criterion.applies_to_project.is_(True),
            )
        )
    ).scalars().all()
    criteria_by_id: dict[uuid.UUID, Criterion] = {c.id: c for c in criteria_rows}

    # 3) Charger les réponses pour cette évaluation
    responses = (
        await db.execute(
            select(ProjectEsgCriterionResponse).where(
                ProjectEsgCriterionResponse.assessment_id == assessment_id
            )
        )
    ).scalars().all()

    # 4) Calculer score pondéré (uniquement critères répondus du référentiel)
    total_weight = Decimal("0")
    weighted_sum = Decimal("0")
    covered: set[uuid.UUID] = set()
    pillar_acc: dict[str, list[tuple[Decimal, Decimal]]] = {}

    for r in responses:
        crit = criteria_by_id.get(r.criterion_id)
        if crit is None:
            # Critère hors référentiel ciblé : ignoré pour le score
            continue
        weight = Decimal(str(crit.weight))
        score_norm = Decimal(str(r.normalized_score))
        weighted_sum += score_norm * weight
        total_weight += weight
        covered.add(r.criterion_id)

        # Pillar dérivé du préfixe du code (ex: "IFCPS1-A" → "PS1")
        pillar_key = crit.code.split("-")[0]
        pillar_acc.setdefault(pillar_key, []).append((score_norm, weight))

    score = (
        int(round(100 * float(weighted_sum / total_weight)))
        if total_weight > 0
        else 0
    )

    pillar_scores: dict[str, int] = {}
    for key, items in pillar_acc.items():
        tot_w = sum((w for _, w in items), Decimal("0"))
        if tot_w == 0:
            continue
        wsum = sum((s * w for s, w in items), Decimal("0"))
        pillar_scores[key] = int(round(100 * float(wsum / tot_w)))

    # 5) Critères manquants (parmi ceux applicables au référentiel)
    missing = [cid for cid in criteria_by_id if cid not in covered]

    coverage_rate = (
        Decimal(len(covered)) / Decimal(len(criteria_by_id))
        if criteria_by_id
        else Decimal("0")
    )

    return {
        "score": score,
        "pillar_scores": pillar_scores,
        "covered_criteria": sorted(covered, key=str),
        "missing_criteria": sorted(missing, key=str),
        "coverage_rate": coverage_rate.quantize(Decimal("0.001")),
    }


def missing_required_criteria(
    criteria_all: list[Criterion],
    covered_ids: set[uuid.UUID],
) -> list[Criterion]:
    """Liste les critères ``is_required=True`` non couverts (pour finalisation)."""
    return [c for c in criteria_all if c.is_required and c.id not in covered_ids]
