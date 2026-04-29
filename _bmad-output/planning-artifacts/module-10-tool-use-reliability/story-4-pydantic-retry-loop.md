---
story_id: M10-S4
epic: M10-EPIC-1
title: Boucle de correction Pydantic (1 retry max + fallback)
status: ready
priority: P4
effort: "0.5 j"
source_items: [10.5, 10.8.4]
created: 2026-04-29
depends_on: [M10-S1]
---

# Story M10-S4 — Boucle de correction Pydantic (1 retry)

## Contexte

Meme avec des schemas stricts (M10-S1), le LLM produit parfois un payload invalide (mauvais enum,
champ absent). Aujourd'hui, l'erreur Pydantic remonte brute jusqu'au frontend ou est silencieusement
ignoree. Il faut une boucle de correction bornee qui renvoie l'erreur au LLM pour autocorrection,
puis fallback texte si echec persiste.

## Objectif

Implementer une boucle de validation/retry dans le `tool_node` LangGraph :
1. Validation Pydantic du payload tool_call.
2. Si invalide : 1 retry avec erreur structuree injectee dans le contexte.
3. Si invalide apres retry : fallback texte « je n'arrive pas a formaliser cette action, peux-tu
   reformuler ? » + log d'incident.

## Criteres d'acceptation

- [ ] Wrapper `validate_tool_call(tool_call) -> ValidationResult` dans
  `backend/app/graph/tool_validation.py` :
  - retourne `ValidationResult(valid=True, payload=...)` ou
  - retourne `ValidationResult(valid=False, errors=[...], retry_message="...")`.
- [ ] `tool_node` modifie pour boucler max 1 fois sur invalide, puis fallback texte.
- [ ] Erreur structuree injectee au LLM au format :
  ```
  Le tool {tool_name} a rejete ton appel. Erreurs :
  - field "X": doit etre un enum parmi [A, B, C], tu as envoye "Y"
  - field "Z": requis manquant
  Reessaie avec un payload corrige.
  ```
- [ ] Apres retry echoue : reponse texte fallback ET log d'incident dans `tool_call_logs`
  (champs `validation_status: "failed_after_retry"`, `retry_count: 1`, `pydantic_errors: [...]`).
- [ ] Migration Alembic : ajouter `validation_status: str`, `retry_count: int`, `pydantic_errors: jsonb | null`
  a la table `tool_call_logs`.
- [ ] Tests unitaires :
  - payload valide au 1er essai -> pas de retry, status `"valid"`.
  - payload invalide puis valide au retry -> status `"valid_after_retry"`, retry_count=1.
  - payload invalide 2x -> status `"failed_after_retry"`, fallback texte renvoye au frontend.
- [ ] Test d'integration : appel chat avec un message qui force le LLM a produire un payload
  invalide deterministiquement (mock LLM), verifier le comportement de bout en bout.

## Implementation guidee

1. **Backend** : `backend/app/graph/tool_validation.py` (nouveau).
2. **Backend** : modifier `backend/app/graph/nodes/tool_node.py` pour integrer la boucle.
3. **Migration** : `backend/alembic/versions/XXX_add_validation_to_tool_call_logs.py`.
4. **Tests** : `backend/tests/graph/test_tool_validation.py`.

## Definition of Done

- Migration appliquee.
- Boucle implementee, max 1 retry hard-code.
- Tests passent (unitaires + integration).
- Fallback texte affiche dans le chat lors d'un echec persistant (verification manuelle).
- PR mergee.
