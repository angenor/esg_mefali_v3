# Deferred Work

## Deferred from: review of fix-profile-and-routing-regression (2026-04-30)

- **Asymétrie du fix routeur** : la garde défensive (reset `active_module` sur intention explicite) ne traite que ESG. Les modules `carbon`, `financing`, `application`, `credit`, `action_plan` restent vulnérables à la même séquelle si `active_module="chat"` traîne entre deux tours et que le LLM de continuation retourne `True`. À élargir dans une story dédiée — risque de régression cross-module si on l'inclut ici. [backend/app/graph/nodes.py:520-540]
- **Race condition multi-requêtes même `conversation_id`** : MemorySaver de LangGraph n'est pas transactionnel pour les mutations cross-call. Deux requêtes parallèles peuvent voir un checkpoint stale et écraser `active_module`. Pré-existant ; à traiter avec un lock par conversation_id ou la migration future vers checkpointer Postgres. [backend/app/graph/nodes.py::router_node]
- **`_has_active_esg_assessment` ne consulte que le state** : si l'`esg_assessment` vit en DB mais n'a pas encore été projeté dans le state, la garde peut considérer `has_active_esg=False` à tort et déclencher une session ESG dupliquée. Cross-check DB à ajouter. [backend/app/graph/nodes.py:421]
- **`_detect_esg_request` négation locale** : phrases combinant négation et intention positive (« je ne lance pas X, mais lance-le ») peuvent mal classer. Helper pré-existant ; à raffiner avec un fenêtrage local sur les clauses. [backend/app/graph/nodes.py:293]
- **AC1/AC2 runtime non couverts par tests automatisés** : le verdict final (rows `tool_call_logs` + `company_profiles` peuplés + `esg_assessments` créée) repose sur le replay E2E `agent-browser` à effectuer manuellement (cleanup DB via `/tmp/cleanup-moussa1.sql` puis session `profil-esg-complet-v2`). Décision intentionnelle (CLI sans navigateur headed) documentée dans le Spec Change Log du spec.

## Deferred from: fix-esg-scoring-node-routing review (2026-04-30)

- ~~**[M — HIGH, BUG PRE-EXISTANT révélé par AC5 replay]**~~ ✅ **RÉSOLU le 2026-04-30** dans le même PR. `backend/app/graph/tools/esg_tools.py:372-381` — coercion défensive `c if isinstance(c, dict) else c.model_dump()` ajoutée + test régression `test_batch_save_esg_criteria_accepts_pydantic_items` dans `tests/test_prompts/test_esg_tools.py`. Plus de TypeError post-reload. Cause initiale : Pydantic v2 + `args_schema=BatchSaveESGCriteriaArgs` (story 10.1) convertit l'input LangChain en `_CriterionItem` mais le code accédait `criterion["criterion_code"]` dict-style.
- **[J — LOW]** Frontend `pages/esg/index.vue` `startNewAssessment` — pas d'injection explicite de `assessment_id` dans le contexte du chat widget après création du draft. Fonctionnel grâce à `_load_resumable_assessment` (esg_scoring_node reprend le draft via `get_resumable_assessment` user-scoped), mais à valider en AC5 manual replay. Si la reprise échoue, ajouter une route param `?assessment_id=` ou un store transient.
- **[K — LOW]** Pas de test frontend (Vitest/Playwright) pour `startNewAssessment` couvrant : toast erreur, double-click guard (`isCreating`), skip-toast sur `SessionExpiredError`. Logique vérifiée à la main + revue ; couvrir en E2E lors du sprint suivant.
- **[L — LOW]** Multi-langue : `_detect_esg_request` ne couvre pas l'anglais (« I want to launch my ESG evaluation »). Hors scope (FR-only par CLAUDE.md), à reconsidérer si une UI EN est priorisée.

## Deferred from: 019-guided-tour-post-fix-debts validation live (2026-04-15)

