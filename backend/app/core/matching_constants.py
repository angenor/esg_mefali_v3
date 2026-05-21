"""F045 - Constantes FR partagees pour le matching projet-centric.

Whitelists applicatives FR (avec accents) pour les nouveaux champs projet
``gcf_priority_themes`` et ``vulnerable_populations``. Source de verite
backend Python ; le frontend regenere ``matching_enums.generated.ts``
via ``frontend/scripts/sync-matching-constants.ts``.

Reference : research.md R2, R4, R9 de specs/045-matching-projet-centric/.
"""

from __future__ import annotations


PROJECT_GCF_PRIORITY_THEMES_VALUES: frozenset[str] = frozenset({
    "atténuation",
    "adaptation",
    "cross_cutting",
    "REDD+",
    "forêts",
    "eau",
    "agriculture",
    "énergie",
})


PROJECT_VULNERABLE_POPULATIONS_VALUES: frozenset[str] = frozenset({
    "femmes",
    "jeunes",
    "handicapés",
    "réfugiés",
    "déplacés_internes",
})
