"""Helper FX rates pour la conversion XOF↔EUR/USD/CDF (F10 widgets).

Fournit des taux de change statiques de fallback. La valeur officielle
XOF↔EUR est une parité fixe BCEAO (655.957). Les autres taux sont des
approximations à raffraîchir hebdomadairement post-MVP via une table
``referential_fx_rates`` ou un référentiel équivalent.

Pour MVP, l'endpoint ``GET /api/referential/fx-rates`` consomme ce helper
sans persistance ; le frontend marque un indicateur visuel discret « approx. »
quand les valeurs proviennent du fallback statique.
"""

from __future__ import annotations

# Parité fixe BCEAO/Banque de France (1 EUR = 655.957 XOF)
XOF_PER_EUR: float = 655.957

# Approximations à raffraîchir périodiquement (post-MVP via referential_fx_rates)
XOF_PER_USD: float = 600.0
XOF_PER_CDF: float = 0.35


def get_fx_rates() -> dict[str, float]:
    """Retourne les taux courants XOF / autres devises.

    Format : ``{"XOF_per_EUR": float, "XOF_per_USD": float, "XOF_per_CDF": float}``.

    Pour MVP, retourne uniquement les constants statiques (clarification 2026-05-07
    Q3 : pas d'appel API tiers temps réel). Une feature ultérieure pourra
    surcharger ce helper avec une lecture asynchrone d'une table
    ``referential_fx_rates`` (snapshot quotidien BCEAO/ECB).
    """
    return {
        "XOF_per_EUR": XOF_PER_EUR,
        "XOF_per_USD": XOF_PER_USD,
        "XOF_per_CDF": XOF_PER_CDF,
    }