- **BUG-1 resolu partiellement** — mon fix du prompt (commit 8c71101) permet
  desormais au LLM d'appeler `trigger_guided_tour(tour_id, context={sector, total_tco2, top_category, top_category_pct})`
  avec les 4 bonnes cles (validation live `tool_call_logs` 2026-04-15 02:14:51+).
  MAIS les valeurs numeriques restent `None` (seul `sector` est resolu depuis
  le profil entreprise). Cause : le chat_node ne recoit ni les stats carbone
  ni le resume du bilan dans son prompt, et le router garde le message
  « Montre-moi mes resultats carbone » dans chat_node au lieu de transitionner
  vers carbon_node (qui lui aurait acces a `get_carbon_summary`). Consequence :
  popovers affichent « Votre empreinte est de  tCO2e. [...] represente % du total. »
  (placeholders vides au lieu de valeurs). Fix avale : soit router vers
  carbon_node sur intent « resultats/bilan/empreinte + page /carbon/results »,
  soit injecter un resume carbon dans le system_prompt chat_node quand
  `current_page == '/carbon/results'`. Deterministique, hors scope du fix
  surface du 2026-04-15.

## Resolved (2026-04-15)

### [BUG] feature 019 — event SSE `guided_tour` silencieusement drop par la whitelist de `send_message`

- **Feature d'origine** : 019-floating-copilot-guided-nav (story 6.1)
- **Revele par** : test live `agent-browser --headed` sur `fatou1@gmail.com` page `/carbon/results`, message « Montre-moi mes resultats carbone ». Backend logue `trigger_guided_tour` avec `status=success` dans `tool_call_logs`, mais driver.js ne lance jamais le parcours cote front : `document.querySelector('.driver-popover')` retourne null, UI figee, aucun message systeme. Instrumentation temporaire (`[GT-TRACE]`) dans `handleGuidedTourEvent` et `startTour` revele que le handler n'est JAMAIS appele — le SSE `guided_tour` n'arrive pas au frontend.
- **Cause racine** : la fonction `generate_sse` (closure interne a `send_message` dans `backend/app/api/chat.py`) filtre les events yielded par `stream_graph_events` via un elif explicite. La whitelist contenait `token`, `tool_call_start/end/error`, `interactive_question`, `interactive_question_resolved`, `error` — mais **PAS `guided_tour`**. Consequence : `stream_graph_events` extrait correctement le marker `<!--SSE:{"__sse_guided_tour__":true,...}-->` du `on_tool_end` et yield `{type: "guided_tour", tour_id, context}` (lignes 270-276 apres story 6.1), mais `generate_sse` (ligne 865) ne le forward pas. Event silencieusement drop. Aucun log, aucune erreur — bug tres difficile a diagnostiquer sans instrumentation ciblee.
- **Correctif** (1 ligne) : ajouter `"guided_tour"` dans la whitelist du elif a `backend/app/api/chat.py:865-868`.
- **Validation live** : reproduction initiale + fix confirme via `agent-browser --headed` sur `fatou1@gmail.com` page `/carbon/results`. Apres fix : `popoverCount=1`, `overlayCount=1`, `highlightedSelector="carbon-donut-chart"`, popover « Etape 1/3 — Repartition de vos emissions » visible.
- **Tests** : nouveau test anti-regression `backend/tests/test_api/test_sse_event_whitelist.py` qui verrouille la whitelist par inspection de source (tous les types emis par `stream_graph_events` doivent etre presents dans `send_message`). Bug de cette classe difficile a attraper en integration (filtrage muet), test statique defensif plus pragmatique. 15 tests existants (`test_sse_tool_events.py`, `test_guided_tour_toolnode_registration.py`) toujours verts.
- **Dettes secondaires** (hors scope) :
  - `context` passe a `null` cote backend dans l'appel LLM actuel → placeholders `{{total_tco2}}`, `{{top_category}}`, `{{top_category_pct}}` non interpoles dans le popover (« Votre empreinte est de tCO2e »). A corriger dans une story dediee (enrichir le prompt `GUIDED_TOUR_INSTRUCTION` pour que le LLM remplisse le dict `context` avec les valeurs de la page courante).
  - `profile_update` et `profile_completion` sont emis par `stream_graph_events` (lignes 258-262) mais eux aussi absents de la whitelist `generate_sse`. Meme classe de bug, non investiguee : si la fonctionnalite marche aujourd'hui c'est via une autre voie ; sinon, verifier si elle est cassee depuis la migration tool-calling (feature 012).
- **Note sur le bug precedent (LLM hallucine "outil indisponible")** : deja resolu ce matin (cf. plus bas dans cette section « Resolved 2026-04-15 »). Le present bug etait la *couche suivante* cachee sous celui-la : backend-cote-tool OK → backend-cote-endpoint drop.

