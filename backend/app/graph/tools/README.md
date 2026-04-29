# Tools LangChain — conventions (story 10.1)

Ce repertoire contient les tools LangChain consommes par les noeuds LangGraph.
La fiabilite de l'orchestration LLM repose sur deux invariants : **descriptions
beton** (le LLM choisit le bon tool sans ambiguite) et **schemas Pydantic stricts**
(tout payload invalide est rejete avant la BDD).

## 1. Nommage

- `verbe_objet[_modifier]`, snake_case (ex: `update_company_profile`,
  `batch_save_esg_criteria`, `ask_interactive_question`).
- Lecture seule : prefixe `get_*` ou verbe explicite (`simulate_*`).
- Mutation : verbe d'action (`create_*`, `update_*`, `save_*`, `finalize_*`,
  `export_*`).
- Ne **jamais** renommer un tool existant (les prompts modules et la table
  `tool_call_logs.tool_name` referencent les noms exacts).

## 2. Template de docstring (5 sections obligatoires)

Chaque tool du perimetre story 10.1 (14 tools) suit **strictement** ce gabarit en
francais avec accents :

```python
@tool(args_schema=MonToolArgs)
async def mon_tool(...) -> str:
    """Verbe d'action : phrase courte (< 25 mots) qui leve l'ambiguite.

    Use when:
    - cas concret 1
    - cas concret 2
    Don't use when:
    - cas X (utiliser `tool_alt_1`)
    - cas Y (utiliser `tool_alt_2`)
    Exemple: "message utilisateur" -> appel mon_tool(...).
    Anti: "message utilisateur" -> NE PAS appeler mon_tool.
    """
```

Regles :

- Section 1 : verbe d'action en majuscule debut, < 25 mots.
- Section 2 : `Use when:` puis bullets `- ...` (>= 2 cas).
- Section 3 : `Don't use when:` puis bullets `- ...` (>= 2 cas, **chaque cas
  cite le tool alternatif** entre backticks).
- Section 4 : `Exemple:` (1 ligne) — un message utilisateur typique + le tool
  call attendu.
- Section 5 : `Anti:` (1 ligne) — un message utilisateur qui pourrait pieger
  + l'instruction de NE PAS appeler.

## 3. Template `args_schema` Pydantic v2

```python
from pydantic import BaseModel, ConfigDict, Field
from app.models.company import SectorEnum   # reutiliser les Enum existants


class MonToolArgs(BaseModel):
    """Args strict pour mon_tool."""

    model_config = ConfigDict(extra="forbid")  # OBLIGATOIRE

    application_id: str = Field(..., min_length=1, max_length=64)
    sector: SectorEnum | None = None
    score: int = Field(..., ge=0, le=100)
    justification: str = Field(..., min_length=1, max_length=500)
```

Regles :

- `model_config = ConfigDict(extra="forbid")` est **obligatoire** (rejet des
  champs inconnus). `class Config` (Pydantic v1) interdit.
- Tous les `int` / `float` / `Decimal` ont `Field(ge=, le=)` adaptes au metier.
- Les choix fermes (status, type, category, country, sector) **doivent** etre
  des Enum Python issus de `app/models/`.
- Les strings libres ont des bornes `min_length` / `max_length`.
- Les ids et codes courts contraints utilisent `pattern=...`.
- Le parametre `config: RunnableConfig` du tool LangChain n'est **pas** dans le
  schema : il est injecte par le runtime.

## 4. Enum partages a reutiliser

| Enum | Fichier | Valeurs |
|---|---|---|
| `SectorEnum` | `app.models.company` | agriculture, energie, recyclage, transport, construction, textile, agroalimentaire, services, commerce, artisanat, autre |
| `ESGStatusEnum` | `app.models.esg` | draft, in_progress, completed |
| `TargetType` | `app.models.application` | fund_direct, intermediary_bank, intermediary_agency, intermediary_developer |
| `ApplicationStatus` | `app.models.application` | draft, preparing_documents, in_progress, review, ready_for_intermediary, ready_for_fund, submitted_to_intermediary, submitted_to_fund, under_review, accepted, rejected |
| `InteractiveQuestionType` | `app.models.interactive_question` | qcu, qcm, qcu_justification, qcm_justification |

