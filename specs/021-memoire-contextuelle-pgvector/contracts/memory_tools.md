# Contract : Tool LangChain `recall_history`

Module : `backend/app/graph/tools/memory_tools.py`

---

## Signature

```python
from datetime import datetime
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


class RecallHistoryArgs(BaseModel):
    """Paramètres du tool recall_history."""

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Requête textuelle libre décrivant ce que l'on cherche dans l'historique.",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Nombre maximum de résultats à retourner (1 à 10, défaut 5).",
    )
    since: datetime | None = Field(
        default=None,
        description="Date ISO 8601 optionnelle. Limite les résultats aux chunks créés à cette date ou après.",
    )
    include_current_conversation: bool = Field(
        default=False,
        description=(
            "Si False (défaut), exclut la conversation courante du résultat (les 15 derniers messages "
            "y sont déjà). Si True, inclut la conversation courante (utile pour chercher au-delà de "
            "la fenêtre des 15 derniers messages dans la même conversation)."
        ),
    )


@tool(args_schema=RecallHistoryArgs)
async def recall_history(
    query: str,
    max_results: int = 5,
    since: datetime | None = None,
    include_current_conversation: bool = False,
    state: Annotated[dict, InjectedState] = None,
) -> list[dict]:
    """
    Récupère des messages anciens de l'historique conversationnel sémantiquement proches de la requête.

    Use when:
      - L'utilisateur fait référence à un échange passé ("tu te souviens", "la dernière fois", "il y a X temps").
      - Le contexte récent (15 derniers messages + 3 résumés) est insuffisant pour répondre.
      - L'utilisateur cite un projet, un fonds, un montant ou un détail qu'il a partagé dans le passé.

    Don't use when:
      - L'information demandée est dans les 15 derniers messages (déjà dans le contexte).
      - L'information est dans le profil entreprise, les projets actifs, ou les scores ESG/carbon récents
        (ces données sont injectées séparément).
      - La requête est générale et ne fait pas explicitement référence au passé conversationnel.

    Exemple :
      User : "Tu te souviens du nom du fonds qu'on évoquait pour mes panneaux solaires il y a 2 mois ?"
      → recall_history(query="fonds panneaux solaires", max_results=3)
      Retourne les 3 messages historiques les plus pertinents.
    """
    ...
```

## Comportement

1. **Lecture du contexte d'exécution** : le tool récupère depuis `state` (injecté par LangGraph) :
   - `account_id` : l'identifiant du tenant courant (déjà placé dans le state par `chat.py`).
   - `current_conversation_id` : l'identifiant de la conversation en cours.
   - Si l'un ou l'autre manque → log warning + retour liste vide (défense en profondeur).
2. **Délégation au service** : appelle `app.modules.memory.service.search_history(...)` avec les paramètres validés.
3. **Sérialisation du retour** : transforme la liste de `MessageRecallResult` en liste de dict prête à être injectée dans le contexte LLM.

## Contrat de retour

Liste de dictionnaires (max `max_results` éléments). Chaque dict contient :

| Champ | Type | Description |
|---|---|---|
| `message_id` | str (UUID) | Identifiant du message d'origine. |
| `conversation_id` | str (UUID) | Identifiant de la conversation. |
| `conversation_title` | str | Titre de la conversation (utile pour situer). |
| `role` | str | `user` ou `assistant`. |
| `chunk_text` | str | Texte du chunk (déjà masqué). |
| `created_at` | str (ISO 8601) | Horodatage UTC. |
| `relative_time` | str | Format français : « il y a 3 jours », « le 12/03/2026 ». |
| `similarity` | float | Score cosinus dans [0, 1] (1 = identique, > 0.6 = pertinent). |

Si aucun résultat ne dépasse le seuil 0.6, retourne `[]` (liste vide).

## Validation Pydantic v2

- `query` : 2 à 500 caractères. Requis. Vide → erreur Pydantic remontée comme erreur outil au LLM.
- `max_results` : 1 à 10. Hard cap server-side même si LLM demande plus.
- `since` : datetime UTC. Si timezone-naïve, considérée UTC.
- `include_current_conversation` : booléen. Pas de coercion.

## Erreurs

| Cas | Comportement |
|---|---|
| `account_id` absent du state | Log warning, retour `[]`. |
| Embedding API timeout (5 s) | Log warning, retour `[]`. |
| RLS context non positionné (bug applicatif) | Log error, retour `[]`. |
| Query trop courte (< 2 caractères) | Pydantic rejette, erreur retournée au LLM (auto-correction). |
| Aucun chunk indexé pour cet account | Retour `[]` normal. |

## Visibilité

`recall_history` est ajouté à `GLOBAL_WHITELIST` dans `app/graph/tool_selector_config.py`. Il est donc exposé dans **tous les nœuds spécialistes** (chat, esg_scoring, carbon, financing, application, credit, action_plan).

`MAX_TOOLS_PER_TURN` est porté de 13 à 14 pour absorber l'ajout (validé : `_validate_config()` mis à jour).

## Tests requis

Référence : `backend/tests/memory/test_recall_history_tool.py`.

| # | Test | Vérification |
|---|------|--------------|
| 1 | `test_recall_history_basic_success` | Crée 5 messages, embed, query similaire → retourne 1+ résultats avec similarity > 0.6. |
| 2 | `test_recall_history_threshold_filter` | Crée messages non pertinents → retourne `[]` (similarité < 0.6). |
| 3 | `test_recall_history_since_filter` | Crée messages anciens (1 an) et récents (1 jour) avec `since=hier` → seuls les récents remontent. |
| 4 | `test_recall_history_rls_isolation_account_a_vs_b` | Crée 100 chunks dans account A, 100 dans account B avec contenu identique. Recall depuis A → 0 résultats d'account B (vérification SQL directe). |
| 5 | `test_recall_history_include_current_conversation_flag` | Conv courante a 30 messages. Sans flag → seuls les chunks d'autres conversations remontent. Avec flag `true` → chunks de la courante peuvent remonter aussi. |

Coverage cible ≥ 80 % sur ce fichier de tool.
