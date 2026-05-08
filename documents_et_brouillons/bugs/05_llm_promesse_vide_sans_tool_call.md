# Bug 05 — Le LLM promet une action sans appeler le tool correspondant

## Symptôme

Lorsque l'utilisateur exprime une intention de création/mutation en langage naturel, le LLM répond souvent par une **promesse textuelle** (« Je vais créer ce projet immédiatement », « Je lance votre évaluation maintenant », etc.) **sans invoquer le tool** correspondant. Aucun `tool_call_start` n'apparaît dans le SSE, le `done` arrive juste après les tokens texte, et **rien n'est créé en BDD**.

Reproduction (session du 2026-05-08, conversation `e3a4d132-a067-4f8d-81b5-bfcaa9c82a60`) :

| Message utilisateur | Réponse LLM | Tool appelé ? |
|---|---|---|
| « Crée mon projet vert : nom 'Solarisation Boulangerie Dakar', installer 50 kWc... maturité ideation, statut brouillon. Confirme la création. » | « Je vais créer ce projet vert immédiatement. » (4 tokens, puis done) | ❌ Aucun |
| « Appelle MAINTENANT le tool create_project avec ces parametres exacts : name='...', description='...', objective_env=[...], maturity='ideation', status='draft', target_amount_amount=35000000, target_amount_currency='XOF', location_country='SN', location_region='Dakar'. » | (silence, puis tool_call) | ✅ `create_project` |

Conséquence : l'expérience conversationnelle est cassée. L'utilisateur croit que son projet est créé, navigue ailleurs, ne trouve rien. Pour réussir une action, il doit déjà connaître le nom du tool et le format de ses paramètres — l'inverse de ce qu'un assistant LLM est censé apporter.

## Cause racine (hypothèses à valider)

Trois pistes non exclusives :

1. **Prompt système trop défensif** — `backend/app/graph/nodes.py:1664-1680` injecte des instructions du type *« Ne réponds JAMAIS de mémoire »*, *« ANTI-BOUCLE ESG : Tu ne dois JAMAIS poser de widget »*, etc. Beaucoup de NEVER, peu de MUST. Le LLM peut interpréter le silence sur les actions de création comme une zone d'ombre et préférer répondre en texte.

2. **Manque d'instruction "must call tool when user expresses creation intent"** — aucune phrase du prompt ne dit explicitement : *« Quand l'utilisateur demande de créer/modifier/supprimer une entité, tu DOIS invoquer le tool correspondant dans la même réponse, sans demander de confirmation textuelle préalable. »*.

3. **Selecteur de tools n'expose pas `create_project` sur le bon scope** — à vérifier. `_PATH_TO_SLUG_PATTERNS` mappe `/profile/projects` → slug `profile_projects` qui contient bien `create_project` (cf. `tool_selector_config.py:88-94`), mais il faut confirmer que `select_tools_for_node(node_name="chat", current_page="/profile/projects")` retourne effectivement `create_project` au runtime. Un debug log existe (`debug_info["tools_offered"]`) — il faut le tracer.

## Fichiers concernés

- `backend/app/graph/nodes.py:1600-1750` — `chat_node` : prompt système, sélection tools, bind_tools
- `backend/app/graph/nodes.py:1664-1680` — bloc `tool_instructions` (à enrichir)
- `backend/app/prompts/system.py` — `build_system_prompt` et `build_page_context_instruction`
- `backend/app/graph/tool_selector.py` — `select_tools_for_node` (vérifier le retour)
- `backend/app/graph/tool_selector_config.py` — `PAGE_TOOL_MAPPING` (vérifier que `profile_projects` expose `create_project`)
- `backend/app/graph/tools/project_tools.py:394-461` — docstring `create_project` (déjà bonne, ne pas modifier sans raison)

## Tâche

1. **Diagnostic d'abord — pas de fix aveugle** :
   - Activer un log explicite des `tools_offered` au début de `chat_node` (en `INFO`, pas `DEBUG`) pour voir, à chaque tour, quels tools sont effectivement transmis au LLM.
   - Lancer un test reproductible : envoyer un message de création de projet sur `/profile/projects` et capturer les logs. Confirmer que `create_project` est bien dans `tools_offered`.
   - Si **non** : c'est un bug de sélection (corriger le mapping ou la logique).
   - Si **oui** : c'est un problème de prompt/comportement LLM → poursuivre étapes 2-3.

2. **Renforcer le prompt système** (si étape 1 valide que les tools sont bien exposés) :
   - Ajouter dans `tool_instructions` (ou `build_page_context_instruction`) une règle explicite :
     ```
     RÈGLE D'INVOCATION DES TOOLS (impérative) :
     - Si l'utilisateur exprime une intention de CRÉATION, MODIFICATION ou SUPPRESSION
       d'une entité (projet, candidature, évaluation, etc.) ET qu'un tool correspondant
       est dans ta liste de tools, tu DOIS l'invoquer DANS LA MÊME RÉPONSE.
     - N'annonce JAMAIS « je vais créer », « je lance », « je vais ajouter » sans appeler
       le tool en parallèle. Les promesses textuelles sans action sont un échec produit.
     - Si des paramètres essentiels manquent (ex: `name` pour create_project), pose UNE
       question ciblée puis attends la réponse — n'invente pas de valeurs.
     ```
   - Important : tester avec 5+ formulations naturelles différentes pour valider la robustesse.

3. **Tests de non-régression** :
   - Créer `backend/tests/graph/test_chat_node_tool_invocation.py` avec un mock LLM qui retourne soit du texte seul, soit du texte + tool_call. Valider que pour une intention de création, le tool est appelé.
   - Test E2E (Playwright ou direct SSE) : envoyer 5 messages naturels de création (projet, application, etc.), vérifier que chaque message produit AU MOINS un `tool_call_start` correspondant.

4. **Métrique optionnelle** :
   - Ajouter un compteur Prometheus / log structuré `chat_node.empty_promise` qui incrémente quand une réponse contient un verbe d'action au futur proche (« je vais créer/lancer/ajouter ») mais aucun `tool_call`. Surveille la régression à long terme.

## Critères d'acceptation

- [ ] Étape 1 (diagnostic) produit un log clair `tools_offered=[...]` à chaque tour de chat_node.
- [ ] Le test E2E des 5 formulations naturelles passe à 5/5 (avant fix : 0/5 ou 1/5).
- [ ] Pas de régression sur la « ANTI-BOUCLE ESG » : le LLM ne pose pas de widget de confirmation pour les évaluations ESG (cf. `_detect_esg_request`).
- [ ] Pas de régression sur la sourçage F01 : les chiffres restent décorés de `cite_source`.
- [ ] La nouvelle règle de prompt ne dépasse pas 6 lignes (budget tokens).

## Notes

- Bug observé avec Claude Sonnet 4.6 (via OpenRouter, `.env:18`). Les modèles plus petits (Haiku) ou plus anciens peuvent avoir un comportement différent (plus prudent ou plus impulsif).
- À ne pas confondre avec le bug d'**hallucination de noms de tools** (LLM invente `ask_yes_no` au lieu d'`ask_interactive_question`) observé pendant la session minimax — ce dernier est résolu par le passage à un modèle qui supporte le tool-calling natif.
- Lié partiellement au bug 04 (concurrent tool calls) : si fixer 04 ralentit les tools, le LLM pourrait être tenté de préférer le texte. À surveiller.
- Vérifier en passant si le bouton "Ouvrir l'assistant IA" est présent sur `/profile/projects` (cf. bug 06) — sinon le diagnostic UI est compromis.
