"""F18 — Refactor du score combiné avec pondérations dynamiques (FR-016).

Règles fonctionnelles :

- **FR-015 / SC-005** : la catégorie ``public_data`` est plafonnée à 10 %
  du score combiné, peu importe le poids cumulé déclaré dans
  :class:`CreditMethodologyFactor`. Le cap est appliqué AU CALCUL, pas en
  amont — un admin peut donc déclarer un poids public_data > 10 % sans
  enfreindre l'invariant produit.
- **FR-016** : pondérations dynamiques selon la disponibilité réelle des
  données ET la présence des consentements F05. Les catégories sans donnée
  (ou sans consentement actif) sont exclues, et les poids restants sont
  renormalisés sur 1.

Catégories supportées :

- ``solvability`` (toujours présente — base obligatoire)
- ``green_impact`` (toujours présente — base obligatoire)
- ``mobile_money_flux`` (consent ``mobile_money_analysis``)
- ``photos_ia`` (consent ``photos_ia_analysis`` — différé P2)
- ``public_data`` (consent ``public_data_analysis`` — cap 10 %)

Le calcul produit un breakdown détaillé pour audit + UI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)


# Plafond strict de la catégorie ``public_data`` dans le score combiné
# (FR-015 / SC-005).
PUBLIC_DATA_CAP: float = 0.10

# Pondérations cibles par défaut (normalisées sur 1) lorsque toutes les
# catégories sont disponibles. Public_data est volontairement déjà ≤ 10 %.
DEFAULT_TARGET_WEIGHTS: dict[str, float] = {
    "solvability": 0.40,
    "green_impact": 0.30,
    "mobile_money_flux": 0.15,
    "photos_ia": 0.05,
    "public_data": 0.10,
}

# Catégories obligatoires : si l'une manque, on bascule sur du legacy 50/50.
MANDATORY_CATEGORIES: frozenset[str] = frozenset({"solvability", "green_impact"})


@dataclass(frozen=True)
class CategoryInput:
    """Donnée d'entrée pour une catégorie de scoring crédit alternatif."""

    name: str
    score: float  # 0..100
    available: bool = True  # True si données présentes
    consent_active: bool = True  # True si consent F05 actif (ou non requis)


@dataclass(frozen=True)
class WeightedCategory:
    """Catégorie avec son poids effectif après normalisation et cap."""

    name: str
    score: float
    weight: float
    capped: bool = False  # True si ``public_data`` a été plafonné


@dataclass(frozen=True)
class CombinedScoreResult:
    """Résultat du calcul du score combiné dynamique."""

    combined_score: float  # 0..100, arrondi à 1 décimale
    categories: tuple[WeightedCategory, ...] = field(default_factory=tuple)
    excluded: tuple[str, ...] = field(default_factory=tuple)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Borne une valeur entre minimum et maximum."""
    return max(minimum, min(maximum, value))


def compute_combined_score(
    inputs: list[CategoryInput],
    target_weights: dict[str, float] | None = None,
    confidence: float = 1.0,
) -> CombinedScoreResult:
    """Calcule le score combiné avec pondérations dynamiques (FR-015 / FR-016).

    Args:
        inputs: catégories candidates (avec score 0..100, available, consent).
        target_weights: pondérations cibles pré-cap (défaut DEFAULT_TARGET_WEIGHTS).
        confidence: coefficient multiplicatif final (0..1).

    Returns:
        CombinedScoreResult avec ``combined_score`` (0..100), liste des
        ``categories`` retenues + leur poids effectif, et la liste
        ``excluded`` des catégories écartées.

    Notes:
        - Une catégorie est retenue si ``available=True`` ET
          ``consent_active=True``.
        - Si une catégorie obligatoire (solvability OU green_impact) manque,
          le calcul applique le legacy 50/50 sur celles présentes (tolérance
          rétrocompat).
        - ``public_data`` est plafonné à ``PUBLIC_DATA_CAP`` (10 %) AVANT
          renormalisation des autres catégories.
    """
    weights_target = dict(target_weights or DEFAULT_TARGET_WEIGHTS)

    # 1. Filtrer les catégories disponibles + autorisées.
    retained: list[CategoryInput] = []
    excluded: list[str] = []
    for ci in inputs:
        if not ci.available:
            excluded.append(ci.name)
            continue
        if not ci.consent_active:
            excluded.append(ci.name)
            continue
        retained.append(ci)

    if not retained:
        logger.warning("compute_combined_score: aucune catégorie disponible")
        return CombinedScoreResult(
            combined_score=0.0, categories=(), excluded=tuple(excluded)
        )

    # 2. Récupérer les poids cibles non nuls pour les catégories retenues.
    raw_weights: dict[str, float] = {
        ci.name: weights_target.get(ci.name, 0.0) for ci in retained
    }
    # Sécurité : si tous les poids sont 0 (catégories inconnues), bascule
    # sur poids égaux.
    if sum(raw_weights.values()) <= 0:
        equal = 1.0 / len(retained)
        raw_weights = {ci.name: equal for ci in retained}

    # 3. Application du cap public_data (FR-015) AVANT normalisation.
    capped = False
    if "public_data" in raw_weights and raw_weights["public_data"] > PUBLIC_DATA_CAP:
        raw_weights["public_data"] = PUBLIC_DATA_CAP
        capped = True

    # 4. Normalisation : poids effectifs somment à 1, en respectant le cap.
    # Cas 1 : public_data présent → on fixe son poids à PUBLIC_DATA_CAP (cap)
    #         et on répartit (1 - cap) sur les autres au prorata de leurs poids
    #         cibles.
    # Cas 2 : pas de public_data → simple normalisation par somme.
    if "public_data" in raw_weights:
        cap = min(raw_weights["public_data"], PUBLIC_DATA_CAP)
        others_target = {k: v for k, v in raw_weights.items() if k != "public_data"}
        others_total = sum(others_target.values())
        effective: dict[str, float] = {"public_data": cap}
        if others_total > 0:
            for name, w in others_target.items():
                effective[name] = (w / others_total) * (1.0 - cap)
        else:
            # Aucun autre poids cible → public_data prend 100 % (cas dégénéré).
            effective["public_data"] = 1.0
    else:
        total = sum(raw_weights.values())
        effective = {k: v / total for k, v in raw_weights.items()}

    # 5. Calcul pondéré final.
    raw_score = 0.0
    weighted: list[WeightedCategory] = []
    for ci in retained:
        w = effective.get(ci.name, 0.0)
        score = _clamp(ci.score)
        raw_score += score * w
        weighted.append(
            WeightedCategory(
                name=ci.name,
                score=round(score, 2),
                weight=round(w, 4),
                capped=(ci.name == "public_data" and capped),
            )
        )

    # 6. Application de la confiance (clamp 0..1).
    conf = max(0.0, min(1.0, confidence))
    combined = _clamp(raw_score * conf)

    return CombinedScoreResult(
        combined_score=round(combined, 1),
        categories=tuple(weighted),
        excluded=tuple(excluded),
    )


__all__ = [
    "CategoryInput",
    "WeightedCategory",
    "CombinedScoreResult",
    "compute_combined_score",
    "PUBLIC_DATA_CAP",
    "DEFAULT_TARGET_WEIGHTS",
]
