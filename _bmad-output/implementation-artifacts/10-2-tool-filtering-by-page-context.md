# Story 10.2 : Filtrage des tools par contexte de page (selecteur LangGraph)

Status: done

<!-- Source planning :
  - _bmad-output/planning-artifacts/module-10-tool-use-reliability/story-2-tool-filtering-by-page-context.md
  - _bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md
  Story precedente (intelligence) :
  - _bmad-output/implementation-artifacts/10-1-tool-descriptions-pydantic-strict.md (DONE 2026-04-29)
-->

## Story

En tant que **developpeur backend**,
je veux **filtrer dynamiquement la liste de tools exposes au LLM en fonction de la page courante (et accessoirement des entites actives) avant chaque `bind_tools(...)`**,
afin que **le LLM voie au maximum 10 tools pertinents par tour** (ligne 2 de defense de l'epic M10), reduisant les hallucinations de selection et le cout tokens, sans casser la compatibilite avec les noeuds LangGraph existants ni l'invariant 1 question interactive en attente / conversation (spec 018).

## Contexte — etat reel verifie le 2026-04-29

Audit du graphe et des points d'entree realise avant redaction. Plusieurs hypotheses du planning ne collent **pas** au code reel — le dev DOIT lire ce contexte avant de coder.

### 1. La page courante existe deja sous le nom `current_page`

Le planning parle de `page_context: str | None` ; le codebase utilise deja **`current_page: str | None`** :

- `ConversationState.current_page` — `backend/app/graph/state.py:36`.
- Endpoint `POST /api/chat/messages` accepte deja `current_page: str | None = Form(None)` — `backend/app/api/chat.py:670`, sanitisation `strip()[:200] or None` — lignes 682-684.
- Frontend Pinia `stores/ui.ts:19,151` (`currentPage`), envoye en multipart par `useChat.ts:253,653`.
- Injecte dans les prompts via `app/prompts/system.py:134` (`build_page_context_instruction`).

**Decision pour cette story** : **on REUTILISE `current_page`**. On **n'ajoute PAS** un champ `page_context` redondant (ce serait un breaking double-emploi). La spec planning sera implementee en mappant `current_page` sur la cle de selection.

### 2. Les `active_entities` n'existent pas

Aucun champ `active_entities` dans `ConversationState`, ni dans le payload chat. Mais `active_module` + `active_module_data` existent deja (spec 013, lignes 34-35 de `state.py`).

**Decision pour cette story** : **AJOUTER** `active_entities: dict | None` au state ET au payload (Form field), **SANS** retirer `active_module*`. Pour le MVP, on charge la pondération uniquement sur `(current_page, active_module)` — `active_entities` est cabled mais le selecteur l'ignore (V1). Cela laisse la voie ouverte pour une story future sans nouveau breaking change.

### 3. Pas de noeud `tool_selector_node` separe — le filtrage doit etre une fonction utilitaire appelee dans chaque noeud specialiste

Le planning evoque un noeud `tool_selector_node` distinct dans le graphe. **Probleme** : le graphe actuel attache les tools **a la construction** via `create_tool_loop(graph, "<node>", node_fn, tools=[...])` — `backend/app/graph/graph.py:136-142`. La liste de tools du `ToolNode` est figee au build, et `bind_tools(...)` est rappele **dans chaque noeud** (`nodes.py` lignes 562, 674, 839, 898, 1073, 1146, 1243, 1305).

**Decision pour cette story** : pas de nouveau noeud LangGraph (eviterait un refactor du `ToolNode` cable). On expose un helper `select_tools_for_node(node_name, current_page, ...)` qui retourne la sous-liste a passer a `bind_tools(...)`. Le `ToolNode` cote graphe **garde la liste complete par module** (sinon le retour de tool serait rejete) ; **seul le LLM** voit la liste filtree, ce qui est exactement le besoin de l'epic M10.

> Cle technique : `bind_tools(filtered)` cote LLM != tools cables au `ToolNode`. Le `ToolNode` doit pouvoir executer tout tool que le LLM a effectivement appele ; en bornant la liste **vue par le LLM**, on garantit qu'il n'appellera pas un tool absent du `ToolNode`. Inversion possible (filtrer aussi le `ToolNode`) = breaking — hors scope.

### 4. Inventaire reel des tools (post-story 10.1)

Les 14 tools refactores story 10.1 + le reste du catalogue :

```
backend/app/graph/tools/
├── action_plan_tools.py    → ACTION_PLAN_TOOLS
├── application_tools.py    → APPLICATION_TOOLS  (6 tools)
├── carbon_tools.py         → CARBON_TOOLS
├── chat_tools.py           → CHAT_TOOLS         (4 tools lecture seule)
├── credit_tools.py         → CREDIT_TOOLS
├── document_tools.py       → DOCUMENT_TOOLS
├── esg_tools.py            → ESG_TOOLS          (5 tools)
├── financing_tools.py      → FINANCING_TOOLS
├── guided_tour_tools.py    → GUIDED_TOUR_TOOLS  (1 tool : trigger_guided_tour)
├── interactive_tools.py    → INTERACTIVE_TOOLS  (1 tool : ask_interactive_question)
└── profiling_tools.py      → PROFILING_TOOLS    (2 tools : update_, get_company_profile)
```

Liens d'import effectifs : `nodes.py` charge ces listes via leurs constantes (`PROFILING_TOOLS`, `ESG_TOOLS`, etc.) — confirmer que **chacune existe** comme attribut module avant d'ecrire le selecteur (sinon ajouter `__all__` correspondant dans `__init__.py` du paquet).

### 5. Ecart majeur — la whitelist du planning cite des tools qui n'existent pas

Le planning cite `ask_qcu, ask_qcm, show_kpi_card, show_mermaid` comme whitelist transverse. **Realite** (verifiee story 10.1, sections §2-§3) :

- `ask_qcu`/`ask_qcm` n'existent PAS : un seul tool `ask_interactive_question` avec un Enum `InteractiveQuestionType`.
- `show_kpi_card`/`show_mermaid` n'existent PAS du tout (visualisations via blocs JSON inline + SSE markers).

**Decision pour cette story** : whitelist transverse reelle =
```python
GLOBAL_WHITELIST = {"ask_interactive_question", "trigger_guided_tour"}
```
Tout autre tool transverse devra etre justifie + revu. **NE PAS** creer les tools `show_*` dans cette PR (verrou story 1, item §3).

### 6. Pages reelles cote frontend

Pages routees dans Nuxt — dossier `frontend/app/pages/`. Audit a faire avant de figer le mapping (lister via `find frontend/app/pages -name "*.vue"`). Slugs documentes dans `app/prompts/system.py:build_page_context_instruction`. Slugs minimaux a couvrir (8 pages epic M10 §criteres d'acceptation) :

`profile`, `candidatures`, `chat_global`, `esg`, `carbon`, `financing`, `dashboard`, `action_plan`.

> Le frontend envoie aujourd'hui `current_page` brut (souvent un **path**, ex `/esg/results`). Le selecteur doit normaliser : path -> slug (ex : `/esg/*` -> `"esg"`, `/financing/*` -> `"financing"`, `/` ou `/chat` -> `"chat_global"`). Cette normalisation centralisee est dans le selecteur, pas cote frontend (pour ne pas casser la spec 003 qui injecte le path brut dans les prompts).

### 7. `tool_call_logs` n'a pas le champ `tools_offered` — migration necessaire

Modele actuel : `backend/app/models/tool_call_log.py:13-83` — colonnes `id, user_id, conversation_id, node_name, tool_name, tool_args, tool_result, duration_ms, status, error_message, retry_count, created_at`.

**Decision pour cette story** : ajouter `tools_offered: JSON | None` (nullable, defaut `None` cote app) via migration Alembic. Aucune backfill necessaire (les anciennes lignes restent NULL). Convention de fichier de migration : suivre `backend/alembic/versions/<hash>_<slug>.py` (cf. exemples `5b7f090f1dcc_add_action_plan_dashboard_tables.py`).

### 8. Methode actuelle de logging d'un tool call

`log_tool_call(...)` est dans `backend/app/graph/tools/common.py` (cf. story 10.1 §6). Le selecteur n'ecrit PAS dans `tool_call_logs` directement — c'est le helper existant qui le fait, **a chaque execution**. Il faut donc :

1. Soit propager `tools_offered` jusqu'a `log_tool_call` via le `RunnableConfig` (`configurable={"tools_offered": [...]}`).
2. Soit stocker `tools_offered` dans `ConversationState` au tour courant (champ ephemere) et le lire depuis le ToolNode. **Option recommandee** : (1) — le pattern `RunnableConfig` est deja utilise pour `user_id` et `conversation_id`.

## Acceptance Criteria

1. **AC1 — Etat & payload etendus (additif, pas de breaking change).**
   - `ConversationState` gagne le champ `active_entities: dict | None` (en plus de `current_page` deja present). Aucun champ existant n'est renomme.
   - Endpoint `POST /api/chat/messages` accepte un Form field optionnel `active_entities: str | None = Form(None)` (JSON string) sanitise `strip()[:2000] or None`, parse via `json.loads` avec fallback `None` si invalide. **Le frontend N'EST PAS modifie dans cette PR** (envoi de `active_entities` = scope future).
   - Le champ `current_page` est **deja** transmis et reutilise tel quel — **interdit** de creer un alias `page_context` (anti-pattern nommage redondant).

2. **AC2 — Mapping declaratif `tool_selector_config.py`.** Fichier `backend/app/graph/tool_selector_config.py` cree, contenant :
   - `PAGE_TOOL_MAPPING: dict[str, set[str]]` — clef = slug page (8 pages minimum : `profile`, `candidatures`, `chat_global`, `esg`, `carbon`, `financing`, `dashboard`, `action_plan`), valeur = set de **noms** de tools (str, `tool.name` LangChain) autorises pour cette page.
   - `MODULE_TOOL_MAPPING: dict[str, set[str]]` — clef = nom de noeud LangGraph (`chat`, `esg_scoring`, `carbon`, `financing`, `application`, `credit`, `action_plan`), valeur = set de tools de ce module (sert de fallback si aucune page connue).
   - `GLOBAL_WHITELIST: frozenset[str] = frozenset({"ask_interactive_question", "trigger_guided_tour"})` — tools toujours disponibles, ajoutes a chaque selection.
   - `MAX_TOOLS_PER_TURN: int = 10` (constante).
   - `PATH_TO_PAGE_SLUG: dict[str, str]` ou helper `normalize_page(current_page: str | None) -> str | None` — mapping path Nuxt -> slug (ex : `/esg/results` -> `"esg"`, `/financing/<id>` -> `"financing"`, `/` ou `None` -> `"chat_global"`). Au minimum 10 patterns regex/prefix couvrant les pages reelles `frontend/app/pages/`.
   - Test au load-time : assert `set(MODULE_TOOL_MAPPING.keys()) <= {"chat", "esg_scoring", "carbon", "financing", "application", "credit", "action_plan", "document"}` (eviter les noms de noeuds inventes).

3. **AC3 — Helper de selection `select_tools_for_node(...)`.** Fichier `backend/app/graph/tool_selector.py` expose :

    ```python
    def select_tools_for_node(
        node_name: str,
        current_page: str | None,
        all_tools: list[BaseTool],
        active_entities: dict | None = None,  # accepte mais ignore en V1
    ) -> tuple[list[BaseTool], dict]:
        """Retourne (tools_filtres, debug_info).

        debug_info = {
            "tools_offered": [t.name for t in tools_filtres],
            "page_slug": str | None,
            "fallback_used": bool,
            "truncated": bool,
        }
        """
    ```

    Regles dans cet ordre :
    - (a) Normaliser `current_page` -> slug via `normalize_page`.
    - (b) Si slug connu -> base = `PAGE_TOOL_MAPPING[slug]` ∩ `{t.name for t in all_tools}`.
    - (c) Sinon (slug inconnu / None) -> base = `MODULE_TOOL_MAPPING[node_name]` ∩ `{t.name for t in all_tools}` ; `fallback_used=True`.
    - (d) Ajouter `GLOBAL_WHITELIST` ∩ `{t.name for t in all_tools}`.
    - (e) Si `len(base) > MAX_TOOLS_PER_TURN` -> tronquer **deterministiquement** (ordre alphabetique du nom de tool) et logger un `WARNING` `tool_selector.truncated` ; `truncated=True`.
    - (f) Retourner les `BaseTool` correspondants (pas seulement les noms), preservant l'ordre du mapping pour reproductibilite.
    - **Invariant runtime** : `len(tools_filtres) <= MAX_TOOLS_PER_TURN`. **Assertion** active (pas un `if`) — un depassement est un bug du mapping.

4. **AC4 — Cablage dans les 8 noeuds specialistes.** Dans `backend/app/graph/nodes.py`, chaque appel `llm.bind_tools(...)` est precede d'un appel a `select_tools_for_node(node_name=..., current_page=state.get("current_page"), all_tools=...)`. Lignes a toucher (audit story 10.1) :
   - `chat_node` (~ ligne 1146) — `node_name="chat"`.
   - `esg_scoring_node` (~ ligne 674) — `node_name="esg_scoring"`.
   - `carbon_node` (~ ligne 839) — `node_name="carbon"`.
   - `financing_node` (~ ligne 898) — `node_name="financing"`.
   - `application_node` (~ ligne 1243) — `node_name="application"`.
   - `credit_node` (~ ligne 1073) — `node_name="credit"`.
   - `action_plan_node` (~ ligne 1305) — `node_name="action_plan"`.
   - `document_node` (si bind_tools present — sinon noter explicitement « pas de bind_tools cote document_node »).

   Le `ToolNode` cote `graph.py` **n'est PAS modifie** (garde la liste complete) — voir §3 du contexte.

5. **AC5 — Trace `tools_offered` dans `tool_call_logs`.**
   - Migration Alembic : nouvelle colonne `tools_offered: JSON | None` (nullable, defaut NULL en BDD pour les lignes existantes). Nom de fichier de migration sous forme `<hash>_add_tools_offered_to_tool_call_logs.py`. Downgrade implemente (drop_column).
   - Modele SQLAlchemy mis a jour (`app/models/tool_call_log.py`).
   - Le helper `log_tool_call(...)` (`backend/app/graph/tools/common.py`) accepte un nouveau parametre `tools_offered: list[str] | None = None` et l'ecrit dans la colonne. Aucun appel existant n'est casse (parametre keyword optionnel).
   - Propagation : la liste `tools_offered` issue de `select_tools_for_node` est attachee au `RunnableConfig.configurable["tools_offered"]` cote noeud, lue dans `log_tool_call` via `config.get("configurable", {}).get("tools_offered")`.

6. **AC6 — Tests d'integration LangGraph par page (pytest).**
   Fichier `backend/tests/graph/test_tool_selector.py` :
   - Pour **5 pages** au minimum (`profile`, `esg`, `carbon`, `financing`, `candidatures`) : assertion **liste exacte** (set) de `tool.name` retournee par `select_tools_for_node` matche `PAGE_TOOL_MAPPING[slug] ∪ GLOBAL_WHITELIST` ∩ available tools.
   - Test fallback : `current_page=None` + `node_name="esg_scoring"` -> `MODULE_TOOL_MAPPING["esg_scoring"] ∪ GLOBAL_WHITELIST` ; `fallback_used=True`.
   - Test page inconnue (`current_page="/route_inexistante"`) -> meme comportement que `None`.
   - Test invariant `<=10` : pour chaque slug du mapping, assert que la base brute (avant whitelist) tient en `MAX_TOOLS_PER_TURN - len(GLOBAL_WHITELIST)`. Si une page configuree depasse, le test echoue (gate de configuration).
   - Test normalisation : 8 paths -> slugs attendus (`/esg/results` -> `esg`, `/dashboard` -> `dashboard`, `/` -> `chat_global`, `None` -> `None`, etc.).

7. **AC7 — Test E2E LangGraph (un noeud, mode dry-run).**
   Test (`backend/tests/graph/test_node_filtered_binding.py`) qui :
   - Construit un `ConversationState` minimal avec `current_page="/esg/results"`.
   - Mock le LLM (pas d'appel reseau) pour capturer les `tools` passes a `bind_tools(...)`.
   - Invoque `esg_scoring_node` une fois.
   - Verifie que la liste vue par `bind_tools` est strictement la meme que `select_tools_for_node("esg_scoring", "/esg/results", ESG_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS)[0]`.
   - Assert `len(...) <= 10`.

8. **AC8 — Audit log de selection (sample 50 conversations).**
   - Un script `backend/scripts/audit_tools_offered.py` lit `tool_call_logs` (par defaut 50 derniers `conversation_id` distincts) et imprime un rapport markdown :

       ```
       Page slug             | turns | avg tools_offered | max
       /esg                  |   12  | 6.2               | 8
       /financing            |   8   | 5.1               | 7
       /chat_global          |   30  | 5.8               | 9
       ...
       Conversations > 10 tools : 0 (gate OK)
       ```
   - **Gate** : 0 conversation avec un tour > 10 tools. Le script sort code 1 si gate viole.
   - Rapport committe dans `backend/tools/_tools_offered_report.md` (peut etre vide juste apres merge ; sera rempli au premier run en dev).

9. **AC9 — Non-regression backend & startup.**
   - `pytest backend/` : tous les tests verts (>=1219 attendus apres 10.1 + nouveaux 6 minimum tests AC6/AC7).
   - `python -c "from app.main import app"` demarre sans warning supplementaire LangChain.
   - Aucune modification des prompts modules (`app/prompts/*.py`) — verrou story 10.1 AC8 reactive ici.
   - Aucun renommage de tool, aucun ajout/retrait de tool dans les `__all__` des modules tools.

10. **AC10 — Documentation breve.**
    - Section ajoutee a `backend/app/graph/tools/README.md` (cree story 10.1) : « Filtrage par contexte (story 10.2) — comment ajouter une nouvelle page : (1) ajouter le slug dans `PAGE_TOOL_MAPPING`, (2) lister les tools, (3) ajouter le mapping path -> slug dans `normalize_page`, (4) ajouter le test exact-match. ».
    - Pas de nouveau .md externe.

## Tasks / Subtasks

- [x] **Tache 1 — Audit prealable (AC1, AC2)**
  - [x] 1.1 `find frontend/app/pages -name "*.vue"` -> capturer la liste exhaustive des paths Nuxt et les regrouper en 8+ slugs.
  - [x] 1.2 Verifier que `PROFILING_TOOLS`, `ESG_TOOLS`, `CARBON_TOOLS`, `FINANCING_TOOLS`, `APPLICATION_TOOLS`, `CREDIT_TOOLS`, `ACTION_PLAN_TOOLS`, `CHAT_TOOLS`, `DOCUMENT_TOOLS`, `INTERACTIVE_TOOLS`, `GUIDED_TOUR_TOOLS` sont exposes par leurs modules respectifs (`grep -n "^[A-Z_]*_TOOLS" backend/app/graph/tools/*.py`).
  - [x] 1.3 Lire les noms reels de `t.name` pour chaque BaseTool de chaque liste (devrait matcher le nom de fonction Python — verifier un par un).
- [x] **Tache 2 — State + endpoint additif (AC1)**
  - [x] 2.1 `app/graph/state.py` : ajouter `active_entities: dict | None`.
  - [x] 2.2 `app/api/chat.py` : Form field `active_entities: str | None = Form(None)`, parse JSON safe, sanitisation `[:2000]`, propagation dans `ConversationState` initial. Aucun changement frontend.
  - [x] 2.3 Test endpoint : couvert indirectement par la non-regression `pytest backend/` (1259 verts).
- [x] **Tache 3 — Mapping & helper (AC2, AC3)**
  - [x] 3.1 Creer `backend/app/graph/tool_selector_config.py` (PAGE_TOOL_MAPPING, MODULE_TOOL_MAPPING, GLOBAL_WHITELIST, MAX_TOOLS_PER_TURN, normalize_page).
  - [x] 3.2 Creer `backend/app/graph/tool_selector.py` (`select_tools_for_node`).
  - [x] 3.3 Logging : `logger = logging.getLogger("app.graph.tool_selector")` ; warning `tool_selector.truncated` si troncature.
- [x] **Tache 4 — Cablage dans les 8 noeuds (AC4)**
  - [x] 4.1 `chat_node` -> `select_tools_for_node("chat", state.get("current_page"), PROFILING_TOOLS + CHAT_TOOLS + DOCUMENT_TOOLS + INTERACTIVE_TOOLS + GUIDED_TOUR_TOOLS, state.get("active_entities"))`.
  - [x] 4.2 Idem pour `esg_scoring_node`, `carbon_node`, `financing_node`, `application_node`, `credit_node`, `action_plan_node`.
  - [x] 4.3 `document_node` : aucun `bind_tools` present, RIEN a faire (verifie ligne 468 de nodes.py).
  - [x] 4.4 7 appels `bind_tools(...)` consomment maintenant `filtered_tools` (verifie via `grep bind_tools nodes.py`).
- [x] **Tache 5 — Migration & log enrichi (AC5)**
  - [x] 5.1 Migration `backend/alembic/versions/10b2_add_tools_offered_to_tool_call_logs.py` (down=018_interactive, upgrade/downgrade explicites).
  - [x] 5.2 Migration testee localement non applicable (env CI). La table sera mise a jour au deploiement (`alembic upgrade head`).
  - [x] 5.3 `app/models/tool_call_log.py` : `tools_offered: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)`.
  - [x] 5.4 `app/graph/tools/common.py` : `log_tool_call(..., tools_offered=None)` + helper `_tools_offered_from_config`. Propagation aux 3 sites de log dans `with_retry`.
  - [x] 5.5 Helper `_propagate_tools_offered(config, names)` dans `nodes.py` ; appele dans chaque noeud apres selection.
- [x] **Tache 6 — Tests (AC6, AC7)**
  - [x] 6.1 `backend/tests/graph/test_tool_selector.py` (35 tests, `pytest.mark.unit`).
  - [x] 6.2 `backend/tests/graph/test_node_filtered_binding.py` (1 test E2E, mock LLM, capture bind_tools args).
  - [x] 6.3 Marqueurs : `pytest.mark.unit` selecteur, `pytest.mark.integration` E2E.
- [x] **Tache 7 — Audit script (AC8)**
  - [x] 7.1 `backend/scripts/audit_tools_offered.py` (SQLAlchemy async, 50 derniers conv_ids, agregat par node_name, exit code 1 si gate viole).
  - [x] 7.2 Section 8 ajoutee dans `backend/app/graph/tools/README.md`.
- [x] **Tache 8 — Docs & validation finale (AC9, AC10)**
  - [x] 8.1 `pytest backend/` : 1259 verts (3 echecs preexistants `test_guided_tour_*` hors scope).
  - [x] 8.2 `python -c "from app.main import app"` clean (77 routes).
  - [x] 8.3 README mis a jour (section 8 « Filtrage par contexte »).
  - [x] 8.4 PR avec recap : 12 slugs couverts (8 requis + 4 bonus : credit, documents, reports), tools/page <= 10, rapport audit dans `backend/tools/_tools_offered_report.md`.

## Dev Notes

### Architecture & guardrails

- **Versions** (CLAUDE.md confirmees) : Python 3.12, FastAPI, LangGraph >=0.2.0, LangChain >=0.3.0, langchain-openai >=0.3.0, Pydantic v2, SQLAlchemy async, Alembic.
- **Filtre LLM-side uniquement** : on **change ce que le LLM voit** (`bind_tools`), pas ce que `ToolNode` execute. Ainsi un retour LLM avec un nom de tool **non filtre** reste impossible (le LLM ne le connait pas), et un eventuel cas d'echec retombe dans le pattern d'erreur LangChain habituel (le LLM appelle alors un tool qu'il connait ou repond en texte).
- **`RunnableConfig`** : pattern existant pour `user_id`, `conversation_id` (cf. `common.py`). Ajout de `tools_offered` suit le meme pattern, **n'augmente pas** la taille de prompt.
- **Pas de noeud `tool_selector_node`** : decision architecturale du contexte §3. Le helper est appele inline dans chaque noeud — c'est un trade-off entre purete LangGraph et minimalite de PR.
- **Determinisme** : `select_tools_for_node` doit etre **pur** (pas d'I/O, pas de DB). Toute la decision repose sur `(node_name, current_page, all_tools, active_entities)`.

### Sources de verite (paths et lignes)

- `backend/app/graph/state.py:9-39` (`ConversationState`).
- `backend/app/api/chat.py:127-175` (signature interne) ; `:670-690` (Form fields, sanitisation) ; `:855-860` (propagation au graphe).
- `backend/app/graph/graph.py:7-8, 100-160` (build, ToolNode cabling).
- `backend/app/graph/nodes.py` -> appels `bind_tools` aux lignes : 562 (esg setup), 674 (esg bind), 839, 898, 1073, 1146, 1243, 1305.
- `backend/app/graph/tools/common.py` (`get_db_and_user`, `log_tool_call`).
- `backend/app/models/tool_call_log.py:13-83` (modele a etendre).
- `backend/app/prompts/system.py:134` (`build_page_context_instruction`) — **non modifie** mais explique la convention slugs deja presente.
- `frontend/app/composables/useChat.ts:253,653` (envoi `current_page`).
- `frontend/app/stores/ui.ts:19,151` (`currentPage`).
- Migrations Alembic existantes : `backend/alembic/versions/<hash>_<slug>.py` — convention de nom hash+slug.
- Source planning : `_bmad-output/planning-artifacts/module-10-tool-use-reliability/story-2-tool-filtering-by-page-context.md`.
- Source epic : `_bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md`.
- Story precedente : `_bmad-output/implementation-artifacts/10-1-tool-descriptions-pydantic-strict.md` (DONE — descriptions + schemas durcis ; les `tool.name` sont stables, AC8 verrouille les renommages).

### Source tree a toucher

```
backend/app/graph/
  state.py                       [MODIFIE — ajout active_entities]
  tool_selector_config.py        [CREE]
  tool_selector.py               [CREE]
  nodes.py                       [MODIFIE — 7 a 8 appels bind_tools]
  tools/
    README.md                    [MODIFIE — section filtrage]
    common.py                    [MODIFIE — log_tool_call accepte tools_offered]
backend/app/api/
  chat.py                        [MODIFIE — Form field active_entities]
backend/app/models/
  tool_call_log.py               [MODIFIE — colonne tools_offered]
backend/alembic/versions/
  <hash>_add_tools_offered_to_tool_call_logs.py  [CREE]
backend/scripts/
  audit_tools_offered.py         [CREE]
backend/tests/graph/
  test_tool_selector.py          [CREE]
  test_node_filtered_binding.py  [CREE]
```

**Hors scope (NE PAS toucher)** :
- `backend/app/prompts/*.py` (verrou — pas de modification de prompts).
- `backend/app/graph/graph.py` (le `ToolNode` garde la liste complete par module — voir contexte §3).
- `frontend/**` (le frontend envoie deja `current_page` ; `active_entities` est cabled cote backend uniquement, scope future).
- `backend/app/graph/tools/{action_plan,carbon,credit,document,financing,chat,guided_tour,interactive,esg,profiling,application}_tools.py` (les tools eux-memes ne changent pas).
- Aucun renommage de tool. Aucun ajout/suppression de tool.

### Anti-patterns a eviter (LLM dev mistakes)

1. **NE PAS** introduire un alias `page_context` — `current_page` existe deja (contexte §1).
2. **NE PAS** ajouter un noeud `tool_selector_node` au graphe — c'est un helper, pas un noeud (contexte §3).
3. **NE PAS** filtrer la liste cote `ToolNode` (`create_tool_loop`) — le ToolNode doit pouvoir executer un tool eventuellement appele ; on filtre **uniquement** cote LLM via `bind_tools`.
4. **NE PAS** mettre dans `GLOBAL_WHITELIST` les noms de tools `show_*` ou `ask_qcu`/`ask_qcm` qui n'existent pas (contexte §5 ; verrou story 10.1).
5. **NE PAS** modifier les prompts modules (pas necessaire, verrou epic).
6. **NE PAS** tronquer le mapping en silence — emettre un WARNING + `truncated=True` dans le debug_info ; le test AC6 verifie qu'aucune page **configuree** ne depasse 10 ; la troncature ne devrait jamais se declencher en prod, c'est un filet de securite.
7. **NE PAS** lire la base de donnees dans `select_tools_for_node` — fonction pure, deterministe, testable sans I/O.
8. **NE PAS** ajouter `active_entities` cote frontend dans cette PR — cabled-only backend pour preparer la story future.
9. **NE PAS** appeler le LLM pour classifier l'intention (story 1.5/2.5 du planning original parlait d'un classificateur LLM leger ; **deplace post-MVP**, story 5 backlog).
10. **NE PAS** modifier la signature de `log_tool_call` de maniere breaking — ajouter `tools_offered` en kwarg avec defaut `None`.

### Methodologie suggeree (TDD)

1. Ecrire `test_tool_selector.py` (AC6) -> RED.
2. Implementer `tool_selector_config.py` + `tool_selector.py` (AC2, AC3) -> GREEN.
3. Cabler 1 seul noeud (`esg_scoring_node`) + ecrire `test_node_filtered_binding.py` (AC7) -> verifier mock-LLM.
4. Cabler les 6 autres noeuds (AC4).
5. Migration + extension `log_tool_call` + injection RunnableConfig (AC5).
6. Script audit (AC8) — peut etre teste avec une fixture seed minimale.
7. Validation finale (AC9).

### Standards de tests (rappel global)

- Couverture minimale 80% (cf. `~/.claude/rules/common/testing.md`).
- Framework : `pytest` + `pytest-asyncio` ; `pytest.mark.unit` pour le selecteur, `pytest.mark.integration` pour le test noeud LangGraph.
- Activer le venv : `source backend/venv/bin/activate` avant `pytest` (cf. CLAUDE.md).

### Project Structure Notes

- Le fichier `backend/tests/graph/__init__.py` existe deja (cree story 10.1).
- Le repertoire `backend/scripts/` existe deja (`measure_tools_token_budget.py`, etc.).
- Aucune nouvelle dependance Python — uniquement langchain/langgraph/sqlalchemy deja en place.

### Sprint status note

`sprint-status.yaml` ne contient PAS encore d'entree pour epic 10 (verifie 2026-04-29). Le PM/dev doit ajouter avant la PR :
- `epic-10: in-progress` (deja initie a story 10.1, a confirmer).
- `10-1-tool-descriptions-pydantic-strict: done` (story 10.1 implementee).
- `10-2-tool-filtering-by-page-context: ready-for-dev` (cette story).
- `last_story_created: '10-2-tool-filtering-by-page-context'` + `last_updated`.

### References

- `_bmad-output/planning-artifacts/module-10-tool-use-reliability/story-2-tool-filtering-by-page-context.md` (lignes 13-75 : objectifs, AC origine).
- `_bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md` (lignes 64-86 : architecture cible ; lignes 88-96 : criteres de succes epic).
- `_bmad-output/implementation-artifacts/10-1-tool-descriptions-pydantic-strict.md` (intelligence : noms de tools stables, perimetre 14 tools, anti-patterns persistants).
- `CLAUDE.md` Recent Changes : specs 012 (32 tools origine), 013 (active_module + active_module_data), 018 (interactive widgets), 019 (guided tours).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) via Claude Code CLI (bmad-create-story workflow).

### Debug Log References

- Baseline pytest avant implementation : 1223 passed, 3 failed (preexistants `test_guided_tour_*`).
- Pytest final : 1259 passed (+36 nouveaux tests), 3 failed identiques (hors scope).
- Startup `from app.main import app` : OK, 77 routes.

### Completion Notes List

- Selecteur implemente comme **fonction utilitaire pure** (pas de noeud LangGraph) — verrou §3 respecte.
- `current_page` reutilise tel quel (pas d'alias `page_context`) — verrou §1 respecte.
- `ToolNode` dans `graph.py` non touche : il garde la liste complete par module — verrou §3 respecte.
- Aucun prompt module modifie — verrou epic respecte.
- Aucun changement frontend (`active_entities` cabled-only backend pour scope future).
- 12 slugs couverts dans `PAGE_TOOL_MAPPING` (8 requis + `credit`, `documents`, `reports` bonus + alias `candidatures`).
- Whitelist transverse : `{ask_interactive_question, trigger_guided_tour}` uniquement (pas de `show_*` ou `ask_qcu/qcm` qui n'existent pas — verrou §5 respecte).
- Tests : 35 unit (`test_tool_selector.py`) + 1 integration (`test_node_filtered_binding.py`).
- 3 failures `test_guided_tour_*` preexistantes : non liees a la story 10.2, deja presentes dans la baseline. A traiter dans une story dediee guided_tour.

### File List

**CREE** :
- `backend/app/graph/tool_selector_config.py` (mapping PAGE/MODULE/WHITELIST + normalize_page)
- `backend/app/graph/tool_selector.py` (helper `select_tools_for_node`)
- `backend/alembic/versions/10b2_add_tools_offered_to_tool_call_logs.py` (migration)
- `backend/scripts/audit_tools_offered.py` (script audit)
- `backend/tools/_tools_offered_report.md` (rapport audit, vide initial)
- `backend/tests/graph/test_tool_selector.py` (35 tests unit)
- `backend/tests/graph/test_node_filtered_binding.py` (1 test integration)

**MODIFIE** :
- `backend/app/graph/state.py` (+ `active_entities`)
- `backend/app/graph/nodes.py` (cablage selecteur dans 7 noeuds, helper `_propagate_tools_offered`)
- `backend/app/api/chat.py` (Form field `active_entities` + helper `_parse_active_entities`)
- `backend/app/models/tool_call_log.py` (+ colonne `tools_offered`)
- `backend/app/graph/tools/common.py` (`log_tool_call(tools_offered=...)`, propagation via 3 sites de log)
- `backend/app/graph/tools/README.md` (section 8 « Filtrage par contexte »)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status -> in-progress puis review)

### Change Log

- 2026-04-29 : Implementation story 10.2 complete. 1259 tests verts (vs 1223 baseline). Statut -> review.
