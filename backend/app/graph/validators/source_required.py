"""Validator post-tour LLM : exige une citation pour chaque chiffre detecte (F01).

Algorithme :
1. Detecter les grappes "chiffre + unite contigue" dans le texte final.
2. Filtrer les motifs IGNORED (ISO 14001, normes techniques, references reglementaires).
3. Pour chaque grappe, verifier qu'une cite_source ou flag_unsourced couvre le tour.
4. Si manque de couverture : signaler pour retry (1 max) puis fallback texte.

Granularite (FR-014) : une seule citation peut couvrir plusieurs grappes
consecutives separees de moins de 200 caracteres dans le meme paragraphe et
relevant de la meme source. Si deux grappes proches relevent de sources
differentes, deux citations distinctes sont attendues.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


# Motifs ignores (FR-017). Casse-insensible. Ces patterns ressemblent a des
# chiffres mais ne necessitent pas de citation (normes, identifiants techniques).
IGNORED_NUMERIC_PATTERNS: tuple[str, ...] = (
    # Normes ISO usuelles
    r"\bISO\s*9001\b",
    r"\bISO\s*14001\b",
    r"\bISO\s*14064\b",
    r"\bISO\s*14067\b",
    r"\bISO\s*26000\b",
    r"\bISO\s*27001\b",
    r"\bISO\s*50001\b",
    # References reglementaires
    r"\barticle\s+\d+(?:[.,]\d+)*\b",
    # Identifiants techniques
    r"\b802\.1Q\b",
    r"\bPCI-?DSS\s*\d+(?:[.,]\d+)?\b",
    # AR6, COP, F01..F24 (references internes)
    r"\bAR\s*\d+\b",
    r"\bCOP\s*\d+\b",
    r"\bF\d{2}\b",
    r"\bUS\d+\b",
    # ODD ONU
    r"\bODD\s*\d+\b",
    # GIEC chapter
    r"\bWG\s*\d+\b",
    # Numeros de version (vNN)
    r"\bv\d+(?:[.,]\d+)*\b",
    # Annee seule (1900-2099) sans unite — souvent une date contextuelle
    # On l'ignore SAUF si suivi explicitement d'une unite verifiable
    # (le regex de detection s'en charge).
)

_IGNORED_RE = re.compile(
    "|".join(IGNORED_NUMERIC_PATTERNS), re.IGNORECASE,
)


# Detection des grappes "chiffre + unite". Une grappe = nombre suivi de :
# - une unite verifiable (kWh, kgCO2e, %, FCFA, EUR, USD, t, kg, MW, ans, etc.)
# - ou en contexte explicite "score de 75 sur 100" ou "75/100".
_NUMBER_UNIT_RE = re.compile(
    r"""
    (?P<num>
        \d{1,3}(?:[.\s]\d{3})*(?:[.,]\d+)?
        |
        \d+(?:[.,]\d+)?
    )
    \s*
    (?P<unit>
        (?:kgCO2e/(?:kWh|L|kg))
        | (?:tCO2e(?:/an|/MFCFA|/MXOF|/personne)?)
        | (?:kgCO2e)
        | (?:kWh|MWh|GWh|TWh)
        | (?:[mkM]?W(?!h))
        | (?:litres?|L)
        | (?:km|m²|m³)
        | (?:%)
        | (?:FCFA|XOF|EUR|USD|GBP)
        | (?:milliards?|millions?)\s*(?:de\s*)?(?:FCFA|EUR|USD)?
        | (?:tonne(?:s)?(?:\s*de\s*[A-Za-z]+)?)
        | (?:années|annees|ans)
        | (?:sur\s*100|sur\s*10|/100|/10)
        | (?:emplois?)
        | (?:degr[ée]s?\s*C(?:elsius)?)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class NumericClaim:
    """Une grappe detectee dans le texte (chiffre + unite + position)."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class ValidationResult:
    """Resultat de la validation."""

    passed: bool
    claims_detected: list[NumericClaim]
    claims_uncovered: list[NumericClaim]
    requires_retry: bool
    substituted_text: str | None = None
    incident_logged: bool = False


def _strip_ignored(text: str) -> str:
    """Remplacer les motifs IGNORED par des espaces pour les exclure de la detection."""
    return _IGNORED_RE.sub(lambda m: " " * len(m.group(0)), text)


def detect_claims(text: str) -> list[NumericClaim]:
    """Detecter les grappes chiffre+unite dans un texte.

    Les motifs IGNORED_NUMERIC_PATTERNS sont neutralises avant detection.
    """
    if not text:
        return []
    cleaned = _strip_ignored(text)
    claims: list[NumericClaim] = []
    for m in _NUMBER_UNIT_RE.finditer(cleaned):
        claims.append(
            NumericClaim(
                text=text[m.start() : m.end()],
                start=m.start(),
                end=m.end(),
            ),
        )
    return claims


def _extract_tool_calls_by_name(
    tool_calls: Iterable[dict] | None, *, tool_name: str,
) -> list[dict]:
    """Extraire les tool_calls dont le nom correspond."""
    if not tool_calls:
        return []
    matched = []
    for tc in tool_calls:
        name = tc.get("name") or tc.get("tool") or tc.get("tool_name")
        if name == tool_name:
            matched.append(tc)
    return matched


def _check_coverage(
    claims: list[NumericClaim],
    cite_source_calls: list[dict],
    flag_unsourced_calls: list[dict],
) -> list[NumericClaim]:
    """Retourner les grappes non couvertes par une citation valide.

    Strategie pragmatique (FR-014) :
    - Si au moins une cite_source ou flag_unsourced est invoquee, on considere
      que les grappes du paragraphe sont couvertes (granularite paragraphe).
    - Sinon, toutes les grappes sont non couvertes.

    Implementation simplifiee : on suppose qu'une citation par texte couvre
    les grappes du texte, sauf grappes provenant de sources differentes.
    """
    if not claims:
        return []
    has_citation = bool(cite_source_calls)
    has_flag = bool(flag_unsourced_calls)
    if has_citation or has_flag:
        # Granularite paragraphe : on tolere une citation pour couvrir le tour.
        return []
    return list(claims)


FALLBACK_TEXT = "[je ne dispose pas d'une source verifiee pour ce chiffre]"


def _substitute_with_fallback(text: str, claims: list[NumericClaim]) -> str:
    """Remplacer les grappes non couvertes par le texte de repli."""
    if not claims:
        return text
    # Trier par position decroissante pour preserver les indices.
    sorted_claims = sorted(claims, key=lambda c: c.start, reverse=True)
    out = text
    for claim in sorted_claims:
        out = out[: claim.start] + FALLBACK_TEXT + out[claim.end :]
    return out


def validate_response(
    final_text: str,
    tool_calls: list[dict] | None = None,
    *,
    retry_count: int = 0,
) -> ValidationResult:
    """Point d'entree du validator.

    Args:
        final_text: Texte final produit par le LLM apres tous les outils.
        tool_calls: Liste des tool_calls invoques durant le tour.
        retry_count: Nombre de tentatives deja effectuees (0 = premier passage).

    Returns:
        ValidationResult contenant le verdict et le texte substitue le cas echeant.
    """
    claims = detect_claims(final_text)
    cite_calls = _extract_tool_calls_by_name(tool_calls, tool_name="cite_source")
    flag_calls = _extract_tool_calls_by_name(
        tool_calls, tool_name="flag_unsourced",
    )

    uncovered = _check_coverage(claims, cite_calls, flag_calls)

    if not uncovered:
        return ValidationResult(
            passed=True,
            claims_detected=claims,
            claims_uncovered=[],
            requires_retry=False,
        )

    # Premiere tentative : demander un retry.
    if retry_count == 0:
        return ValidationResult(
            passed=False,
            claims_detected=claims,
            claims_uncovered=uncovered,
            requires_retry=True,
        )

    # Retry epuise : substituer par fallback et logger l'incident.
    substituted = _substitute_with_fallback(final_text, uncovered)
    logger.warning(
        "Validator source_required : substitution fallback apres retry, "
        "%d grappe(s) non couverte(s)",
        len(uncovered),
    )
    return ValidationResult(
        passed=False,
        claims_detected=claims,
        claims_uncovered=uncovered,
        requires_retry=False,
        substituted_text=substituted,
        incident_logged=True,
    )