### [BUG] feature 019 — LLM hallucine « trigger_guided_tour temporairement inaccessible »

- **Feature d'origine** : 019-floating-copilot-guided-nav (stories 6.1 et suivantes)
- **Revele par** : test live `agent-browser --headed` sur compte `fatou1@gmail.com`, message « Montre-moi mes resultats carbone sur l'ecran ». Le LLM repondait « Le guidage visuel interactif n'est pas disponible pour le moment — l'outil de navigation vers la page /carbon/results n'est pas accessible dans cette session ». Cette phrase n'existe nulle part dans le code : hallucination pure.
- **Cause racine** (trouvee via logs instrumentes dans chat_node) :
  1. `GUIDED_TOUR_TOOLS` etait bien binde cote LLM dans 6 noeuds (chat, esg_scoring, carbon, financing, credit, action_plan) via `llm.bind_tools(...)`.
  2. MAIS `GUIDED_TOUR_TOOLS` etait **absent de la liste `tools=` passee a `create_tool_loop(...)` dans `app/graph/graph.py`** (lignes 132-138). Les ToolNodes ne contenaient pas le tool.
  3. Consequence : le LLM emettait `tool_calls=['trigger_guided_tour']` au 1er tour, mais le ToolNode ne trouvait pas le tool a executer et ne produisait pas de ToolMessage exploitable. Au 2e tour LLM, le modele generait un texte hallucinant l'indisponibilite de l'outil — aggrave par l'historique polue (les conversations precedentes contenaient deja des hallucinations similaires, perpetuees via `context_memory` et les summaries).
- **Correctif** (3 volets, diff minimal) :
  1. **Fix principal** [backend/app/graph/graph.py] — ajouter `GUIDED_TOUR_TOOLS` dans les 6 appels `create_tool_loop` des noeuds qui le bindent cote LLM (exclusion : `application_node` qui ne le bind pas). Import du module ajoute dans la section des imports paresseux.
  2. **Defense en profondeur contre la recidive** [backend/app/chains/summarization.py] — renforcement de `SUMMARY_PROMPT` : interdiction explicite de persister dans les resumes des formulations comme « outil indisponible », « hors service », « pas accessible dans cette session ». Les hallucinations qui passent le tool-calling ne doivent plus contaminer les sessions futures.
  3. **Nettoyage des summaries legacy** [backend/app/prompts/system.py `_format_memory_section`] — ajout d'un paragraphe neutralisant : toute affirmation d'indisponibilite d'outil dans les resumes injectes via `context_memory` est declaree INVALIDE et a IGNORER (protege contre les summaries deja en base chez d'autres users, non nettoyes).
- **Nettoyage BDD** : 9 `conversations.summary` contamines (tous users confondus) remis a NULL via script one-shot (seront regeneres au prochain summarization avec le nouveau prompt durci).
- **Tests** : 8 tests anti-regression ajoutes dans `tests/test_graph/test_guided_tour_toolnode_registration.py` qui verrouillent la coherence `bind_tools` ↔ `ToolNode` pour `trigger_guided_tour` dans les 7 modules (6 avec + 1 sans). 241 tests suites (prompts + graph + chat) verts, zero regression.
- **Validation live** : reproduction initiale + fix confirme via `agent-browser --headed` sur `fatou1@gmail.com` page /carbon/results. Avant : assistant generait le texte hallucine. Apres : `tool_call_logs` contient `trigger_guided_tour` avec `status=success` et la reponse assistant est vide (conforme a `GUIDED_TOUR_INSTRUCTION` « pas de texte apres l'appel »).
- **Note sur le declenchement front du tour** : l'event SSE `guided_tour` est emis correctement, mais le driver.js n'a pas lance visuellement le parcours lors du test (aucun `.driver-popover` dans le DOM). Probablement lie au guard `currentInteractiveQuestion` residuel dans `useChat.ts` (cf. dette 6-4 : edge case orphan-state). Symptome secondaire, hors scope du bug LLM. A investiguer dans une story de suivi.
- **Commit** : voir `git log` sur la branche `main` (date 2026-04-15).

## Resolved (2026-04-14)

### [BUG] carbon_node — lecture de bilan carbone retourne "Aucun bilan" alors qu'une entree existe

- **Feature d'origine** : 007-carbon-footprint-calculator
- **Revele par** : test live feature 019 (parcours Fatou) avec `agent-browser` sur compte `fatou1@gmail.com`
- **Cause racine** : `carbon_node` et le tool `get_carbon_summary` n'utilisaient que `get_resumable_assessment` (filtre `status = in_progress`). Lorsque l'utilisateur n'a que des bilans `completed`, le fallback retournait None et le LLM pensait qu'aucun bilan n'existait. Dans le meme temps, `create_carbon_assessment` detectait bien le bilan existant (contrainte d'unicite user_id + year), d'ou la reponse contradictoire.
- **Correctif** :
  1. Ajout de `get_latest_assessment(db, user_id)` dans `backend/app/modules/carbon/service.py` — retourne le bilan le plus recent quel que soit le statut.
  2. Mise a jour de `get_carbon_summary` dans `backend/app/graph/tools/carbon_tools.py` — fallback sur `get_latest_assessment` quand aucun bilan `in_progress`.
  3. Mise a jour de `carbon_node` dans `backend/app/graph/nodes.py` — charge egalement les bilans `completed` dans l'etat injecte au prompt (annee, statut, assessment_id reels) + nouvel en-tete de contexte "BILAN CARBONE EXISTANT (finalise, disponible en consultation)".
