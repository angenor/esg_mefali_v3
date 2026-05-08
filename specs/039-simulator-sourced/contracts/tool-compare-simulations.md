# Contract — LangChain tool `compare_simulations`

**Module** : `app.graph.tools.simulation_tools`
**Type** : LangChain tool synchronisé avec le pattern `args_schema` Pydantic v2 strict.
**Visibilité** :
- `MODULE_TOOL_MAPPING['financing']`
- `MODULE_TOOL_MAPPING['application']`
- `PAGE_TOOL_MAPPING['financing']`
- `PAGE_TOOL_MAPPING['simulator']` (à ajouter — pattern `^/financing/simulator(?:/|$)`)

## Args schema (Pydantic v2)

```python
class CompareSimulationsArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    project_id: UUID = Field(..., description="Identifiant du projet de la PME (F06).")
    offer_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="1 à 5 offres Fonds×Intermédiaire (F07) à comparer côte-à-côte.",
    )
```

## Comportement

1. Le tool reçoit `(project_id, offer_ids)` et l'`account_id` via le `RunnableConfig` (`configurable.account_id`, déjà câblé par F23/F12).
2. Il appelle `multi_simulate_service.simulate_multi(db, project_id, offer_ids, account_id)`.
3. Il construit un **payload `ComparisonTableArgs` (F11)** avec :
   - `subjects` : 1 par offre (label = `<fund.name> via <intermediary.name>`, sous-label = devise du fonds).
   - `rows` :
     - « Coût total » → `total_cost` (Money) avec `source_id` agrégé (ou `null` si dégradé).
     - « Timeline (semaines)` → `weeks_max` somme des étapes, `source_id` = la pire des étapes.
     - « ROI » → `notes_fr` + `ratio` si applicable.
     - « Impact carbone (tCO2e/an) » → `tco2e_per_year` ou « non estimé ».
     - « Score compatibilité » → masquée si F14 indisponible (R6).
   - `winner_indices` : `{rows[0]: cheapest_offer_index, rows[1]: fastest_offer_index}` quand applicable.
4. Il émet le marker SSE F11 dans le contenu de l'outil :
   ```
   <!--SSE:{"__sse_visualization_block__":true,"block_type":"comparison_table","payload":{...}}-->
   ```
5. Il retourne au LLM un JSON résumé court :
   ```json
   {
     "ok": true,
     "compared": 3,
     "cheapest_offer_id": "<uuid>",
     "fastest_offer_id": "<uuid>",
     "degraded_offers": [],
     "rendered_block": "comparison_table"
   }
   ```

## Règles métier

- **R-001** : Le tool refuse si `offer_ids` après dedup > 5 → retourne `{"ok": false, "error": "max_5_offres"}` sans appel BDD.
- **R-002** : Le tool refuse si l'utilisateur n'a pas accès au projet ou à au moins une offre → retourne `{"ok": false, "error": "access_denied"}` (RLS implicite). Aucune information révélatrice.
- **R-003** : Si un projet n'est pas spécifié et que le contexte LangGraph n'a pas de `current_project_id` connu, le tool retourne `{"ok": false, "error": "project_required"}` et le LLM est instruit (par le prompt) de poser une question interactive (F18 widget).
- **R-004** : Le tool n'est pas mutateur — il ne crée ni ne modifie aucune donnée persistée (cohérent F12 `recall_history` pattern).

## Erreurs (renvoyées au LLM)

| `error` | Cause |
|---------|-------|
| `max_5_offres` | `len(offer_ids) > 5` après dedup. |
| `access_denied` | RLS bloque le projet ou une offre. |
| `project_required` | `project_id` non fourni et non inférable du contexte. |
| `internal_error` | Exception inattendue (loggée, message générique). |

## Tests à fournir

| Type | Fichier | Cas couverts |
|------|---------|--------------|
| Unit | `tests/unit/test_compare_simulations_tool.py` | args_schema valide / invalide ; dedup ; ok=false sur > 5 ; ok=false sur access_denied (mock RLS). |
| Integration | `tests/integration/test_compare_simulations_tool.py` | Marker SSE émis correctement ; payload conforme ComparisonTableArgs F11 ; winner_indices corrects. |
| Conformity | `tests/graph/tools/test_no_skill_mutation_tool.py` (existant) | Vérifie que `compare_simulations` n'est pas un nom interdit (pattern skills). |
