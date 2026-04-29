---
story_id: M10-S2
epic: M10-EPIC-1
title: Filtrage des tools par contexte de page (LangGraph selecteur)
status: ready
priority: P2
effort: "1-2 j"
source_items: [10.1, 10.4, 10.8.2]
created: 2026-04-29
depends_on: [M10-S1]
---

# Story M10-S2 — Filtrage des tools par contexte de page

## Contexte

Exposer 30+ tools au LLM a chaque tour degrade fortement la precision de selection. Avec 5 a 10
tools bien choisis, la fiabilite est presque infaillible. Le frontend connait deja la page courante
(Module 1.1) et peut transmettre ce contexte au backend.

## Objectif

Implementer un **selecteur de tools** dans LangGraph qui, a chaque tour, charge uniquement les
tools pertinents selon `(intention_detectee, page_courante, entites_actives)`.

## Architecture

```
ConversationState += { page_context: str, active_entities: dict }
        |
        v
[router_node] --> classifie l'intention (LLM leger ou regles deterministes)
        |
        v
[tool_selector_node] --> retourne max 10 tools selon mapping (page, intention) -> tools[]
        |
        v
[specialist_node avec llm.bind_tools(filtered_tools)]
```

## Criteres d'acceptation

- [ ] `ConversationState` etendu avec `page_context: str | None` et `active_entities: dict | None`.
- [ ] Endpoint `POST /api/chat/messages` accepte `page_context` (slug : `profile`, `candidatures`,
  `chat_global`, `esg`, `carbon`, `financing`, `dashboard`, `action_plan`).
- [ ] Mapping declarative `backend/app/graph/tool_selector_config.py` :
  ```python
  PAGE_TOOL_MAPPING: dict[str, list[str]] = {
      "profile": ["update_company_profile", "ask_qcu", "ask_qcm", "show_kpi_card", ...],
      "candidatures": ["update_candidature_status", "show_table", ...],
      "chat_global": [<sous-ensemble par defaut>] + [<tools transverses>],
      ...
  }
  ```
- [ ] Aucun tour de conversation ne charge plus de **10 tools** vers le LLM (assertion runtime
  + log warning si depassement).
- [ ] Whitelist transverse (tools toujours disponibles) : `ask_qcu`, `ask_qcm`, `show_kpi_card`,
  `show_mermaid` — fallback minimal si page inconnue.
- [ ] Tests d'integration : pour 5 pages, verifier la liste exacte de tools exposes au LLM.
- [ ] Trace dans `tool_call_logs` : nouveau champ `tools_offered: list[str]` (audit).

## Implementation guidee

1. **Backend** : nouveau noeud `tool_selector_node` dans `backend/app/graph/nodes/`.
2. **Config** : `tool_selector_config.py` avec mapping versionne.
3. **State** : migration LangGraph `ConversationState` (champs additifs, pas de breaking change).
4. **Frontend** : `useChat.ts` envoie `page_context` derive de `useRoute().path`.
5. **Tests** : `backend/tests/graph/test_tool_selector.py` avec table de mapping page -> tools.

## Definition of Done

- Mapping couvre 8 pages principales.
- Frontend transmet `page_context` sur tous les chats.
- Logs montrent <=10 tools/tour sur 100% des cas (sample de 50 conversations).
- PR mergee.