- **Tests** : 4 tests ajoutes (3 service + 1 tool). 1072 tests backend verts, zero regression.
- **Commit** : voir `git log` sur la branche `main` (date 2026-04-14).
- **Note sur la journalisation `tool_call_logs`** : symptome non lie au bug. Les tools metier (carbon, esg, etc.) n'instrumentent pas actuellement `log_tool_call` ; seuls `interactive_tools` et `guided_tour_tools` le font. Dette d'observabilite a traiter separement.

## Deferred from: code review of story-8-1 (2026-04-14)

- Imports `../../../app/types/carbon` sans path alias dans les fixtures E2E — a refactorer globalement avec un alias Vitest/Playwright (hors scope 8.1). [frontend/tests/e2e/fixtures/mock-backend.ts:666]
- `testMatch` ambiguite : un `.test.ts` sous `tests/e2e/` serait silencieusement skip par Vitest ET ignore par Playwright (qui matche `.spec.ts`). Documenter la convention dans `tests/e2e/README.md`. [frontend/vitest.config.ts:66 ; frontend/playwright.config.ts:97]
- Pas de header `X-Accel-Buffering: no` sur la reponse SSE fabriquee — inutile tant que la reponse est single-shot, a ajouter si un futur patch active le vrai streaming chunke. [frontend/tests/e2e/fixtures/sse-stream.ts:581]
- `route.continue()` appele sur les methodes non-POST dans plusieurs endpoints mockes (`:772, 1007, 1028, 1065`) — en environnement e2e full-mock, ceci laisse passer les requetes vers un backend qui n'existe pas. Le catch-all 404 couvre deja le cas ; a nettoyer avec une passe de harmonisation. [frontend/tests/e2e/fixtures/mock-backend.ts:772]

## Deferred from: code review of story-7-2 (2026-04-14)

- `refreshPromise` module-level dans `useAuth.ts` risque de partage entre requetes SSR — composable client-only en pratique mais pas de guard `import.meta.client` explicite. [frontend/app/composables/useAuth.ts:49]
- `useCarbon.fetchBenchmark` et `useEsg.fetchBenchmark` avalent toutes les erreurs non-session-expirée et retournent `null` — UI ne peut pas distinguer 404 vs 500. Comportement pre-existant, a traiter globalement. [frontend/app/composables/useCarbon.ts:93-98, useEsg.ts:90-96]
- Tests manquants : cycle 401 sur `apiFetchBlob` (fiche de preparation PDF), `/auth/me` (fetchUser), echec d'import dynamique dans `handleAuthFailure`. Scenarios principaux couverts par les 19 tests existants. [frontend/tests/composables/useAuth.refresh.test.ts]
- Composables non migres vers `apiFetch` (`useApplications`, `useCreditScore`, `useActionPlan`, `useReports`, `useDocuments`, `useCompanyProfile`, `useChat`) ne beneficient pas de l'intercepteur 401. Dette technique deja documentee dans la story, future story `X-Y-migration-composables-vers-apifetch` proposee.

