# Contract — Tools LangChain `sourcing_tools.py`

**Feature** : F01
**Fichier** : `backend/app/graph/tools/sourcing_tools.py`
**Injection** : tous les nœuds qui produisent des chiffres (chat, esg_scoring, carbon, financing, application, credit, action_plan).
**Mutation interdite** : aucun de ces tools ne mute le catalogue (invariant ESG Mefali #7). `flag_unsourced` insère uniquement dans la table `unsourced_flags` (journal append-only).

## Tool 1 — `cite_source`

### Signature

```python
@tool
async def cite_source(source_id: str) -> dict:
    """Référence une source vérifiée pour étayer une affirmation factuelle.

    Args:
        source_id: UUID de la source au catalogue. La source DOIT être
            en verification_status='verified'. Sinon, le tool retourne
            une erreur structurée que l'agent doit traiter en invoquant
            `search_source` ou `flag_unsourced`.

    Returns:
        SourceCitation sous forme de dict contenant :
        - id, url, title, publisher, version, date_publi, page

    Raises:
        ValueError si source_id n'est pas un UUID valide.
    """
```

### Comportement

1. Parse `source_id` en UUID (sinon → `{"error": "invalid_uuid", "source_id": <input>}`).
2. Lookup `sources` table.
3. Si source inexistante → `{"error": "source_not_found", "source_id": <id>}`.
4. Si `verification_status != 'verified'` → `{"error": "source_not_verified", "source_id": <id>, "actual_status": <status>}`.
5. Sinon : retourne `SourceCitation` :
   ```json
   {
     "id": "uuid",
     "url": "https://...",
     "title": "...",
     "publisher": "ADEME",
     "version": "v23",
     "date_publi": "2024-06-15",
     "page": 42
   }
   ```

### Side effects

- Insère un `tool_call_log` (existant feature 012) avec `tool_name='cite_source'`, `arguments={"source_id": ...}`, `result=<dict ci-dessus>`.
- Émet potentiellement un event SSE `source_cited` consommé par le frontend pour afficher un picto inline (pattern à valider en feature ultérieure ; pour F01 le frontend reconstruit l'historique via le marker existant).

### Tests unitaires (`test_sourcing_tools.py::TestCiteSource`)

1. `test_cite_source_with_verified_source_returns_citation` — happy path.
2. `test_cite_source_with_pending_source_returns_error` — `error: source_not_verified`.
3. `test_cite_source_with_outdated_source_returns_error` — `error: source_not_verified`.
4. `test_cite_source_with_unknown_uuid_returns_404_error` — `error: source_not_found`.
5. `test_cite_source_with_invalid_uuid_returns_value_error` — `error: invalid_uuid`.
6. `test_cite_source_logs_to_tool_call_logs` — vérifier `tool_call_logs` contient l'entrée.

## Tool 2 — `search_source`

### Signature

```python
@tool
async def search_source(
    query: str,
    publisher: str | None = None,
    limit: int = 5,
) -> dict:
    """Recherche dans le catalogue de sources vérifiées par mots-clés et embeddings.

    Args:
        query: requête en texte libre (≥ 3 caractères). Combinée à un embedding
            pour recherche hybride full-text + cosine similarity.
        publisher: filtre optionnel par publisher exact (ex: "ADEME", "UEMOA").
        limit: nombre maximum de résultats (1..5, défaut 5, hard cap 5).

    Returns:
        {
            "results": [SourceListItem, ...],  # max `limit` items
            "query": <query>,
            "publisher_filter": <publisher | null>,
        }
    """
```

### Comportement

1. Validation : `query` ≥ 3 caractères, `limit` ∈ [1, 5].
2. Calcul de l'embedding de `query` via `text-embedding-3-small` (ou cache si déjà calculé pour cette requête).
3. Requête SQL hybride :
   ```sql
   SELECT id, title, publisher, version, date_publi, verification_status,
          ts_rank_cd(to_tsvector('french', title || ' ' || publisher || ' ' || COALESCE(section,'')),
                     plainto_tsquery('french', :query)) AS fts_rank,
          1 - (embedding <=> :query_embedding) AS cosine_sim
   FROM sources
   WHERE verification_status = 'verified'
     AND (:publisher IS NULL OR publisher = :publisher)
     AND (
        to_tsvector('french', title || ' ' || publisher || ' ' || COALESCE(section,''))
            @@ plainto_tsquery('french', :query)
        OR embedding <=> :query_embedding < 0.4
     )
   ORDER BY (0.5 * fts_rank + 0.5 * cosine_sim) DESC
   LIMIT :limit;
   ```
4. Si moins de `limit` résultats → retour partiel.

### Side effects

- Insère un `tool_call_log` avec `tool_name='search_source'`, `arguments={"query": ..., "publisher": ..., "limit": ...}`, `result={"count": N}`.

### Tests unitaires (`test_sourcing_tools.py::TestSearchSource`)

1. `test_search_source_full_text_match` — requête « émission électricité » retourne sources ADEME/IEA.
2. `test_search_source_publisher_filter` — `publisher='UEMOA'` ne retourne que UEMOA.
3. `test_search_source_excludes_non_verified` — sources `pending` ou `outdated` exclues.
4. `test_search_source_limit_max_5` — `limit=10` est borné à 5.
5. `test_search_source_query_too_short_returns_empty` — `query='ab'` retourne `results=[]`.
6. `test_search_source_no_match_returns_empty` — requête imaginaire retourne `results=[]`.

## Tool 3 — `flag_unsourced`

### Signature

```python
@tool
async def flag_unsourced(claim: str, reason: str) -> dict:
    """Marque une affirmation comme non sourçable, avec un motif explicite.

    Args:
        claim: texte de l'affirmation que l'agent ne peut pas sourcer
            (ex: "estimations internes ESG Mefali").
        reason: motif explicite (ex: "aucune source officielle disponible
            dans le catalogue pour ce chiffre").

    Returns:
        {
            "flagged": true,
            "flag_id": "uuid",
            "claim_excerpt": "...",  # premiers 100 caractères
        }
    """
```

### Comportement

1. Validation : `claim` 10..2000 chars ; `reason` 10..500 chars.
2. Insertion dans `unsourced_flags` avec `claim`, `reason`, `conversation_id` (depuis le contexte LangGraph), `message_id` (NULL si pas encore persisté).
3. Émet un event SSE `unsourced_flag` (consommé par frontend pour afficher un libellé visible « Ce chiffre n'est pas sourcé : <reason> »).
4. Retourne un message à l'agent confirmant le flag.

### Side effects

- 1 INSERT dans `unsourced_flags`.
- 1 INSERT dans `tool_call_logs`.
- 1 event SSE émis vers le frontend.

### Tests unitaires (`test_sourcing_tools.py::TestFlagUnsourced`)

1. `test_flag_unsourced_inserts_record` — vérifier `unsourced_flags` contient la ligne.
2. `test_flag_unsourced_returns_flag_id` — UUID valide.
3. `test_flag_unsourced_validates_min_length` — `claim` < 10 chars → ValueError.
4. `test_flag_unsourced_links_conversation_id` — `conversation_id` correctement extrait du contexte LangGraph.

## Injection dans les nœuds LangGraph

Tous les nœuds suivants reçoivent les 3 tools dans leur `tools=[...]` lors de la création :

- `chat_node` (`backend/app/graph/nodes.py::chat_node`)
- `esg_scoring_node`
- `carbon_node`
- `financing_node`
- `application_node`
- `credit_node`
- `action_plan_node`

> **Important** : la modification de `nodes.py` est autorisée puisque ce n'est PAS dans la liste des zones interdites. La zone `graph.py` (assemblage du graphe) reste intouchée.

## Tests d'intégration LangGraph (`test_sourcing_tools_in_graph.py`)

1. `test_chat_node_invokes_cite_source_when_question_about_emission_factor` — happy path conversationnel.
2. `test_carbon_node_uses_search_source_to_find_iea` — l'agent recherche puis cite.
3. `test_credit_node_flags_unsourced_for_inventede_simulation_factor` — l'agent flag_unsourced sur les constantes du simulateur (status pending).
4. `test_all_tools_available_in_action_plan_node` — vérifier que les 3 tools sont injectés.

## Eval LLM (golden set 10 cas)

Fichier `backend/tests/llm_eval/test_cite_source_golden_set.py` — exécuté **uniquement** quand `RUN_LLM_EVAL=true` (mock par défaut, vrai LLM en mode dédié).

10 questions imposant l'utilisation d'au moins un chiffre :

1. « Quel est le facteur d'émission de l'électricité réseau en Côte d'Ivoire ? »
2. « Quel est le seuil PME selon la réglementation UEMOA ? »
3. « Combien de critères ESG la Taxonomie verte UEMOA impose-t-elle ? »
4. « Quel est le rendement attendu d'un projet solaire au Sénégal selon le GCF ? »
5. « Quels sont les seuils de financement minimum du Fonds Vert pour le Climat ? »
6. « Quel est le facteur d'émission du diesel selon l'ADEME ? »
7. « Combien d'employés une micro-entreprise UEMOA peut-elle avoir ? »
8. « Quel est l'impact carbone moyen d'un million de FCFA investi en agriculture ? »
9. « Quels sont les critères ODD prioritaires pour le scoring ESG ? »
10. « Quels documents la BOAD exige-t-elle pour un dossier vert ? »

Pour chaque cas : assertion qu'au moins une `cite_source` invocation a été journalisée dans `tool_call_logs` avant la fin du tour (ou à défaut, une `flag_unsourced` valide).

Critère de succès : ≥ 9 / 10 cas conformes (SC-003).
