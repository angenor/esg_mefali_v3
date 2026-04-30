---
title: 'Fix routage chat → esg_scoring_node + invocation effective du scoring'
type: 'bugfix'
created: '2026-04-30'
status: 'done'
baseline_commit: '9087e98'
context:
  - '{project-root}/CLAUDE.md'
  - '{project-root}/_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/REPORT.md'
  - '{project-root}/_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/PROMPT-BMAD-FIX-ESG-ROUTING.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** En production (preuve E2E live 2026-04-30, REPORT.md « Extension »), 6 confirmations widget « créer l'évaluation / finaliser / voir résultats » ont été acceptées par l'utilisateur sans qu'aucune row ne soit créée dans `esg_assessments`. Cause racine : le `chat_node` embarque `INTERACTIVE_TOOLS` mais pas `create_esg_assessment` ; son LLM pose donc des widgets ESG en boucle alors que `_detect_esg_request()` (keywords router) ne reconnaît pas « lance mon évaluation / finalise / créer l'évaluation » et ne bascule jamais `active_module` vers `esg_scoring`.

**Approach:** (1) Élargir le pattern keywords de `_detect_esg_request()` pour couvrir les verbes d'intention courants. (2) Interdire au `chat_node` de poser des widgets de confirmation à thème ESG via une consigne explicite dans son prompt + filtrage conditionnel du tool `ask_interactive_question` quand l'intention ESG est détectée. (3) Câbler le bouton « Nouvelle évaluation » de `pages/esg/index.vue` sur le endpoint existant `POST /api/esg/assessments` avant d'ouvrir le widget chat. (4) Ajouter tests TDD couvrant les 5 AC.

## Boundaries & Constraints

**Always:**
- Préserver le contrat `ConversationState` (champs `active_module`, `active_module_data`).
- Conserver la sécurité du routeur : défaut « rester dans le module » en cas d'échec LLM (cf. `_is_topic_continuation`).
- Coverage ≥ 80% sur le code modifié dans `backend/app/graph/`.
- Toutes les 935+ tests existants restent verts (zéro skip, zéro régression).
- Dark mode complet sur toute modif UI ; ici uniquement le handler du bouton change.

**Ask First:**
- Si la résolution exige de modifier la migration `018_create_interactive_questions.py` ou le schéma `interactive_questions` → HALT.
- Si un test existant doit être supprimé (pas seulement modifié) → HALT.
- Si la fix nécessite un nouveau tool LangChain (au-delà des 32 existants) → HALT.

**Never:**
- Pas de nouveau node LangGraph.
- Pas de tool `start_esg_assessment` séparé (réutiliser `create_esg_assessment` existant).
- Pas de modification du graphe `graph.py` (priorité de routage déjà correcte : ESG > carbon > … > chat).
- Pas de breaking change sur l'API SSE (events `interactive_question`, `tool_call_*` inchangés).
- Pas d'ajout de logique business hors `backend/app/graph/`, `backend/app/modules/esg/`, et `frontend/app/pages/esg/index.vue`.

## I/O & Edge-Case Matrix

| Scénario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Intention explicite | `active_module=null`, message « lance mon évaluation ESG » | router pose `_route_esg=True` ; tour suivant `active_module='esg_scoring'` | N/A |
| Intention « finalise » | `active_module=null`, message « finalise mon scoring » | route → esg_scoring | N/A |
| Anti-boucle widget | `active_module=chat`, ≥ 1 widget ESG `state=answered` dans la même conversation | router force la transition vers esg_scoring au tour suivant | si requête DB échoue, log warning et fallback heuristique keywords |
| chat_node prompt | LLM tenté de poser widget « voulez-vous créer l'évaluation ? » | bloqué par instruction prompt + filtre tool ; LLM répond en texte invitant à dire « lance mon évaluation ESG » | N/A |
| Bouton UI | clic « Nouvelle évaluation » sur `/esg` | `POST /api/esg/assessments` → row draft créée → ouverture chat avec `assessment_id` | toast erreur si 4xx/5xx, chat ne s'ouvre pas |
| Hypothèses prudentes | clic widget « hypothèses prudentes » dans esg_scoring_node | `batch_save_esg_criteria` appelé (30 critères, scores 4-5/10) puis `finalize_esg_assessment` | retry 1× sur tool error (déjà en place) |

</frozen-after-approval>

## Code Map