## Deferred from: code review of story-3-1 (2026-04-13)

- Pas d'annotation reducer pour `current_page` dans ConversationState — le champ pourrait ne pas se propager si un noeud LangGraph retourne un state partiel. Risque latent pour Story 3.2 quand les noeuds liront activement cette valeur. [backend/app/graph/state.py:36]
- `invoke_graph` n'accepte pas `current_page` — inconsistance latente avec `stream_graph_events`. Verifier si cette fonction est encore utilisee et la mettre a jour ou la supprimer. [backend/app/api/chat.py:56]

## Deferred from: code review of story-3-2 (2026-04-13)

- Checkpointer LangGraph et `current_page` — aucun nœud ne retourne `current_page` dans son `return {}`, risque théorique d'écrasement par le checkpoint. Risque quasi nul car toujours re-injecté dans `initial_state` et read-only. [backend/app/graph/nodes.py]
- `send_message_json` passe toujours `current_page=None` — endpoint de compatibilité, pas utilisé par le frontend actuel. Ajouter le support ou documenter la limitation. [backend/app/api/chat.py:938]
- Routes dynamiques (`/financing/123`) tombent sur la branche générique du prompt — nécessite un design de prefix matching pour extraire les descriptions contextuelles des pages avec paramètres. [backend/app/prompts/system.py:138]
- Valeur initiale `"/"` dans `uiStore.currentPage` envoyée au backend comme page inconnue — initialiser à `null` ou ajouter `"/"` à `PAGE_DESCRIPTIONS`. [frontend/app/stores/ui.ts:17]
- Tests ne couvrent pas le chemin complet nœud → prompt pour 5 des 6 spécialistes (carbon, financing, application, credit, action_plan) — couverture indirecte via tests prompts directs. [backend/tests/test_graph/test_current_page.py]

## Deferred from: code review of story-4-1 (2026-04-13)

- Pas de `timeout` sur `requestIdleCallback` dans `prefetchDriverJs()` — sous charge CPU le prefetch peut ne jamais se declencher avant le premier guidage. Le fallback `loadDriver()` gere ce cas mais avec latence supplementaire. [frontend/app/composables/useDriverLoader.ts:25]
- Couleurs hexadecimales hardcodees en mode clair dans les overrides Driver.js CSS — incohérence avec le dark mode qui utilise des variables CSS du design system. Pattern pre-existant dans le projet. [frontend/app/assets/css/main.css]

## Deferred from: code review of story-4-2 (2026-04-13)

- `countdown` sans borne min/max — accepte 0, négatif, NaN. Ajouter validation dans le moteur `useGuidedTour` (Story 5.1). [frontend/app/types/guided-tour.ts]
- `lib/` pas dans les dirs auto-import Nuxt — import manuel requis. Choix d'architecture, documenter si nécessaire. [frontend/nuxt.config.ts]
- `tsconfig.json` étend `.nuxt/tsconfig.json` — tests TypeScript cassent avant `nuxt prepare` en clone frais. Setup pré-existant. [frontend/tsconfig.json]
- `route` field non contraint dans `GuidedTourStep` — un typo de route échoue silencieusement au runtime. Validation croisée à ajouter dans Story 5.1. [frontend/app/types/guided-tour.ts]
- `TourContext = Record<string, unknown>` sans contrat entre les placeholders attendus et le contexte fourni — risque d'affichage de `{{variable}}` brut si clé manquante. Design d'interpolation à prévoir dans Story 5.1. [frontend/app/types/guided-tour.ts]

## Deferred from: code review of story-4-3 (2026-04-13)

- Route mismatch `show_esg_results` : registre declare `route: '/esg'` mais `esg-score-circle` est sur `/esg/results`. Corriger dans `registry.ts:22` la route en `/esg/results`. [frontend/app/lib/guided-tours/registry.ts:22]
- 8 elements `data-guide-target` dans des blocs `v-if` (esg-strengths-badges, esg-recommendations, carbon-donut-chart, carbon-benchmark, carbon-reduction-plan, action-plan-timeline, credit-score-gauge, dashboard cards pendant loading). Le moteur `useGuidedTour` (Story 5.1) devra gerer les elements absents du DOM via skip, attente ou fallback. [multiple pages]

