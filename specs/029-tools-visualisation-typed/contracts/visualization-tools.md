# Contrats — Tools de Visualisation Typés (F11)

**Date**: 2026-05-07
**Localisation backend** : `backend/app/graph/tools/visualization_tools.py`
**Schémas Pydantic** : `backend/app/schemas/visualization.py`

Ces contrats décrivent l'interface entre le LLM (qui invoque les tools), le backend (qui valide les payloads), et le frontend (qui rend les composants).

## Format général

Chaque tool LangChain :
- décoré par `@tool(args_schema=XxxArgs)`
- async (pour cohérence avec le graphe LangGraph)
- retourne une **string JSON** sérialisée à partir de `args.model_dump(mode="json")` (le frontend reçoit cette string via SSE `tool_call_end.output`)
- docstring 5 sections obligatoires (use when / don't use when / exemple / anti) — voir `backend/app/graph/tools/README.md`
- ne mute aucune entité (lecture/présentation uniquement)
- respecte le multi-tenant (F02) : si `project_id` ou `offer_id` est fourni, valider l'appartenance à l'`account_id` courant via `get_db_and_user(config)` puis lookup ; rejeter sinon avec message d'erreur clair pour le LLM

## Tool 1 — `show_kpi_card`

**Signature**:
```python
@tool(args_schema=KPICardArgs)
async def show_kpi_card(
    title: str,
    value: str,
    value_money: Money | None = None,
    delta: float | None = None,
    delta_label: str | None = None,
    delta_direction: DeltaDirection | None = None,
    delta_is_good: bool | None = None,
    icon: str | None = None,
    color: KPIColor = "emerald",
    source_id: str | None = None,
    drilldown_url: str | None = None,
    config: RunnableConfig = None,
) -> str:
    """Afficher une carte KPI typée pour un chiffre clé sourcé.

    Use when:
    - tu présentes un chiffre clé synthétique (score ESG, empreinte carbone totale,
      score crédit, montant total levé, nombre de critères validés)
    - une comparaison temporelle ou cible est pertinente (delta vs période/objectif)
    Don't use when:
    - tu présentes plusieurs valeurs à comparer (utiliser `show_comparison_table`)
    - tu présentes une évolution temporelle (utiliser le richblock chart line)
    - tu présentes une répartition en catégories (utiliser le richblock chart pie/donut)
    Exemple: "résume mon empreinte carbone 2026" -> show_kpi_card(title="Empreinte carbone 2026", value="45 tCO2e", delta=-12, delta_label="vs 2024", delta_direction="down", delta_is_good=True, color="emerald", source_id="...", drilldown_url="/carbon/results").
    Anti: "comment réduire mon empreinte carbone ?" -> NE PAS appeler (préférer texte + plan d'action).
    """
```

**Validation**: voir `KPICardArgs` (data-model.md §3).

**Sortie SSE**: `{"tool_name": "show_kpi_card", "output": "<json string>"}` où `<json string>` est `KPICardArgs.model_dump_json()`.

**Erreurs métier**:
- `source_id` fourni mais non trouvé → log warning, retour normal (le frontend masquera le picto au lieu de cracher).
- payload Pydantic invalide → géré par le validator F11 (retry max 1, fallback texte).

## Tool 2 — `show_match_card`

**Signature**:
```python
@tool(args_schema=MatchCardArgs)
async def show_match_card(
    project_id: str,  # UUID en string
    offer_id: str,    # UUID en string
    fund_name: str,
    fund_logo_url: str | None,
    intermediary_name: str,
    intermediary_logo_url: str | None,
    compatibility_score: int,
    compatibility_breakdown: dict[str, int] | None,
    amount_range: str,
    timeline: str,
    instruments: list[str],
    missing_criteria_count: int,
    cta_label: str = "Explorer",
    drilldown_url: str = ...,
    config: RunnableConfig = None,
) -> str:
    """Afficher une carte de matching projet -> offre cliquable.

    Use when:
    - tu proposes une (ou plusieurs) offres compatibles avec un projet précis
    - tu mets en avant un intermédiaire spécifique pour un fonds donné
    Don't use when:
    - tu listes le catalogue complet (utiliser texte + lien vers /financing)
    - tu compares plusieurs offres pour le même fonds (utiliser `show_comparison_table`)
    Exemple: "quelles offres me correspondent ?" -> 3x show_match_card(...) consécutifs.
    Anti: "explique-moi la différence entre subvention et blending" -> NE PAS appeler.
    """
```

**Multi-tenant**:
- À l'invocation, charger `Project` par `project_id` ; si `account_id` ne match pas le contexte, retourner `"Erreur: projet introuvable ou non accessible."`.
- Idem pour `Offer` par `offer_id`.

**Sortie SSE**: idem pattern.

## Tool 3 — `show_map`

**Signature**:
```python
@tool(args_schema=MapArgs)
async def show_map(
    title: str | None = None,
    center: tuple[float, float] | None = None,
    zoom: int = 6,
    markers: list[MapMarker] = ...,
    show_uemoa_overlay: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Afficher une carte géographique des entités liées au projet.

    Use when:
    - l'utilisateur demande où se trouve un projet, un intermédiaire, un bureau de fonds
    - tu veux contextualiser géographiquement une recommandation (ex: intermédiaire le plus proche)
    Don't use when:
    - aucune coordonnée géographique précise n'est disponible (utiliser texte avec ville/pays)
    - une seule adresse à présenter sans contexte régional (utiliser texte simple)
    Exemple: "où sont mes interlocuteurs ?" -> show_map(markers=[...projet, ...intermédiaire], show_uemoa_overlay=True).
    Anti: "quel est le siège de la BOAD ?" -> NE PAS appeler (préférer texte court).
    """
```

**Validation MapMarker** :
- `lat`, `lon` bornés strictement.
- `popup_content` HTML court ; sanitisation côté frontend obligatoire.
- En l'absence de coordonnées précises pour un intermédiaire, utiliser `UEMOA_COUNTRY_CENTROIDS[country_iso3]` côté caller (helper `app/services/visualization.py` à créer si besoin), avec disclaimer "approximatif" dans `popup_content`.

## Tool 4 — `show_comparison_table`

**Signature**:
```python
@tool(args_schema=ComparisonTableArgs)
async def show_comparison_table(
    title: str,
    subjects: list[ComparisonSubject],
    rows: list[ComparisonRow],
    highlight_winner: bool = True,
    config: RunnableConfig = None,
) -> str:
    """Afficher un tableau comparatif côte-à-côte de 2 à 5 sujets.

    Use when:
    - l'utilisateur demande de comparer plusieurs offres, intermédiaires, scénarios
    - une décision se prend en pesant plusieurs critères structurés
    Don't use when:
    - on présente un seul sujet (utiliser `show_kpi_card` ou `show_match_card`)
    - on présente plus de 5 sujets (refuser, message au LLM "limite 5 max")
    - on présente des données non comparables (texte libre)
    Exemple: "compare GCF via BOAD vs GCF via UNDP" -> show_comparison_table(subjects=[...x3], rows=[frais, délai, taux_succès, ...]).
    Anti: "que penses-tu de GCF ?" -> NE PAS appeler.
    """
```

**Validation cross-field** : chaque `ComparisonRow.values` doit contenir exactement une `ComparisonValue` par sujet (validateur Pydantic, voir data-model.md §6).

**Sortie SSE**: idem pattern.

## Conventions communes

### Sérialisation Money

`Money(amount=Decimal('655957.00'), currency='XOF')` est sérialisé en :
```json
{ "amount": "655957.00", "currency": "XOF" }
```

Le frontend formatte ensuite via `useCurrency` composable (existant F04).

### Sérialisation UUID

Tous les UUID Pydantic sont sérialisés en string (par défaut Pydantic v2 mode JSON).

### Code couleur des markers SVG (frontend)

| `MapMarker.type` | Couleur | Icône SVG par défaut |
|------------------|---------|----------------------|
| `project` | Emerald 500 | leaf |
| `intermediary` | Blue 500 | building-office |
| `fund_office` | Violet 500 | banknotes |
| `company_hq` | Amber 500 | building-storefront |

### Visibility par page (`tool_selector_config.py`)

| Tool | Pages où visible | Modules (fallback) |
|------|------------------|--------------------|
| `show_kpi_card` | dashboard, esg, carbon, credit | chat, esg_scoring, carbon, credit, action_plan, dashboard |
| `show_match_card` | financing, candidatures | chat, financing, application |
| `show_map` | profile, profile_projects, financing | chat, profiling, financing |
| `show_comparison_table` | financing, candidatures | chat, financing, application |

> Important : ces 4 tools sont également ajoutés à la `GLOBAL_WHITELIST` ? **Non** — visibilité ciblée pour respecter `MAX_TOOLS_PER_TURN=14` (sinon dépassement risqué). Le LLM voit ces tools uniquement sur les pages pertinentes.

### Quota tools par tour

- `MAX_TOOLS_PER_TURN` reste 14 (existant).
- Sur la page `dashboard`, les 4 nouveaux tools (KPI/Match/Map/Comparison ne sont visibles que partiellement : KPI oui, autres non) — vérifier que le total reste sous 14.
- Sur la page `financing`, ajout de Match/Comparison/Map (3 tools) — vérifier total.

### Politique d'erreurs LLM

Si un payload invalide arrive :
1. Validator `app/graph/validators/payload_invalid.py` (à créer ou étendre `source_required.py`) intercepte l'exception.
2. Renvoie au LLM un message structuré : `"L'argument {champ} est invalide : {détail}. Réponds en texte simple ou retente avec un payload conforme au schéma {SchemaName}."`
3. Limite à 1 retry par message LLM.
4. Si la 2e tentative échoue → fallback texte natif.

## Référence — accès aux données métier

Les tools appellent (helpers existants) :
- `get_db_and_user(config)` — extrait db session et user courant depuis `RunnableConfig`.
- `account_id` est implicite via le service / le user courant.
- F06 : `Project.id`, `Project.country_iso3`, `Project.lat`, `Project.lon`.
- F07 : `Offer.id`, `Offer.fund_id`, `Offer.intermediary_id`, `Offer.compatibility_score`.
- F01 : `Source.id`, `Source.verification_status`.
- F04 : `app.core.money.Money`.

## Tests de contrat

Couverts dans `backend/tests/unit/test_visualization_tools_*.py` :
1. Args valides → tool retourne JSON string contenant tous les champs.
2. Args invalides (extra field, enum hors liste, borne dépassée) → `ValidationError` levée.
3. Multi-tenant : `project_id` d'un autre `account_id` → erreur métier.
4. Sérialisation Money → format `{"amount": "...", "currency": "..."}`.
5. Sérialisation UUID → string.
6. ComparisonTable cross-field validator → erreur si values_ids ≠ subject_ids.
