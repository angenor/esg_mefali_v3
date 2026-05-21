"""F045 — Gabarits FR de divergence_explanation entre project_score et company_score.

4 gabarits paramétrés (convergent / projet_fort / entreprise_forte / moyen)
qui produisent un paragraphe FR explicatif sans recourir à un freetext LLM.

Reference : specs/045-matching-projet-centric/research.md R6 et
contracts/api-endpoints.md §1.3.
"""

from __future__ import annotations

from typing import Any, Literal


DivergenceCategory = Literal[
    "convergent",
    "projet_fort",
    "entreprise_forte",
    "moyen",
]


# Seuils (research.md R6)
CONVERGENT_ABS_GAP_MAX: int = 15
STRONG_DELTA_THRESHOLD: int = 30


# --- Sub-score labels FR (mirror frontend types) ---

_SUB_SCORE_LABELS_FR: dict[str, str] = {
    "sector": "secteur projet",
    "taxonomy": "taxonomie verte UEMOA",
    "gcf_themes": "thèmes GCF prioritaires",
    "co2_impact": "impact CO2 chiffré",
    "beneficiaries": "nombre de bénéficiaires",
    "gender": "volet genre",
    "vulnerable": "populations vulnérables ciblées",
    "project_esg": "score ESG projet",
}


_COMPANY_LABELS_FR: dict[str, str] = {
    "sector_match": "secteur d'activité",
    "esg_match": "score ESG entreprise",
    "size_match": "taille du projet vs fourchette du fonds",
    "location_match": "pays d'implantation",
    "documents_match": "complétude documentaire",
    "instrument_match": "instrument financier compatible",
}


def categorize_divergence(
    project_score: int, company_score: int,
) -> DivergenceCategory:
    """Categorise la divergence projet/entreprise en 4 cas (R6).

    - convergent : ecart absolu <= 15
    - projet_fort : project - company > 30
    - entreprise_forte : company - project > 30
    - moyen : autres cas (ecart entre 15 et 30)
    """
    diff = project_score - company_score
    if abs(diff) <= CONVERGENT_ABS_GAP_MAX:
        return "convergent"
    if diff > STRONG_DELTA_THRESHOLD:
        return "projet_fort"
    if -diff > STRONG_DELTA_THRESHOLD:
        return "entreprise_forte"
    return "moyen"


def _top_project_themes_gcf(project_breakdown: dict[str, Any] | None) -> list[str]:
    """Identifie les top sub-scores projet >= 80 (alignement fort)."""
    if not project_breakdown:
        return []
    subs = project_breakdown.get("sub_scores") or {}
    if not isinstance(subs, dict):
        return []
    strong = [
        _SUB_SCORE_LABELS_FR.get(k, k)
        for k, v in subs.items()
        if isinstance(v, (int, float)) and v >= 80
    ]
    return strong[:3]


def _top_project_missing(project_breakdown: dict[str, Any] | None) -> list[str]:
    """Identifie les top critères projet manquants (depuis missing_criteria)."""
    if not project_breakdown:
        return []
    missing = project_breakdown.get("missing_criteria") or []
    out: list[str] = []
    for m in missing[:3]:
        if isinstance(m, dict):
            label = m.get("label_fr") or m.get("key") or ""
            if label:
                # Trim trailing periode pour insertion fluide dans phrase
                out.append(label.rstrip(". "))
    return out


def _top_company_blockers(company_breakdown: dict[str, Any] | None) -> list[str]:
    """Identifie les top sub-scores entreprise <= 40 (faibles)."""
    if not company_breakdown:
        return []
    weak: list[tuple[str, float]] = []
    for key, label in _COMPANY_LABELS_FR.items():
        value = company_breakdown.get(key)
        if isinstance(value, (int, float)) and value <= 40:
            weak.append((label, float(value)))
    weak.sort(key=lambda kv: kv[1])
    return [label for label, _ in weak[:3]]


