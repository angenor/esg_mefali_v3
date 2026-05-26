# Contract — Contexte ESG proactif (D2)

**Fichiers** : `backend/app/api/chat.py` (`_load_full_context_for_state`, propagation state), `ConversationState`, prompts `backend/app/graph/nodes.py`

## `_load_full_context_for_state(db, user_id)` (modifié)

Retour étendu :

```python
{
  "profile": <profil>,
  "projects": [<projets actifs>],            # inchangé
  "project_esg_assessments": [               # NOUVEAU — résumé léger
    {
      "project_id": "<uuid>", "project_name": "...",
      "assessment_id": "<uuid>", "referential_code": "boad_ess",
      "state": "finalized", "score": 55,
      "coverage_rate": 0.62, "covered_count": 8, "missing_count": 2
    }
  ]
}
```

- Borné aux projets actifs déjà chargés (réutilise `get_active_projects_for_user`, limit 20).
- Scoping `account_id` (RLS F02). Tolérant aux erreurs (liste vide en cas d'échec, comme `projects`).
- ≤ 1 requête SQL supplémentaire (jointure assessments ↔ projets actifs).

## `ConversationState`
- Nouveau champ `user_project_esg_assessments: list[dict] | None` (analogue `user_projects`), propagé depuis `chat.py` (~ligne 1239).

## Directive prompt (nœuds financing / application / esg_scoring)
Injecter une consigne :
> « Si une évaluation ESG existe dans le contexte (`user_project_esg_assessments`), NE déclare PAS un critère manquant sans avoir appelé `get_project_esg_assessment(assessment_id=…)` pour lire l'état réel. Pour démarrer, retrouve le projet via le contexte/`list_projects`, puis `list_project_esg_assessments(project_id=…)`. Ne crée pas un second assessment si un draft existe (réutilise-le). »

## Cas de test (TDD)
| # | Situation | Attendu |
|---|-----------|---------|
| T1 | user avec 1 assessment finalized | résumé présent dans le retour, compteurs corrects |
| T2 | user sans assessment | clé présente = `[]`, pas d'erreur |
| T3 | erreur SQL simulée | retour `[]`, log, pas d'exception propagée |
| T4 | multi-tenant | seuls les assessments de l'`account_id` du user |
| T5 | propagation state | `user_project_esg_assessments` présent dans le state LangGraph |

## Comportement chatbot (intégration / E2E)
- Session A : saisir ≥ 2 critères d'un référentiel pour un projet.
- Session B (nouvelle conversation) : « où en est mon évaluation ESG du projet X » → le chatbot reconnaît l'évaluation et les critères couverts, **ne** les liste **pas** comme manquants (FR-009, SC-002).
