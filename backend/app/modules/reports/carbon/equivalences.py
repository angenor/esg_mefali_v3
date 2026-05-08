"""F21 — Équivalences pédagogiques pour le rapport carbone.

Tous les facteurs sont sourcés (ADEME Base Carbone v23 / IPCC AR6) avec
flag ``unsourced`` quand aucune source vérifiée F01 n'est disponible. Le
fallback est ``« Recommandation générale (non sourcée) »`` (FR-016).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal


# Facteurs ADEME / IPCC (constants documentaires).
# 1 tCO2e équivalent à...
KM_VOITURE_PER_TCO2E: float = 5_700.0  # 1 tCO2e ≈ 5 700 km voiture moy. essence (ADEME).
VOLS_PARIS_NEW_YORK_PER_TCO2E: float = 1.0  # 1 vol AR Paris-NYC ≈ 1 tCO2e (ADEME).
FOYERS_PER_TCO2E: float = 0.4  # 1 tCO2e ≈ conso annuelle 0,4 foyer moyen UEMOA (IEA).
FCFA_ECONOMIES_PER_TCO2E: float = 30_000.0  # ~30 000 FCFA / tCO2e (prix carbone moyen marché Afrique).


@dataclass(frozen=True)
class Equivalence:
    """Une équivalence pédagogique sourcée."""

    label: str
    value: float
    unit: str
    source_id: uuid.UUID | None = None
    is_sourced: bool = False
    fallback_label: str | None = None


def compute_equivalences(
    total_tco2e: Decimal | float,
    sources: dict[str, uuid.UUID] | None = None,
) -> list[Equivalence]:
    """Calculer les équivalences pédagogiques pour un total tCO2e.

    Args:
        total_tco2e: empreinte totale en tonnes équivalent CO2.
        sources: mapping optionnel ``{equivalence_key: source_id}`` permettant
            d'associer chaque équivalence à une source vérifiée F01.
            Clés supportées : ``km_voiture``, ``vols``, ``foyers``, ``fcfa``.

    Returns:
        Liste de 4 ``Equivalence`` ; les non-sourcées portent
        ``is_sourced=False`` et ``fallback_label='Recommandation générale (non sourcée)'``.
    """
    sources = sources or {}
    total = float(total_tco2e or 0.0)
    fallback = "Recommandation générale (non sourcée)"

    items = [
        ("km_voiture", "Kilomètres en voiture essence", total * KM_VOITURE_PER_TCO2E, "km"),
        ("vols", "Vols aller-retour Paris–New York", total * VOLS_PARIS_NEW_YORK_PER_TCO2E, "vols"),
        ("foyers", "Foyers moyens UEMOA équivalents (1 an)", total * FOYERS_PER_TCO2E, "foyers"),
        ("fcfa", "Économies potentielles via crédits carbone", total * FCFA_ECONOMIES_PER_TCO2E, "FCFA"),
    ]

    out: list[Equivalence] = []
    for key, label, value, unit in items:
        sid = sources.get(key)
        out.append(
            Equivalence(
                label=label,
                value=round(value, 1),
                unit=unit,
                source_id=sid,
                is_sourced=sid is not None,
                fallback_label=None if sid is not None else fallback,
            )
        )
    return out


__all__ = ["Equivalence", "compute_equivalences"]
