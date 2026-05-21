# Contracts — Tool LangChain `match_funds_for_project` (Feature 045)

**Date** : 2026-05-21
**Branche** : `045-matching-projet-centric`

Ce document décrit le nouveau tool LangChain qui permet à l'agent conversationnel Claude de déclencher le matching projet → fonds depuis le chat. Le tool s'ajoute aux 7 tools projet existants (F06) et aux 4 tools matching F14.

---

## 1. Signature Python

Dans `backend/app/graph/tools/project_tools.py` :

```python
from langchain.tools import tool
from pydantic import BaseModel, Field
from uuid import UUID


class MatchFundsForProjectArgs(BaseModel):
    """Arguments du tool match_funds_for_project."""

    project_id: UUID = Field(
        ...,
        description=(
            "UUID du projet pour lequel calculer le matching. "
            "Doit appartenir au compte de l'utilisateur (RLS F02 silencieux sinon)."
        ),
    )
    min_score: int = Field(
        default=60,
        ge=0,
        le=100,
        description=(
            "Seuil minimum sur project_score (0..100) pour inclusion. "
            "Défaut 60 — ajustable si la PME veut voir tous les matches."
        ),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=10,
        description=(
            "Nombre maximum de matches retournés (top N par project_score). "
            "Hard cap 10 pour limiter le payload LLM."
        ),
    )


@tool(args_schema=MatchFundsForProjectArgs)
async def match_funds_for_project(
    project_id: UUID,
    min_score: int = 60,
    limit: int = 10,
) -> str:
    """Calcule (ou récupère du cache) la liste des fonds verts compatibles
    avec un projet précis, classés par score projet décroissant.

    Émet jusqu'à 5 <MatchCardBlock> (F11) via marker SSE en parallèle du
    texte retourné. Le score projet est calculé à partir des attributs du
    projet (taxonomie UEMOA, thèmes GCF, impact CO2, bénéficiaires, gender,
    populations vulnérables, ESG projet) sans propagation du score
    entreprise comme bottleneck.

    Renvoie un JSON compact (string serializée) à destination du LLM, qui
    peut reformuler les résultats pour la PME en français.
    """
    # Implémentation : appel à matching_service.match_funds_for_project_chat(...)
    # Émission des blocks F11 via emit_visualization_block(...)
    ...
```

### 1.1 Décorateurs et configuration

- `@tool(args_schema=MatchFundsForProjectArgs)` : LangChain expose le tool au LLM avec son schéma JSON.
- Mutation/lecture : **lecture seule** (le calcul est idempotent côté payload, le UPDATE in-place sur `offer_matches` est un effet de side acceptable car invisible au caller).
- `source_of_change` : `'llm'` quand le tool écrit dans `offer_matches` (UPDATE in-place) — propagé via le ContextVar F03 par le décorateur `@_with_llm_source` (à appliquer).

### 1.2 Inclusion dans les whitelists

- `project_tools.py` : exporté dans `__all__` à côté des 7 tools F06 existants.
- `tool_selector_config.py` :
  - `MODULE_TOOL_MAPPING['financing']` : ajouter `"match_funds_for_project"`.
  - `MODULE_TOOL_MAPPING['application']` : ajouter `"match_funds_for_project"`.
  - `PAGE_TOOL_MAPPING['profile_projects']` : ajouter `"match_funds_for_project"`.
  - `PAGE_TOOL_MAPPING['chat']` : ajouter `"match_funds_for_project"`.
- `MAX_TOOLS_PER_TURN` actuel = 29 → +1 reste sous la cap. Pas besoin de bumper.

---

## 2. Payload JSON retourné au LLM

Retour string `json.dumps(payload, ensure_ascii=False, indent=None)` :

```jsonc
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "Agroforesterie 200ha Togo",
  "matches_count": 5,
  "top_matches": [
    {
      "offer_id": "...",
      "fund_name": "Green Climate Fund",
      "intermediary_name": "BOAD",
      "project_score": 78,
      "company_score": 12,
      "divergence_short": "Projet vert éligible, entreprise à renforcer",
      "top_3_blockers_project": [
        {
          "key": "co2_impact_below_threshold",
          "label_fr": "Impact CO2 estimé en dessous du seuil GCF",
          "current_value": 450,
          "target_value": 1000
        }
        // ... max 3 critères
      ]
    }
    // ... max 10 (limit)
  ],
  "no_match_reason": null,
  "visualization_emitted": true                          // True si 1+ MatchCardBlock SSE émis
}
```

### 2.1 Champ `divergence_short`

Version courte (≤ 80 caractères) de `divergence_explanation` (R6), générée par même gabarit FR mais condensée pour le payload LLM (économie de tokens) :

| Cas | divergence_short |
|---|---|
| convergent | « Projet et entreprise alignés » |
| projet_fort | « Projet vert éligible, entreprise à renforcer » |
| entreprise_forte | « Entreprise solide, projet à renforcer côté impact » |
| moyen | « Profils contrastés — voir détails » |

### 2.2 Champ `no_match_reason`