Si un Enum manque (ex: `CountryEnum`, `ESGCategoryEnum`), **ne pas** le creer
uniquement dans `app/graph/tools/` : l'ajouter dans `app/models/` avec migration
Alembic correspondante (et probablement hors scope story 10.1 — demander avant).

## 5. Anti-patterns

1. Ne pas creer un nouveau tool si une description plus precise + un Enum
   suffit a discriminer un cas existant.
2. Ne pas dupliquer un tool de mutation par variante (`create_X_qcu`, etc.) —
   utiliser un Enum sur le payload.
3. Ne pas inclure `RunnableConfig` dans `args_schema` (injecte par le runtime).
4. Ne pas importer `pydantic.v1` ou `langchain.pydantic_v1` (deprecated v2).
5. Ne pas omettre `extra="forbid"` : sans cela LangChain auto-genere
   `additionalProperties: true` et le LLM peut halluciner des champs.

## 6. Tests

Chaque tool a un fichier `backend/tests/graph/tools/test_<module>_tools_schemas.py` :

- 1 cas positif minimum.
- >= 2 cas negatifs (`pytest.raises(ValidationError)`).
- 1 cas `extra_field=...` rejete par `extra="forbid"`.
- Tests parametres via `@pytest.mark.parametrize`, marques `@pytest.mark.unit`.

Le test meta `test_tools_meta_conformity.py` scanne dynamiquement les 14 tools
du perimetre et valide les invariants AC4 (5 sections, longueur >= 200, schema
strict, choix fermes en Enum).

## 7. Mesure du budget tokens

`backend/scripts/measure_tools_token_budget.py` totalise la longueur des
descriptions des 14 tools et compare a un baseline
(`backend/tools/_tokens_baseline.json`). Gate strict : variation `<= +25%` (AC6).

## 8. Filtrage par contexte (story 10.2)

Le LLM ne voit jamais plus de `MAX_TOOLS_PER_TURN` (= 10) tools par tour.
La selection est realisee par `app/graph/tool_selector.select_tools_for_node`
en fonction de `(current_page, node_name)`. Le `ToolNode` cote graphe garde
la liste complete : on filtre uniquement ce qui est expose au LLM via
`bind_tools(...)`.

### Comment ajouter une nouvelle page

1. Ajouter le slug dans `PAGE_TOOL_MAPPING` (`app/graph/tool_selector_config.py`)
   avec la liste exacte des `tool.name` autorises.
2. Ajouter le mapping path Nuxt -> slug dans `_PATH_TO_SLUG_PATTERNS` de la
   meme configuration (premier pattern matchant gagne). Cette table est
   consommee par `normalize_page(current_page)` ; pour valider, exporter
   `normalize_page` depuis un REPL et tester le path attendu.
3. Verifier que `len(PAGE_TOOL_MAPPING[slug] | GLOBAL_WHITELIST) <= 10` —
   sinon le test `test_invariant_max_tools_per_turn_for_all_pages` echoue.
4. Ajouter le test exact-match dans `tests/graph/test_tool_selector.py`
   (parametre `page_slug` du test `test_select_tools_by_page_exact_match`).

### Audit en production

```
python backend/scripts/audit_tools_offered.py --conversations 50
```

Lit les 50 dernieres conversations de `tool_call_logs.tools_offered`, agrege
par noeud LangGraph et ecrit un rapport markdown dans
`backend/tools/_tools_offered_report.md`. Code de sortie 1 si une conversation
depasse `MAX_TOOLS_PER_TURN`.