def _top_company_strengths(company_breakdown: dict[str, Any] | None) -> list[str]:
    """Identifie les top sub-scores entreprise >= 80 (forts)."""
    if not company_breakdown:
        return []
    strong: list[tuple[str, float]] = []
    for key, label in _COMPANY_LABELS_FR.items():
        value = company_breakdown.get(key)
        if isinstance(value, (int, float)) and value >= 80:
            strong.append((label, float(value)))
    strong.sort(key=lambda kv: -kv[1])
    return [label for label, _ in strong[:3]]


def _format_items_fr(items: list[str]) -> str:
    """Joint des elements FR avec virgules et 'et' final."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " et " + items[-1]


# --- Gabarits FR (R6) ---


def _template_convergent() -> str:
    return (
        "Votre projet et votre entreprise sont alignés sur les critères de ce "
        "fonds. Aucune divergence majeure détectée."
    )


def _template_projet_fort(
    project_breakdown: dict[str, Any] | None,
    company_breakdown: dict[str, Any] | None,
) -> str:
    themes = _top_project_themes_gcf(project_breakdown)
    blockers = _top_company_blockers(company_breakdown)
    n_themes = len(themes)
    m_blockers = len(blockers)
    themes_str = _format_items_fr(themes) if themes else "plusieurs piliers d'impact"
    blockers_str = (
        _format_items_fr(blockers) if blockers else "plusieurs critères financiers"
    )
    return (
        f"Votre projet est éligible parce qu'il aligne {n_themes or 'plusieurs'} "
        f"critères impact ({themes_str}). Votre entreprise reste à renforcer sur "
        f"{m_blockers or 'plusieurs'} critères financiers et ESG ({blockers_str})."
    )


def _template_entreprise_forte(
    project_breakdown: dict[str, Any] | None,
    company_breakdown: dict[str, Any] | None,
) -> str:
    strengths = _top_company_strengths(company_breakdown)
    missing = _top_project_missing(project_breakdown)
    strengths_str = (
        _format_items_fr(strengths) if strengths else "plusieurs piliers consolidés"
    )
    missing_str = (
        _format_items_fr(missing) if missing else "plusieurs attributs verts"
    )
    return (
        f"Votre entreprise présente un profil solide ({strengths_str}) mais votre "
        f"projet manque {len(missing) or 'plusieurs'} attributs verts ({missing_str}). "
        "Renforcez ces points pour optimiser votre éligibilité."
    )


def _template_moyen() -> str:
    return (
        "Votre projet et votre entreprise présentent un profil contrasté. "
        "Consultez le détail des critères pour identifier les axes d'amélioration."
    )


def build_divergence_explanation(
    project_score: int,
    company_score: int,
    project_breakdown: dict[str, Any] | None = None,
    company_breakdown: dict[str, Any] | None = None,
) -> str:
    """Genere le paragraphe FR de divergence pour persister dans offer_matches.

    Args:
        project_score: score projet 0..100
        company_score: score entreprise 0..100
        project_breakdown: dict ProjectScoreBreakdown (sub_scores, missing_criteria...)
        company_breakdown: dict des sub_scores entreprise (sector_match...)

    Returns:
        Paragraphe FR (toujours non vide).
    """
    category = categorize_divergence(project_score, company_score)
    if category == "convergent":
        return _template_convergent()
    if category == "projet_fort":
        return _template_projet_fort(project_breakdown, company_breakdown)
    if category == "entreprise_forte":
        return _template_entreprise_forte(project_breakdown, company_breakdown)
    return _template_moyen()


def build_divergence_short(
    project_score: int, company_score: int,
) -> str:
    """Variante courte (<=80 caracteres) pour payload LLM. Reference R6/§2.1."""
    category = categorize_divergence(project_score, company_score)
    if category == "convergent":
        return "Projet et entreprise alignés"
    if category == "projet_fort":
        return "Projet vert éligible, entreprise à renforcer"
    if category == "entreprise_forte":
        return "Entreprise solide, projet à renforcer côté impact"
    return "Profils contrastés — voir détails"


__all__ = [
    "DivergenceCategory",
    "build_divergence_explanation",
    "build_divergence_short",
    "categorize_divergence",
]
