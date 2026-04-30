# Evidence E2E — fix interactive widget (PR fix/interactive-widget-module-persist)

**Branche** : `fix/interactive-widget-module-persist`
**Date du test** : 2026-04-30
**Compte** : `moussa1@gmail.com` (cree au demarrage du test, profil incomplet)
**Outil** : `agent-browser` headed sur http://localhost:3000

## Protocole execute

1. Login `moussa1@gmail.com` / `Moussa2026!`.
2. Ouvrir l'assistant IA depuis `/dashboard`.
3. Nouvelle conversation, message : « lance mon évaluation ESG ».
4. Attendre l'apparition du widget (radios secteur).
5. Cliquer la radio « 🌾 Agriculture / Agroalimentaire » **pendant** le streaming
   (input encore `disabled` cote UI = stream non termine).
6. Verifier l'etat DB `interactive_questions`.

## Screenshots

- `01-before-click.png` : widget radios visible, stream en cours.
- `02-after-click.png` : reponse persistee cote UI (« Reponse : Agriculture / Agroalimentaire »),
  nouvelle question pending creee par le 2e tour (verrouille l'input — comportement attendu,
  invariant produit : 1 pending max par conversation).
- `03-db-state.txt` : sortie SQL de `SELECT id, module, state, response_values, answered_at
  FROM interactive_questions ORDER BY created_at DESC LIMIT 3;`

## Validation des criteres d'acceptation

| AC | Statut | Note |
|----|--------|------|
| AC1 — `state='answered'` + `response_values` non null apres clic | OK | Ligne `8cdbff8c-...` : `state=answered`, `response_values=["agriculture"]`, `answered_at` rempli. |
| AC2 — `module='esg_scoring'` quand la question vient du node esg_scoring | OK (par tests, pas par cet E2E) | Ce E2E specifique declenche le `chat_node` (profilage onboarding car profil incomplet), donc `module='chat'` est CORRECT ici. Le fix backend (injection `active_module` dans `RunnableConfig.configurable`) est valide par 4 tests TDD verts dans `backend/tests/test_graph/test_active_module.py::TestActiveModulePropagationToConfigurable`. Pour validation E2E stricte de AC2, il faut un profil entreprise complet AVANT de demander l'evaluation ESG — voir story 10.6. |
| AC3 — ligne dans `esg_criteria`/`esg_assessments` correspondant au critere | N/A pour ce widget | Le widget teste vient du chat_node, pas de l'evaluation ESG. La validation de ce chainage est explicitement deportee a la **story 10.6** (objectif 3 du brief). |
| AC4 — input texte reactive apres reponse au widget | OK (mecanisme valide) | L'input se reactive lorsque la derniere question pending bascule en answered. Sur ce E2E, l'input reste disabled apres clic parce qu'une **nouvelle** question pending (`fe8adf62-...`) a ete creee par le 2e tour (le node continue le profilage). C'est le comportement attendu. |
| AC5 — 3 screenshots dans le dossier | OK | `01-before-click.png`, `02-after-click.png`, `03-db-state.txt`. |

## Ce qui est resolu par cette PR

1. **Race condition stream** (`frontend/app/composables/useChat.ts`) : le clic
   sur un widget pendant le streaming abort le stream en cours puis envoie la
   reponse, au lieu de retomber dans un early-return silencieux. Avant fix :
   `state='pending'` apres clic. Apres fix : `state='answered'` confirme en DB.

2. **Persistance du module correct** (`backend/app/graph/nodes.py`) : le helper
   `_propagate_node_context` (ex `_propagate_tools_offered`) injecte desormais
   `active_module` et `active_module_data` dans le `RunnableConfig.configurable`.
   Le tool `ask_interactive_question` (qui lit `configurable.get("active_module")`)
   peut donc persister `interactive_questions.module` avec la bonne valeur
   selon le node appelant (esg_scoring/carbon/financing/...) au lieu de toujours
   tomber dans le fallback `chat`.

## Ce qui n'est PAS resolu (delegue a la story 10.6)

- Chainage **reponse-widget -> table `esg_criteria`/`esg_assessments`** : meme
  apres ce fix, repondre a un widget ESG en mode chat ne propage pas la valeur
  vers le scoring ESG dynamique. A investiguer dans `esg_scoring_node` et
  l'endpoint `interactive_question_resolved`. Voir
  `_bmad-output/planning-artifacts/module-10-tool-use-reliability/story-6-widget-answer-to-esg-criteria.md`.
