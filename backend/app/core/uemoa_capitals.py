"""F21 — Coordonnées des capitales UEMOA pour fallback géolocalisation intermédiaires.

Les 8 capitales UEMOA (Bénin, Burkina Faso, Côte d'Ivoire, Guinée-Bissau,
Mali, Niger, Sénégal, Togo). Source : Wikipedia / OpenStreetMap (Public Domain).

Usage : si un intermédiaire n'a ni latitude ni longitude renseignées, on
positionne son marker sur la capitale de son ``country`` (alpha-2 ou alpha-3).

Toute évolution future (zone plus large) passera par F09 admin et un seed
dédié — pas par mutation de cette constante.
"""

from __future__ import annotations


# Capitales UEMOA — (lat, lon).
UEMOA_CAPITAL_COORDINATES: dict[str, tuple[float, float]] = {
    # Bénin — Porto-Novo
    "BJ": (6.4969, 2.6289),
    "BEN": (6.4969, 2.6289),
    # Burkina Faso — Ouagadougou
    "BF": (12.3714, -1.5197),
    "BFA": (12.3714, -1.5197),
    # Côte d'Ivoire — Yamoussoukro (capitale officielle ; Abidjan = capitale économique)
    "CI": (6.8276, -5.2893),
    "CIV": (6.8276, -5.2893),
    # Guinée-Bissau — Bissau
    "GW": (11.8636, -15.5977),
    "GNB": (11.8636, -15.5977),
    # Mali — Bamako
    "ML": (12.6392, -8.0029),
    "MLI": (12.6392, -8.0029),
    # Niger — Niamey
    "NE": (13.5117, 2.1251),
    "NER": (13.5117, 2.1251),
    # Sénégal — Dakar
    "SN": (14.7167, -17.4677),
    "SEN": (14.7167, -17.4677),
    # Togo — Lomé
    "TG": (6.1725, 1.2314),
    "TGO": (6.1725, 1.2314),
}


def get_capital_coordinates(country: str | None) -> tuple[float, float] | None:
    """Retourner (lat, lon) de la capitale UEMOA pour un code pays.

    Accepte alpha-2 (`SN`) et alpha-3 (`SEN`). Insensible à la casse.
    Retourne ``None`` si le code n'est pas une capitale UEMOA.
    """
    if not country:
        return None
    return UEMOA_CAPITAL_COORDINATES.get(country.strip().upper())


__all__ = [
    "UEMOA_CAPITAL_COORDINATES",
    "get_capital_coordinates",
]