- `backend/app/graph/nodes.py:343-540` — `router_node` + `_detect_esg_request()` + `_is_topic_continuation()` : élargir keywords + ajouter détection « widget ESG déjà répondu ».
- `backend/app/graph/nodes.py:1190-1290` — `chat_node` : ajouter filtre conditionnel sur `ask_interactive_question` quand intention ESG détectée ; renforcer prompt.
- `backend/app/graph/prompts/chat.py` (ou équivalent — chercher la chaîne SYSTEM_PROMPT du chat_node) — ajouter section « ANTI-BOUCLE ESG ».
- `backend/app/graph/nodes.py:573-720` — `esg_scoring_node` (vérification seulement) : confirmer `create_esg_assessment` au démarrage si `assessment_id` absent.
- `backend/app/graph/tools/esg_tools.py` — `batch_save_esg_criteria` (vérification seulement, pas de modif).
- `backend/app/modules/esg/router.py:27` — `POST /api/esg/assessments` (existant, vérifier signature body optionnel).
- `frontend/app/pages/esg/index.vue:67` — handler bouton « Nouvelle évaluation » : appeler API avant d'ouvrir le widget chat.
- `frontend/app/composables/useESG.ts` (créer si absent) — méthode `createDraftAssessment()`.
- `backend/tests/test_esg_routing.py` (NOUVEAU) — tests intégration AC1-AC4.
- `backend/tests/test_router_node.py` (NOUVEAU) — test classification keywords ESG (8 phrases).

## Tasks & Acceptance