Présent uniquement si `matches_count == 0`. Texte FR explicatif (cf. R13 et US3 acceptance scenario 1) :

```
"Aucun fonds n'aligne ses critères avec ce projet. Pour augmenter votre éligibilité, renseignez : alignement taxonomie verte UEMOA, impact CO2 chiffré, thèmes GCF prioritaires."
```

---

## 3. Émission des blocks visualisation F11

Pendant l'exécution du tool, et **avant** de retourner le payload LLM, le tool émet jusqu'à 5 `<MatchCardBlock>` (F11) via marker SSE :

```python
from app.graph.tools.visualization_helpers import emit_visualization_block

for match in top_matches[:5]:
    block_payload = MatchCardBlockSchema(
        title=f"{match.fund_name} via {match.intermediary_name}",
        project_score=match.project_score,
        company_score=match.company_score,
        divergence=match.divergence_short,
        fund_url=f"/financing/offers/{match.offer_id}",
        sources=match.project_score_breakdown.sources_used,
        # ... cf. data-model.md §3 et schemas F11
    )
    await emit_visualization_block(
        block_type="match_card_project",
        payload=block_payload.model_dump(),
    )
```

Le marker SSE émet `<!--SSE:{"__sse_visualization_block__":true,"block_type":"match_card_project",...}-->`.

### 3.1 Schema MatchCardBlock étendu

Le schema F11 existant `MatchCardBlockSchema` est étendu pour accepter 2 scores au lieu d'1 :

```python
class MatchCardBlockSchema(BaseModel):
    """Block visualisation F11 — MatchCard projet-centric."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str = Field(..., max_length=120)
    project_score: int = Field(..., ge=0, le=100)
    company_score: int = Field(..., ge=0, le=100)
    divergence: str = Field(..., max_length=100)       # divergence_short FR
    fund_url: str = Field(...)
    sources: list[SourceRefSchema] = Field(default_factory=list, max_length=10)
    missing_criteria_top_3: list[MissingCriterionSchema] = Field(
        default_factory=list, max_length=3
    )
    factor_status: Literal["ok","sources_pending","unsourced_fallback"] = "ok"
```

### 3.2 Cohabitation avec le schema F14 MatchCardBlock

F14 a un schema `MatchCardBlockSchema` qui contient `fund_score`, `intermediary_score`, `global_score`, `bottleneck`. La 045 ajoute un **nouveau** schema `MatchCardProjectBlockSchema` (block_type différent : `"match_card_project"` vs F14 `"match_card"`) pour éviter la rupture. Le frontend route les 2 types vers 2 composants Vue distincts :
- `block_type='match_card'` → `<MatchCardBlock>` (F14 existant)
- `block_type='match_card_project'` → `<ProjectMatchCardBlock>` (045 nouveau)

---

## 4. Gestion d'erreurs

Le tool ne lève **jamais** d'exception au LLM. Il renvoie des payloads structurés avec champ `error` :

```jsonc
{
  "error": {
    "code": "project_not_found",
    "message_fr": "Le projet demandé n'existe pas ou n'appartient pas à votre compte."
  }
}
```

Codes d'erreur :
| code | message_fr | Cause |
|---|---|---|
| `project_not_found` | « Le projet demandé n'existe pas ou n'appartient pas à votre compte. » | RLS F02 ou UUID inexistant |
| `migration_not_applied` | « La fonctionnalité de matching projet n'est pas encore disponible. » | Colonne `project_score` absente (déploiement en cours) |
| `no_offers_published` | « Aucune offre n'est encore publiée dans le catalogue. » | Catalogue F25 vide |
| `recompute_in_progress` | « Un recalcul est en cours. Réessayez dans quelques secondes. » | Lock applicatif debounce 30s déjà actif |

---

## 5. Source de changement (audit F03)

Le tool s'exécute dans un contexte `source_of_change='llm'` (ContextVar F03), propagé par le décorateur `@_with_llm_source` appliqué au handler. Pas de modification de `AUDITABLE_MODELS` (OfferMatch est déjà exempté F03 car ce n'est pas une entité métier directe — c'est un cache calculé).

---

## 6. Test conformity

Tests `backend/tests/conformity/test_tool_match_funds_for_project.py` à créer :

1. **`test_tool_in_global_whitelist_or_module_mapping`** : vérifie que `match_funds_for_project` apparaît dans au moins un mapping de `tool_selector_config.py`.
2. **`test_tool_emits_visualization_block`** : appel mocké du tool avec 2 offres mockées → vérifie que `emit_visualization_block` a été appelé avec `block_type='match_card_project'`.
3. **`test_tool_returns_no_match_reason_when_empty`** : projet sans alignement → payload contient `no_match_reason` non vide et `matches_count == 0`.
4. **`test_tool_respects_rls`** : appel avec `project_id` d'un autre compte → retour `{ error: { code: 'project_not_found' } }`, pas d'exception.
5. **`test_tool_boost_rule_rouge_entreprise_vert_projet`** : profil PME score entreprise indéterminé + projet vert → top_matches contient GCF/FEM/Fonds d'Adaptation si présents en catalogue (SC-002 du spec).