## Deferred from: code review of story-5-1 (2026-04-13)

- Delai transition `complete → idle` hardcode a 1000ms — AC5 mentionne un delai configurable. Exposer une constante ou un parametre optionnel dans `startTour`. [frontend/app/composables/useGuidedTour.ts:162-166]
- Element DOM peut etre supprime entre le retour de `waitForElement` et l'appel `highlight` — fenetre de timing tres courte. Limitation architecturale, impact negligeable en conditions normales. [frontend/app/composables/useGuidedTour.ts:112-124]

## Deferred from: code review of story-6-1 (2026-04-13)

- Pas d'allowlist serveur pour `tour_id` — AC4 delegue explicitement la validation au registre frontend (par conception du spec). Hardening defense-en-profondeur possible plus tard. [backend/app/graph/tools/guided_tour_tools.py]
- `context` dict sans limite de taille/profondeur — un LLM pourrait envoyer un context enorme. Pre-existant aux autres tools qui acceptent des dicts LLM-controlled. [backend/app/graph/tools/guided_tour_tools.py:24]
- Marker SSE split entre chunks de streaming — parser actuel dans `stream_graph_events` suppose un `on_tool_end` avec output complet. Limitation partagee avec les markers `__sse_profile__` et `__sse_interactive_question__`. [backend/app/api/chat.py:212-239]
- Plusieurs markers SSE dans un seul output ne sont pas tous parses — `index()` ne trouve que le premier `-->`, les markers suivants sont ignores. Pre-existant. [backend/app/api/chat.py:213-217]

## Deferred from: code review of story-6-2 (2026-04-13)

- Couplage STYLE_INSTRUCTION / GUIDED_TOUR_INSTRUCTION : meme branche conditionnelle `_has_minimum_profile` dans `build_system_prompt`. Un futur changement de seuil du style concis deplacera silencieusement le guidage. Extraire un helper dedie ou ajouter un test d'independance. [backend/app/prompts/system.py:211-217]
- Aucune assertion positionnelle sur l'ordre `WIDGET_INSTRUCTION` → `GUIDED_TOUR_INSTRUCTION` dans les 5 prompts specialises — les tests verifient la presence (`in`) mais pas l'ordre. Un swap futur ne declencherait aucune erreur. [backend/tests/test_prompts/test_guided_tour_instruction.py]
- Chemins frontend listes dans la docstring `GUIDED_TOUR_INSTRUCTION` (`/esg/results`, `/action-plan`, etc.) non epingles contre le registre Nuxt reel (`frontend/app/lib/guided-tours/registry.ts`). Divergence silencieuse possible (cosmetique, le tool_call utilise le `tour_id` qui lui est valide). Test cross-stack a creer. [backend/app/prompts/guided_tour.py:12-17]

## Deferred from: code review of story-6-3 (2026-04-14)

- T-AC2 / T-AC6 court-circuitent `useGuidedTour` via mock statique — le test ne valide pas que `handleGuidedTourEvent` emprunte le code path runtime reel. Couverture d'integration plus realiste a prevoir en epic 8 (e2e). [frontend/tests/composables/useChat.guided-tour-consent.test.ts]
- Plancher `count("GUIDED_TOUR_TOOLS") >= 12` dans T11 conflate shape et correctness. Un refactor legitime (liste partagee, spread) casse le test. Herite 6.2. [backend/tests/test_prompts/test_guided_tour_instruction.py]
- T-AC3 (refus consent) ne prouve pas le respect du refus — test passe car backend n'emet pas `guided_tour`, pas parce que `no` est honore. Si le backend emettait a tort un guided_tour apres refus, le frontend n'a pas de guard `yes`-only. Test d'alignement backend/frontend a ajouter (hors scope prompt-only). [frontend/tests/composables/useChat.guided-tour-consent.test.ts]
- `GUIDED_TOUR_INSTRUCTION` injecte inconditionnellement (y compris pour sessions anonymes / sans profil) — bloat tokens par requete. Decision architecturale a valider globalement ou gated. [backend/app/prompts/system.py:213-220]
- Aucun test cross-file alignant les 6 `tour_id` entre `guided_tour.py` (prompt), `registry.ts` (frontend), `guided_tour_tools.py` (backend tool enum). Renommage silencieux possible. Test de contrat pour story 7.x ou 8.x. [multi-file]
- Validation serveur `tour_id` (tool-level) et validation `context` dans `handleGuidedTourEvent` — hors scope story 6.3 (story 6.1 pour le tool, `useChat.ts` NE PAS TOUCHER pour le handler). [backend/app/graph/tools/guided_tour_tools.py, frontend/app/composables/useChat.ts:682-700]