**Execution:**
- [x] `backend/tests/test_router_node.py` — créer tests RED : 8 phrases d'intention ESG (« lance mon évaluation ESG », « démarre mon scoring ESG », « commence mon évaluation », « calcule mes scores ESG », « finalise mon évaluation », « crée mon évaluation ESG », « voir mon score ESG », « évalue ma conformité ESG ») doivent toutes activer `_detect_esg_request()=True` ou `_route_esg=True`.
- [x] `backend/tests/test_esg_routing.py` — créer 4 tests intégration RED couvrant AC1-AC4 (transition module, création assessment, hypothèses prudentes, anti-boucle widget).
- [x] `backend/app/graph/nodes.py` — élargir `_detect_esg_request()` avec patterns regex insensibles à la casse/accents : `\b(lanc|démarr|demarr|commenc|cré|finalis|évalu|evalu|calcul)\w*\b.{0,40}\b(esg|évaluation|evaluation|scoring|score|conformité|conformite|critère|critere)\b` (et l'ordre inverse). Faire passer les tests router_node.
- [x] `backend/app/graph/nodes.py` — dans `router_node`, après détection keywords, requêter table `interactive_questions` : si `state=answered` ET `module='chat'` ET texte question contient pattern ESG → forcer `_route_esg=True` (rationale AC4).
- [x] `backend/app/graph/prompts/chat.py` (ou prompt inline du chat_node) — ajouter section « ANTI-BOUCLE ESG » : LLM ne doit JAMAIS poser de widget interactif de type « voulez-vous créer/démarrer/finaliser une évaluation ESG ». Reformuler en texte libre : « Pour démarrer ton évaluation ESG, dis-moi simplement : *lance mon évaluation ESG* ».
- [x] `backend/app/graph/nodes.py` (chat_node) — filtrer dynamiquement `ask_interactive_question` du toolkit si dernier message utilisateur matche `_detect_esg_request()` (defense-in-depth).
- [x] `frontend/app/pages/esg/index.vue` — handler bouton « Nouvelle évaluation » : `await $fetch('/api/esg/assessments', { method: 'POST', body: {} })` puis ouverture chat avec `assessment_id` injecté. Toast erreur sur échec.
- [x] `frontend/app/composables/useESG.ts` — exposer `createDraftAssessment(): Promise<Assessment>` (créer le composable si absent).
- [x] `backend/tests/test_esg_routing.py` — passer les 4 tests intégration au GREEN.
- [x] `pytest --cov=app/graph` — vérifier coverage ≥ 80% sur app/graph/.

**Acceptance Criteria:**

- **AC1** (transition module) — Given `active_module=null`, when l'utilisateur envoie « je veux faire mon évaluation ESG », then après 1 tour `active_module='esg_scoring'` ET le prochain message assistant est généré par `esg_scoring_node`.
- **AC2** (création effective) — Given confirmation explicite ESG, when l'utilisateur clique « ✅ Oui, créer l'évaluation » sur un widget esg_scoring_node, then une row `esg_assessments` existe en DB liée à la `conversation_id` avec `status` ∈ {`draft`, `in_progress`}.
- **AC3** (hypothèses prudentes) — Given assessment `in_progress`, when clic « ⚡ Hypothèses prudentes », then `batch_save_esg_criteria` invoqué avec 30 critères ET la row passe à `status='completed'` avec `overall_score`/`environment_score`/`social_score`/`governance_score` non-null.
- **AC4** (anti-boucle widget) — Given conversation avec ≥ 1 widget ESG `state=answered` dans `interactive_questions`, when tour suivant traité, then `chat_node` ne pose pas de nouveau widget de confirmation ESG ET `active_module='esg_scoring'` au tour suivant.
- **AC5** (replay E2E live) — Given le scénario v3 du REPORT.md, when on rejoue « lance mon évaluation ESG » → secteur → taille → « hypothèses prudentes » → « finaliser », then `SELECT count(*) FROM esg_assessments WHERE created_at > NOW() - INTERVAL '5 minutes'` retourne ≥ 1 avec 4 scores remplis.

## Spec Change Log

### AC5 replay extension (2026-04-30)

**Bug séparé révélé par le replay E2E live** : `batch_save_esg_criteria` (esg_tools.py:373) plantait avec `TypeError: '_CriterionItem' object is not subscriptable` car la story 10.1 a introduit `args_schema=BatchSaveESGCriteriaArgs` (Pydantic strict) qui convertit l'input en `_CriterionItem` BaseModel, mais le code accédait dict-style. **Patch appliqué dans le même PR** : coercion défensive `c if isinstance(c, dict) else c.model_dump()` (compatible appels Pydantic + dict legacy) + test régression `test_batch_save_esg_criteria_accepts_pydantic_items`. Régression frontend également corrigée durant le replay : `useEsg.ts` manquait la déclaration `const sessionExpired = ref(false)` (ReferenceError SSR sur /esg).

### Iteration 1 review patches (2026-04-30)

**Triggered by review (3 reviewers — Blind Hunter, Edge Case Hunter, Acceptance Auditor).** No `intent_gap` or `bad_spec` — all 8 findings classified as `patch` (code-only fixes), 3 as `defer`, 1 as `reject`. Spec text unchanged ; patches applied to implementation only :

- **A (HIGH)** — Anti-loop borné : `_has_unresolved_esg_widget_signal` filtre désormais les widgets sur `answered_at >= now() - 10min` ET court-circuite si un `esg_assessment` `in_progress` existe déjà dans `state` (évite la sticky redirect permanente).
- **B (HIGH)** — Narrow `except Exception` → `except SQLAlchemyError`, log `error` (les bugs non-DB ne sont plus silencieusement avalés).
- **C (MEDIUM)** — `_WIDGET_ESG_CONSULTATION_PATTERN` exclut les widgets passé/consultation (« déjà créé », « avez-vous fini ») du signal anti-loop.
- **D (MEDIUM)** — `_ESG_NEGATION_PATTERN` early-return False dans `_detect_esg_request` (« ne lance pas… »).
- **E (MEDIUM)** — Frontend : `isCreating` ref synchrone + `:disabled="loading || isCreating"` (anti double-click).
- **F (MEDIUM)** — Frontend : skip toast sur `SessionExpiredError` (auth redirect prend le relais).
- **G (MEDIUM)** — `conversation_id: NotRequired[str]` ajouté à `ConversationState` ; suppression `# type: ignore`.
- **H (MEDIUM)** — Test parametrize étendu avec « lance ESG maintenant » (capture exclusive du nouveau regex).

**Known-bad state avoided :** redirect permanent vers esg_scoring après une seule réponse à un widget ESG ; bugs DB ou code non-SQLAlchemy silencieusement masqués ; fausse positive sur « ne lance pas d'évaluation » ou widgets de consultation.

**KEEP instructions** (à préserver en cas de re-derivation) :
- Le filtrage `ask_interactive_question` doit rester local au `chat_node` (NE PAS modifier `WIDGET_INSTRUCTION` partagé entre 6 modules).
- Le lazy import `from app.core.database import async_session_factory` à l'intérieur du helper est load-bearing pour les tests (patch via `app.core.database.async_session_factory`).
- `_load_resumable_assessment` (esg_scoring_node) gère la reprise du draft créé par le bouton frontend — ne pas dupliquer cette logique.
- Réutilisation du composable `useEsg.createAssessment()` existant (pas de nouveau composable `useESG.ts`).

## Design Notes

**Pourquoi ne pas créer un tool `start_esg_assessment` ?** `create_esg_assessment` (esg_tools.py) couvre déjà ce besoin et est appelé par esg_scoring_node. Ajouter un tool dans chat_node introduirait une duplication et un point de divergence. Solution préférée : router force la transition, esg_scoring_node fait `create_esg_assessment` au démarrage du tour si `active_module_data.assessment_id` est absent.

**Anti-boucle — pourquoi requêter `interactive_questions` dans le router ?** Le router est sans état entre tours hors `ConversationState`. `state=answered` est persisté en DB. Lecture rapide via index `(conversation_id, state, created_at)`. Coût marginal vs garantie d'absence de boucle.

**Pourquoi filtrer `ask_interactive_question` dynamiquement et pas le retirer de chat_node ?** Le tool reste utile pour widgets non-ESG (profilage, choix de module). Filtre conditionnel = principe du moindre changement.

## Verification

**Commands:**
- `cd backend && source venv/bin/activate && pytest tests/test_router_node.py tests/test_esg_routing.py -v` — expected : tous verts.
- `cd backend && source venv/bin/activate && pytest` — expected : 935+ verts, zéro régression.
- `cd backend && source venv/bin/activate && pytest --cov=app/graph --cov-report=term-missing` — expected : ≥ 80% sur app/graph/.
- `cd frontend && npm run build` — expected : build OK, pas d'erreur TS.

**Manual checks:**
- Replay E2E sur `http://localhost:3000/dashboard` avec `moussa1@gmail.com / Moussa2026!` — séquence du REPORT.md section Extension.
- Vérifier en DB : `PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 -c "SELECT id, status, overall_score FROM esg_assessments ORDER BY created_at DESC LIMIT 1;"` retourne row avec scores non-null.

## Suggested Review Order

**Détection d'intention ESG (cœur du fix)**

- Point d'entrée : nouveau garde négation + extension keywords + helper anti-boucle.
  [`nodes.py:299`](../../backend/app/graph/nodes.py#L299)

- Patterns regex étendus (lance/démarre/finalise + ordre inverse, tolérance accents).
  [`nodes.py:103`](../../backend/app/graph/nodes.py#L103)

- Garde négation early-return (« ne lance pas… »).
  [`nodes.py:285`](../../backend/app/graph/nodes.py#L285)

**Anti-boucle widget (signal DB borné)**

- Helper qui interroge `interactive_questions` avec borne 10 min + court-circuit si esg_assessment in_progress.
  [`nodes.py:330`](../../backend/app/graph/nodes.py#L330)

- Patterns création vs consultation pour discriminer les widgets (« créer » vs « avez-vous déjà créé »).
  [`nodes.py:309`](../../backend/app/graph/nodes.py#L309)

- Branchement dans router_node : appel du helper uniquement si active_module ∈ {None, 'chat'} ET pas d'intention détectée.
  [`nodes.py:563`](../../backend/app/graph/nodes.py#L563)

**Defense-in-depth chat_node**

- Filtrage dynamique de `ask_interactive_question` du toolkit + clause prompt « ANTI-BOUCLE ESG » locale au chat_node (sans polluer WIDGET_INSTRUCTION partagé).
  [`nodes.py:1190`](../../backend/app/graph/nodes.py#L1190)

**Contrat d'état**

- `conversation_id: NotRequired[str]` ajouté à ConversationState (typage propre du nouveau `state.get`).
  [`state.py:42`](../../backend/app/graph/state.py#L42)

**Frontend câblage REST**

- Handler `startNewAssessment` : double-click guard (`isCreating`), création draft via API, skip toast sur SessionExpired.
  [`index.vue:18`](../../frontend/app/pages/esg/index.vue#L18)

- Boutons disabled sur `loading || isCreating` pour neutraliser le double-clic.
  [`index.vue:97`](../../frontend/app/pages/esg/index.vue#L97)

- Composable expose `sessionExpired` ref pour discriminer auth-redirect vs vraie erreur.
  [`useEsg.ts:108`](../../frontend/app/composables/useEsg.ts#L108)

**Tests TDD (en dernier)**

- 15 tests router : 8 phrases d'intention, négation, consultation widgets, anti-loop seed.
  [`test_router_node.py`](../../backend/tests/test_router_node.py)

- 4 tests intégration AC1-AC4.
  [`test_esg_routing.py`](../../backend/tests/test_esg_routing.py)
