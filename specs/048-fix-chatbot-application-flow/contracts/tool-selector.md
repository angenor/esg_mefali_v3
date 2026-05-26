# Contract — Sélecteur de tools piloté par l'intention (D1)

**Fichier** : `backend/app/graph/tool_selector.py` — fonction `select_tools_for_node`

## Comportement attendu (après modification)

Entrées inchangées : `node_name`, `current_page`, `all_tools`, `active_entities`.

Construction de l'ensemble de base :

```
base = GLOBAL_WHITELIST
     ∪ MODULE_TOOL_MAPPING.get(node_name, ∅)        # intention (nœud routé)
     ∪ PAGE_TOOL_MAPPING.get(normalize_page(page), ∅) # contexte (page)
base ∩= {t.name for t in all_tools}                  # bornage au catalogue dispo
```

Troncature si `len(base) > MAX_TOOLS_PER_TURN` — **ordre de priorité de conservation** :
1. `GLOBAL_WHITELIST` (toujours) ;
2. tools du **nœud** `node_name` (intention) ;
3. tools de **page** (rognés en premier, tri déterministe).

## Invariants / assertions

- `len(selected) <= MAX_TOOLS_PER_TURN` (assertion existante conservée).
- Déterministe, pur (aucune I/O, aucun appel LLM).
- `debug_info` enrichi : `node_tools_included: bool`, conserve `page_slug`, `fallback_used`, `truncated`.

## Cas de test (TDD — à écrire AVANT)

| # | node_name | current_page | Attendu |
|---|-----------|--------------|---------|
| T1 | `application` | `/documents` | `create_fund_application` ∈ selected (régression du bug) |
| T2 | `financing` | `/dashboard` | `create_fund_application` ∈ selected |
| T3 | `chat` | `/financing` | tools page financing présents (pas de régression) |
| T4 | `application` | `/applications` | union = inchangée fonctionnellement, ≤ 36 |
| T5 | `esg_scoring` | `/documents` | tools ESG du nœud présents malgré slug documents |
| T6 | (n'importe) | n'importe | `len(selected) ≤ 36` et `GLOBAL_WHITELIST ⊆ selected` |
| T7 | troncature forcée | page riche + nœud riche | tools nœud conservés avant tools page |

## Non-régression
- `_validate_config()` (`tool_selector_config.py:464`) doit continuer à passer (budget page ∪ whitelist ≤ 36). Vérifier que l'union la plus large (page financing ∪ nœud application ∪ whitelist) après troncature reste ≤ 36.