## Deferred from: code review of story 6-4-frequence-adaptative-des-propositions-de-guidage (2026-04-14)

- Decroissance / cap global sur `acceptance_count` et `refusal_count` — actuellement saturation indefinie apres ~5 acceptations (plancher 3s permanent). Decision produit a arbitrer : cap dur vs decay temporel. [frontend/app/composables/useGuidedTour.ts]
- `send_message_json` (endpoint fallback JSON) ne transmet pas `guidance_stats` au graphe — volontaire par spec ; acceptable car le fallback est hors-parcours principal. Extension Chrome / integrations externes (story 8.x) devront explicitement opter pour la modulation. [backend/app/api/chat.py:~976]
- Perte de precision au-dela de `Number.MAX_SAFE_INTEGER` dans `loadGuidanceStats` — limite JS native ; mitigable par plafond serveur (cf. patch P8 meme review). [frontend/app/composables/useGuidedTour.ts]
- Race theorique entre `currentInteractiveQuestion` lu avant `await import(...)` et evenement SSE `interactive_question_resolved` concurrent — fenetre temporelle minime, impact pratique negligeable. [frontend/app/composables/useChat.ts]
- SSE `guided_tour` arrivant pendant une question interactive `pending` laisse un etat orphelin (refus deja comptabilise sur la question precedente, acceptance non comptabilisee sur le tour). Path early-return existant avec message systeme ; edge rare. [frontend/app/composables/useChat.ts:~730-733]
- `test_guided_tour_instruction_unchanged` verifie seulement une plage de longueur (3500-6000 chars) — ne constitue pas un vrai verrou anti-regression semantique. A renforcer avec snapshot au prochain refactor 6.2. [backend/tests/test_prompts/test_guided_tour_adaptive_frequency.py:~894-903]
- `try { ... } catch {}` silencieux autour de l'import dynamique + increment dans `useChat.ts` — swallow des erreurs non-critiques mais sans observabilite. A envisager dans story tooling/observability. [frontend/app/composables/useChat.ts:464-466]
- Migration de la cle localStorage `esg_mefali_guidance_stats` vers un scope par utilisateur (prefixe `user_id:` ou deplacement backend `user_guidance_stats`). Status quo accepte pour story 6.4. A revisiter au demarrage du module 7 (multi-utilisateurs admin/collaborateur/lecteur). Ajouter un TODO inline en meme temps que les patchs 6.4. [frontend/app/composables/useGuidedTour.ts]

## Deferred from: code review of story 7-1-gestion-des-elements-dom-absents-et-timeout-de-chargement (2026-04-14)

- `Date.now()` non-monotone dans `waitForElementExtended` — une bascule NTP/DST peut fausser le calcul d'elapsedMs. Preferer `performance.now()` pour les mesures de duree. [frontend/app/composables/useGuidedTour.ts:179,183,189]
- `setTimeout(..., 500)` dans `interruptTour`/`cancelTour` (transition `interrupted`→`idle`) jamais annule — leak mineur de timers sur cancels repetes. [frontend/app/composables/useGuidedTour.ts:250-252,662-666]
- `cancelled` non reinitialise sur le chemin de succes de `startTour` — etat residuel possible entre deux parcours consecutifs sans cancel entre les deux. [frontend/app/composables/useGuidedTour.ts:278]
- `cancelTour` re-entre pendant la transition `interrupted`→`idle` cree des timeouts dupliques — ajouter `'interrupted'` a la garde de retour anticipe. [frontend/app/composables/useGuidedTour.ts:~635]
- Cleanup du catch global a placer dans un `finally` au lieu d'apres le catch — robustesse face a un throw interne au catch (ex. import dynamique qui throw lui-meme). [frontend/app/composables/useGuidedTour.ts:~590-627]
- `addSystemMessage` peut etre silencieusement drop si aucune conversation active cote `useChat` — limitation pre-existante ; AC4 suppose que l'utilisateur voit toujours le message empathique. A renforcer avec un fallback toast si pas de conversation active. [frontend/app/composables/useGuidedTour.ts:598-600, frontend/app/composables/useChat.ts:739-744]
- Strings FR hardcodees ("Je n'ai pas pu pointer cet element...", "La page met trop de temps a charger...", "Le guidage a rencontre un probleme...") non extraites en MAP de constantes module-level — conforme aux conventions actuelles du projet mais nuit a une future i18n ou a un edit global. [frontend/app/composables/useGuidedTour.ts:424,504,~418,~509,~600]

