"""F11 — Constante centroïdes pays UEMOA pour fallback géolocalisation.

8 pays UEMOA hardcodés (Bénin, Burkina Faso, Côte d'Ivoire, Guinée-Bissau,
Mali, Niger, Sénégal, Togo). Les coordonnées sont les centroïdes officiels
Natural Earth (Public Domain).

Usage : si un intermédiaire ou un fonds n'a pas de coordonnées précises,
``UEMOA_COUNTRY_CENTROIDS[country_iso3]`` fournit un fallback acceptable
(à accompagner d'un disclaimer "position approximative" côté front).

Toute évolution future (zone plus large que UEMOA) passera par F09 admin
et un seed dédié — pas par mutation de cette constante.
"""

from __future__ import annotations


# Centroïdes (lat, lon) — Natural Earth Public Domain.
UEMOA_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "BEN": (9.30769, 2.31583),     # Bénin
    "BFA": (12.23833, -1.56167),   # Burkina Faso
    "CIV": (7.53980, -5.54712),    # Côte d'Ivoire
    "GNB": (11.80372, -15.18041),  # Guinée-Bissau
    "MLI": (17.57046, -3.99617),   # Mali
    "NER": (17.60782, 8.08183),    # Niger
    "SEN": (14.49709, -14.45239),  # Sénégal
    "TGO": (8.61961, 0.82482),     # Togo
}


# Centre régional UEMOA pour défaut MapArgs.center (~ centre géographique).
UEMOA_REGION_CENTER: tuple[float, float] = (12.0, -2.0)


# Zoom Leaflet par défaut pour vue UEMOA complète (5 = continent, 6 = sous-zone).
UEMOA_DEFAULT_ZOOM: int = 5


__all__ = [
    "UEMOA_COUNTRY_CENTROIDS",
    "UEMOA_DEFAULT_ZOOM",
    "UEMOA_REGION_CENTER",
]
