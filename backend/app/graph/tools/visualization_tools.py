"""F11 — Tools LangChain de visualisation typés (KPICard, MatchCard, Map, ComparisonTable).

Ces 4 tools encapsulent les schémas Pydantic stricts définis dans
``app.schemas.visualization`` et sont consommés par les noeuds LangGraph
chat / esg / carbon / credit / action_plan / financing / application / profiling.

Ils ne mutent rien (lecture/présentation uniquement). Persistance limitée au
journal ``tool_call_logs`` (introduit en 012).

Pattern : chaque tool retourne ``args.model_dump_json()`` sérialisé. Le frontend
parse ce JSON depuis l'événement SSE ``visualization_block`` (émis via marker
``<!--SSE:{__sse_visualization_block__:true,...}-->`` détecté par
``stream_graph_events``).

Voir :
- spec.md §FR-001..FR-031
- contracts/visualization-tools.md
- data-model.md
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from app.schemas.visualization import (
    ComparisonTableArgs,
    KPICardArgs,
    MapArgs,
    MatchCardArgs,
)

logger = logging.getLogger(__name__)


def _build_sse_marker(tool_name: str, payload: dict) -> str:
    """Construit le marker SSE de visualisation pour transport vers frontend.

    Format : ``<!--SSE:{...}-->`` détecté par ``stream_graph_events`` pour
    convertir le payload en évènement SSE typé ``visualization_block``.
    """
    marker_data = {
        "__sse_visualization_block__": True,
        "type": "visualization_block",
        "block_type": tool_name,
        "payload": payload,
    }
    return f"<!--SSE:{json.dumps(marker_data, ensure_ascii=False)}-->"


# =====================================================================
# Tool 1 — show_kpi_card
# =====================================================================


@tool(args_schema=KPICardArgs)
async def show_kpi_card(**kwargs) -> str:
    """Affiche une carte KPI typee pour un chiffre cle source (score, total, montant, compteur).

    Use when:
    - tu presentes un chiffre cle synthetique (score ESG, empreinte carbone, score credit, montant leve).
    - une comparaison temporelle ou cible est pertinente (delta vs periode/objectif).
    Don't use when:
    - tu presentes plusieurs valeurs a comparer (utiliser `show_comparison_table`).
    - tu presentes une evolution temporelle (utiliser fence ` ```chart ` line).
    - tu presentes une repartition en categories (utiliser fence ` ```chart ` pie/donut).

    Exemple:
        show_kpi_card(title="Empreinte carbone 2026", value="45 tCO2e",
                      delta=-12, delta_label="vs 2024", delta_direction="down",
                      delta_is_good=True, color="emerald",
                      drilldown_url="/carbon/results")

    Anti: "comment réduire mon empreinte carbone ?" -> NE PAS appeler
        (préférer texte + plan d'action).

    Args (validés via ``KPICardArgs``):
        title: titre court (1-120).
        value: valeur affichée (1-60).
        value_money: Money typé F04 si chiffre monétaire (optionnel).
        delta: delta numérique signé (optionnel).
        delta_label: étiquette du delta (ex: "vs 2024").
        delta_direction: "up" | "down" | "neutral" (optionnel).
        delta_is_good: True si delta favorable (optionnel).
        icon: nom heroicon (optionnel).
        color: emerald | blue | rose | amber | violet (défaut emerald).
        source_id: UUID source F01 (optionnel).
        drilldown_url: URL relative interne (optionnel).
    """
    args = KPICardArgs(**kwargs)
    payload = args.model_dump(mode="json")
    marker = _build_sse_marker("show_kpi_card", payload)
    return f"{args.model_dump_json()}{marker}"


# =====================================================================
# Tool 2 — show_match_card
# =====================================================================


@tool(args_schema=MatchCardArgs)
async def show_match_card(**kwargs) -> str:
    """Afficher une carte de matching projet -> offre cliquable.

    Use when:
    - tu proposes une (ou plusieurs) offres compatibles avec un projet précis.
    - tu mets en avant un intermédiaire spécifique pour un fonds donné.

    Don't use when:
    - tu listes le catalogue complet (utiliser texte + lien vers /financing).
    - tu compares plusieurs offres pour le même fonds (utiliser `show_comparison_table`).

    Exemple:
        show_match_card(project_id="abc-...", offer_id="xyz-...",
                        fund_name="GCF", intermediary_name="BOAD",
                        compatibility_score=78, amount_range="1-5 M FCFA",
                        timeline="12-18 mois", instruments=["subvention","blending"],
                        missing_criteria_count=2,
                        drilldown_url="/financing/offers/xyz?project_id=abc")

    Anti: "explique-moi la différence entre subvention et blending"
        -> NE PAS appeler.

    Args (validés via ``MatchCardArgs``):
        project_id: UUID projet F06 (requis).
        offer_id: UUID offre F07 (requis).
        fund_name: nom du fonds (requis).
        fund_logo_url: URL logo (optionnel).
        intermediary_name: nom intermédiaire (requis).
        intermediary_logo_url: URL logo intermédiaire (optionnel).
        compatibility_score: 0-100 (requis).
        compatibility_breakdown: dict décomposition score (optionnel).
        amount_range: ex "1-5 M FCFA" (requis).
        timeline: ex "12-18 mois" (requis).
        instruments: liste 1-8 instruments (requis).
        missing_criteria_count: 0-99 (requis).
        cta_label: texte du bouton (défaut "Explorer").
        drilldown_url: URL fiche offre dans contexte projet (requis).
    """
    args = MatchCardArgs(**kwargs)
    payload = args.model_dump(mode="json")
    marker = _build_sse_marker("show_match_card", payload)
    return f"{args.model_dump_json()}{marker}"


# =====================================================================
# Tool 3 — show_map
# =====================================================================


@tool(args_schema=MapArgs)
async def show_map(**kwargs) -> str:
    """Affiche une carte geographique des entites liees (projet, intermediaire, fonds, UEMOA).

    Use when:
    - l'utilisateur demande ou se trouve un projet, un intermediaire, un bureau de fonds.
    - tu veux contextualiser geographiquement une recommandation (intermediaire le plus proche).
    Don't use when:
    - aucune coordonnee geographique precise n'est disponible (utiliser `cite_source` + texte).
    - une seule adresse a presenter sans contexte regional (utiliser texte simple).

    Exemple:
        show_map(title="Vos interlocuteurs UEMOA",
                 markers=[
                     {"lat": 7.69, "lon": -5.03, "label": "Bouaké", "type": "project"},
                     {"lat": 6.13, "lon": 1.22, "label": "Lomé BOAD", "type": "intermediary"}
                 ],
                 show_uemoa_overlay=True)

    Anti: "quel est le siège de la BOAD ?" -> NE PAS appeler (préférer texte court).

    Args (validés via ``MapArgs``):
        title: titre carte (optionnel).
        center: tuple (lat, lon) optionnel (défaut centre UEMOA).
        zoom: 1-18 (défaut 6).
        markers: liste 1-50 MapMarker (requis).
        show_uemoa_overlay: bool (défaut False).
    """
    args = MapArgs(**kwargs)
    payload = args.model_dump(mode="json")
    marker = _build_sse_marker("show_map", payload)
    return f"{args.model_dump_json()}{marker}"


# =====================================================================
# Tool 4 — show_comparison_table
# =====================================================================


@tool(args_schema=ComparisonTableArgs)
async def show_comparison_table(**kwargs) -> str:
    """Afficher un tableau comparatif côte-à-côte de 2 à 5 sujets.

    Use when:
    - l'utilisateur demande de comparer plusieurs offres, intermédiaires, scénarios.
    - une décision se prend en pesant plusieurs critères structurés.

    Don't use when:
    - on présente un seul sujet (utiliser `show_kpi_card` ou `show_match_card`).
    - on présente plus de 5 sujets (refuser, message au LLM "limite 5 max").
    - on présente des données non comparables (texte libre).

    Exemple:
        show_comparison_table(title="GCF via 3 intermédiaires",
                              subjects=[{"id":"a","label":"BOAD"}, ...],
                              rows=[{"label":"Frais","type":"money", "values":[...]}, ...])

    Anti: "que penses-tu de GCF ?" -> NE PAS appeler.

    Args (validés via ``ComparisonTableArgs``):
        title: titre tableau (1-200, requis).
        subjects: liste 2-5 ComparisonSubject (requis).
        rows: liste 1-20 ComparisonRow (requis).
        highlight_winner: bool (défaut True).

    Validation cross-field : chaque ComparisonRow.values doit contenir
    exactement une ComparisonValue par sujet (subject_id ⊆ subjects.id).
    """
    args = ComparisonTableArgs(**kwargs)
    payload = args.model_dump(mode="json")
    marker = _build_sse_marker("show_comparison_table", payload)
    return f"{args.model_dump_json()}{marker}"


# =====================================================================
# Liste exportée pour binding LangGraph
# =====================================================================

VISUALIZATION_TOOLS = [
    show_kpi_card,
    show_match_card,
    show_map,
    show_comparison_table,
]


__all__ = [
    "VISUALIZATION_TOOLS",
    "show_comparison_table",
    "show_kpi_card",
    "show_map",
    "show_match_card",
]
