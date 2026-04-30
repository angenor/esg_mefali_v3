# Evidence E2E v2 — fix interactive widget (PR fix/interactive-widget-module-persist)

**Branche** : `fix/interactive-widget-module-persist`
**Date** : 2026-04-30 (~02:10 UTC)
**Compte test** : `moussa1@gmail.com` (cree pour le test, profil incomplet)
**Outil** : `agent-browser --headed` sur http://localhost:3000
**Backend** : uvicorn `esg_mefali_v3/backend/venv` sur :8000, DB dediee `esg_mefali_v3`

## Contexte

Cette evidence v2 a ete capturee APRES decouverte d'un troisieme bug (commit
manquant dans `_resolve_interactive_question`) lors du re-test E2E live. Le
patch B (ajout `await db.commit()` apres `db.flush()` ligne 549 de
`backend/app/api/chat.py`) a ete applique dans la meme PR pour debloquer
visuellement AC1.

Voir aussi `widget-esg-fix-evidence/` pour la session v1 (sur autre backend
sibling, schema DB different).

## Protocole execute (deux scenarios)

### Scenario A — Clic NORMAL (apres fin du stream)

1. Login + nouvelle conversation.
2. « lance mon évaluation ESG ».
3. Attendre que les radios soient `[ref=...]` (sans `[disabled]`) -> stream fini.
4. Cliquer Agriculture.
5. Verifier DB.

### Scenario B — Clic RAPIDE pendant le stream (race condition originale)

1. Nouvelle conversation.
2. « je veux faire mon évaluation ESG maintenant ».
3. Polling 200ms : DES QU'UN RADIO APPARAIT, cliquer immediatement (radios
   encore `[disabled]` = stream non termine).
4. Verifier DB.

## Fichiers

| Fichier | Description |
|---------|-------------|
| `01-db-before.txt` | DB vierge avant test (0 questions). |
| `02-chat-open.png` | Nouvelle conversation ouverte. |
| `03a-widget-visible.png` | Scenario A : widget radios `enabled` (stream fini). |
| `03b-after-normal-click.png` | Scenario A : apres clic normal sur Agriculture. |
| `03c-db-after-scenario-A.txt` | DB apres scenario A : `state=answered`, `response_values=["agri"]`. |
| `04a-fast-click.png` | Scenario B : clic capture pendant que radios sont `[disabled]`. |
| `04b-after-fast-click.png` | Scenario B : UI apres clic rapide. |
| `04c-db-after-scenario-B.txt` | DB apres scenario B : `state=answered`, `response_values=["agriculture"]`. |
| `05-input-reactivated.png` | Input texte reactive apres reponse aux widgets. |
| `06-db-final.txt` | Etat final DB (3 answered + 1 pending normale du flow). |

## Validation des criteres d'acceptation

| AC | Statut | Note |
|----|--------|------|
| AC1 — `state='answered'` apres clic NORMAL (Scenario A) | OK | `e3183458 \| chat \| answered \| ["agri"] \| answered_at rempli` |
| AC1 — `state='answered'` apres clic RAPIDE pendant stream (Scenario B, race condition) | OK | `c7f6f150 \| chat \| answered \| ["agriculture"] \| answered_at rempli` |
| AC2 — `module='esg_scoring'` quand widget vient d'esg_scoring | OK (par tests TDD) | Le widget teste ici vient legitimement du `chat_node` (profilage onboarding car profil incomplet), donc `module='chat'` est correct. La propagation `active_module` dans `RunnableConfig.configurable` est validee par 4 tests TDD `TestActiveModulePropagationToConfigurable`. |
| AC3 — Reponse propage vers `esg_criteria`/`esg_assessments` | Hors scope | Deporte a la story 10.6 (chainage backend a faire). |
| AC4 — Input texte reactive apres reponse au widget | OK | `05-input-reactivated.png` montre `textbox "Ecrivez votre message..."` SANS `[disabled]`. |
| AC5 — 3+ screenshots dans le dossier | OK | 7 screenshots + 4 fichiers DB. |

## Tests automatises (regression)

```
339 passed, 2 warnings in 25.84s
```

Suites couvertes : `test_graph/`, `test_ask_interactive_question_tool.py`,
`test_interactive_question_api.py`, `test_interactive_question_schemas.py`,
`test_api/test_chat_guidance_stats.py`, `graph/`.

## Bugs corriges par cette PR

1. **Race condition stream** (`frontend/app/composables/useChat.ts`) : avorter
   le stream et envoyer la reponse au lieu d'un early-return silencieux.
2. **Persistance du module** (`backend/app/graph/nodes.py`) :
   `_propagate_node_context` injecte `active_module` + `active_module_data`
   dans le `RunnableConfig.configurable` avant l'invocation LLM.
3. **Commit asyncpg manquant** (`backend/app/api/chat.py::_resolve_interactive_question`) :
   `await db.commit()` apres `db.flush()` pour persister la resolution avant
   que le streaming SSE en aval ne ferme la connexion asyncpg.

## Hors scope (story 10.6)

- Chainage **reponse-widget -> table `esg_criteria`/`esg_assessments`** :
  meme apres ces trois fixes, repondre a un widget ESG en mode chat ne propage
  pas la valeur vers le scoring ESG dynamique. Voir story 10.6.