## Deferred from: code review of story 7-3-resilience-sse-et-indicateur-de-reconnexion (2026-04-14)

- Classification HTTP par substring francais `'erreur lors de'` : tous les throws actuels matchent mais tout nouveau message en englais ou reformule tombe dans `'other'`. Refactor en sentinel `class HttpError extends Error` ou en drapeau typed recommande a terme. [frontend/app/composables/useChat.ts:70]
- `throw new Error('Réponse sans body...')` classifie en `'other'` et pollue `error.value` meme pendant un parcours guide. Scenario rare (200 OK sans body). AC3 autorise explicitement ce comportement pour non-network, mais incoherent avec l'intention de masquer les erreurs reseau pendant un tour. [frontend/app/composables/useChat.ts:264, 659]
- `DOMException` non-Abort mid-stream (`NetworkError`, `InvalidStateError`) classifie en `'other'`. Readers modernes throw `TypeError` donc impact < 1 % du trafic (Safari legacy). Documente en spec Dev Notes. [frontend/app/composables/useChat.ts:62-72]
- `useUiStore()` appele dans le catch block — risque Pinia-not-ready dans contextes edge. Impossible dans flow UI reel. Refactor optionnel : hoister en haut de `useChat()`. [frontend/app/composables/useChat.ts:504, 776]
- Test invariant AC8 fragile au cwd : `path.resolve(process.cwd(), 'app/composables/useGuidedTour.ts')` fonctionne si vitest lance depuis `frontend/`. Robustesse : `new URL(..., import.meta.url)`. [frontend/tests/composables/useChat.connection.test.ts:831-838]
- bfcache : listeners survivent mais `isConnected` stale au `pageshow`. Edge case rare (page cachee offline puis restauree online sans event). Handler `pageshow` a ajouter a terme. [frontend/app/composables/useChat.ts:77-85]
- Fetches concurrents (`sendMessage` + `submitInteractiveAnswer`) : si l'un succeed et flip a true puis l'autre fail en network, la bascule a false ecrase le signal de reprise. Peu probable dans l'UX normale (serialisation par `abortController`). [frontend/app/composables/useChat.ts:289, 683, 503, 775]

## Deferred from: code review of 8-3-tests-e2e-parcours-aminata (2026-04-15)

- Semantique exacte de `agent-browser close` (sans `--session`) : bloque sur la documentation upstream de la CLI agent-browser 0.8.5 ; le `cleanup()` actuel appelle `agent-browser --headed close` sans session nommee et swallow la sortie. A tracker via issue CLI si comportement imprevu observe [frontend/tests/e2e-live/8-3-parcours-aminata.sh:1175, 1264].
- Driver.js popover i18n : textes hardcoded FR + fallback EN (Suivant/Next, Terminer/Done/Fermer). Aucune couverture pour ES/DE/etc. Hors scope 8.3 ; a reprendre dans une story dediee si Driver.js expose des builds i18n ou si on force la locale applicative [frontend/tests/e2e-live/8-3-parcours-aminata.sh:1328-1358].
- Flag `--session aminata-e2e` absent des invocations `agent-browser` (la spec AC3–AC8 l'impose, le dev utilise la var d'env `AGENT_BROWSER_SESSION` a la place). Defere le 2026-04-16 par Angenor : « la simulation marche, on laisse comme ca pour le moment ». A reprendre si on observe des collisions de session ou si 8.4/8.5/8.6 introduisent du parallelisme [frontend/tests/e2e-live/8-3-parcours-aminata.sh + lib/env.sh:50].
