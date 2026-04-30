---
story_id: M10-S6
epic: M10-EPIC-1
title: Chainage reponse-widget -> esg_assessments / esg_criteria
status: backlog
priority: post-MVP
effort: "non chiffre"
created: 2026-04-30
depends_on: [M10-S1]
related_pr: fix/interactive-widget-module-persist
---

# Story M10-S6 — Reponse widget -> alimentation esg_assessments / esg_criteria

## Contexte

Suite a la PR `fix/interactive-widget-module-persist` (avril 2026) qui a corrige
trois bugs du widget interactif :

1. **Race condition stream** (frontend) : un clic sur widget pendant le streaming
   ne tombait plus dans un early-return silencieux ; il abort le stream en cours
   et envoie la reponse.
2. **Persistance du module** (backend) : le helper `_propagate_node_context`
   injecte `active_module` dans le `RunnableConfig.configurable`, ce qui permet
   au tool `ask_interactive_question` de stocker `interactive_questions.module`
   correctement (`esg_scoring`, `carbon`, etc.) au lieu de toujours tomber sur
   `chat`.
3. **Commit manquant dans `_resolve_interactive_question`** (backend) : un
   `await db.commit()` explicite est ajoute apres le `db.flush()` pour eviter
   que le commit final de `get_db` echoue avec `InterfaceError: cannot call
   Transaction.commit(): the underlying connection is closed` lorsque le
   streaming SSE en aval ferme la connexion asyncpg sous-jacente. Sans ce fix,
   la question restait `pending` meme apres un clic NORMAL post-stream.

**Constat residuel** : meme avec ces trois fixes, lorsqu'un node specialiste
(typiquement `esg_scoring_node`) pose une question via widget et que l'utilisateur
y repond, la reponse est bien persistee dans `interactive_questions` (avec le bon
`module`), mais **aucun chainage existant ne la propage vers le scoring ESG**.

Concretement :
- L'endpoint `POST /api/chat/interactive-questions/{id}/resolve` (ou equivalent
  `interactive_question_resolved`) marque la question comme `answered` et
  declenche un nouveau tour de conversation, mais n'ecrit rien dans `esg_criteria`
  ou `esg_assessments`.
- `esg_scoring_node`, lors du tour suivant, recoit la reponse sous forme de
  message texte « Reponse : <label> » dans l'historique. Il doit alors decider
  via le LLM d'appeler `save_esg_criterion` / `batch_save_esg_criteria` pour
  persister.
- Ce comportement n'est pas garanti et n'est pas testable de facon deterministe.

## Investigation a mener

1. Lire `backend/app/api/chat/interactive_questions.py` (ou route equivalente) :
   savoir si un hook post-resolution existe.
2. Lire `backend/app/graph/nodes.py::esg_scoring_node` : verifier si un mecanisme
   detecte « la reponse precedente repond a un critere ESG en cours d'evaluation »
   et appelle directement le service de scoring.
3. Lire `backend/app/graph/tools/esg_tools.py` : confirmer que le LLM dispose
   bien d'un tool pour persister un critere et que le prompt l'incite a le faire
   apres une reponse de widget.

## Pistes de design

- **Option A — Chainage explicite via metadata** : enrichir le payload du tool
  `ask_interactive_question` avec un champ optionnel `criterion_id` (et autres
  meta esg). A la resolution, un hook backend transforme directement la reponse
  en `esg_criteria.update(...)`.
- **Option B — Renforcement de prompt** : ajouter dans le prompt du node
  esg_scoring une regle explicite « apres une reponse de widget liee a un
  critere E-S-G, appelle save_esg_criterion immediatement avant toute autre
  action ». Plus simple, moins fiable.
- **Option C — Tool dedie** : `ask_esg_criterion_question` (variante du tool
  generique) qui trace le critere et chaine la persistance automatiquement.

Recommandation initiale : **A** (chainage explicite via metadata) pour la
deterministicite, avec **B** comme filet de securite.

## Criteres d'acceptation

- **AC-A** : Repondre a un widget ESG (issu du node `esg_scoring`) via le chat
  met a jour la table `esg_criteria` correspondante (champ `score` ou
  `evaluation` selon le modele de donnees actuel) sans requerir un appel LLM
  supplementaire pour declencher la persistance.
- **AC-B** : Le score ESG dynamique de l'entreprise (`esg_assessments.global_score`
  ou equivalent) reflete la reponse en temps reel — le `current_pillar` /
  `evaluated_criteria` evoluent dans le state au tour suivant.
- **AC-C** : Test d'integration backend end-to-end (`pytest`) qui :
  1. Cree une conversation et un assessment ESG en cours.
  2. Simule un widget ESG repondu via l'API `interactive-questions/{id}/resolve`.
  3. Asserte que `esg_criteria` contient une ligne pour le critere vise.
  4. Asserte que `esg_assessments.global_score` a ete recalcule.

## Hors scope

- Le formatage UI cote chat des criteres mis a jour (deja gere par les SSE).
- Le renforcement multi-tour (continuer a poser le critere suivant
  automatiquement) — c'est une story separee.
- Migration des `interactive_questions.module='chat'` heritage vers le bon
  module : il s'agit de donnees historiques, pas d'un bug present.

## Liens

- PR a l'origine de cette story : `fix/interactive-widget-module-persist`.
- Evidence E2E ayant revele le manque de chainage :
  `_bmad-output/implementation-artifacts/widget-esg-fix-evidence/README.md`.
- Fichiers a explorer en priorite :
  - `backend/app/api/chat/interactive_questions.py` (ou equivalent)
  - `backend/app/graph/nodes.py::esg_scoring_node`
  - `backend/app/graph/tools/esg_tools.py`
  - `backend/app/modules/esg/service.py`
