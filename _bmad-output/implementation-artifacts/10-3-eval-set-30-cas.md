# Story 10.3 : Mini eval set de 30 cas sur tools critiques

Status: review

<!-- Source planning :
  - _bmad-output/planning-artifacts/module-10-tool-use-reliability/story-3-eval-set-30-cas.md
  - _bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md
  Stories precedentes (intelligence) :
  - _bmad-output/implementation-artifacts/10-1-tool-descriptions-pydantic-strict.md (DONE 2026-04-29)
  - _bmad-output/implementation-artifacts/10-2-tool-filtering-by-page-context.md (DONE 2026-04-29)
-->

## Story

En tant que **developpeur backend M10**,
je veux **un golden set versionne de 30 cas `(message_utilisateur, current_page) -> (tool_attendu, payload_attendu)` et un runner pytest deterministe**,
afin que **toute modification de prompt, de tool description, de modele LLM ou de mapping `tool_selector_config` soit verifiee objectivement contre une baseline** et qu'aucune regression de tool-calling n'arrive en silence avant la demo MVP (epic M10 critere de succes : >=90% bon tool + payload valide).

## Contexte — etat reel verifie le 2026-04-29

Audit prealable realise. **Plusieurs hypotheses du planning d'origine sont fausses** au regard du code apres stories 10.1 et 10.2. Le dev DOIT lire ce contexte avant d'ecrire un seul cas YAML.

### 1. Repartition des 30 cas du planning — invalide telle quelle

Le planning original (`story-3-eval-set-30-cas.md` lignes 28-37) propose :

| Module | Tool cible | Cas |
|--------|-----------|-----|
| `ask_qcu` | question fermee | 5 |
| `ask_qcm` | multi-choix | 3 |
| `show_kpi_card` | chiffre cle | 4 |
| `show_radar_chart` / `show_pie_chart` | visualisation | 4 |
| `update_company_profile` | mutation profil | 5 |
| `create_fund_application` | mutation candidature | 3 |
| `batch_save_esg_criteria` | mutation ESG | 3 |
| Cas piege (texte libre) | — | 3 |

**Ecart 1 — `ask_qcu` / `ask_qcm` n'existent PAS** comme tools distincts (verrou story 10.1 §1, story 10.2 §5). Il existe **un seul tool** `ask_interactive_question` avec `question_type: InteractiveQuestionType` (enum a 4 valeurs : `QCU`, `QCM`, `QCU_JUSTIFICATION`, `QCM_JUSTIFICATION` — cf. `backend/app/schemas/interactive_question.py:47-73`). Source : `backend/app/graph/tools/interactive_tools.py:75,201`.

**Ecart 2 — `show_kpi_card`, `show_radar_chart`, `show_pie_chart`, `show_mermaid` n'existent PAS du tout** (verifie : `grep -rn "show_" backend/app/graph/tools/` retourne 0 ligne). Les visualisations sont produites via blocs JSON inline + SSE markers dans les reponses des prompts modules, **pas** via tool call. **Interdit** d'inventer ces tools dans cette story (verrou epic M10 + verrou story 10.1).

**Decision pour cette story** — repartition reelle des 30 cas :

| Cible | Cas | Justification |
|-------|-----|---------------|
| `ask_interactive_question` (QCU) | 5 | question fermee 2-7 options exclusives |
| `ask_interactive_question` (QCM) | 2 | multi-choix |
| `ask_interactive_question` (QCU_JUSTIFICATION) | 1 | variante justification |
| `update_company_profile` | 6 | mutation profil (page `profile`) |
| `create_fund_application` | 3 | mutation candidature (page `candidatures` ou `financing`) |
| `batch_save_esg_criteria` | 3 | mutation ESG batch (page `esg`) |
| Tool mutation carbone (a verifier dans `carbon_tools.py`) | 2 | mutation carbone (page `carbon`) |
| `trigger_guided_tour` | 1 | tool transverse (whitelist globale story 10.2) |
| `get_company_profile` ou tool lecture | 2 | tool lecture seule (page `profile` / `dashboard`) |
| Cas piege « pas de tool, texte libre attendu » | 5 | salutations, hors-domaine, redirection |

Total = 30. Verrou : ne pas inventer un nouveau tool — chaque `expected_tool` doit exister dans le catalogue verifie story 10.1. Si un tool de la repartition ci-dessus n'existe pas (ex : `update_carbon_footprint`), le dev **substitue** par un tool reel du module `carbon_tools.py` (`grep -n "^[A-Z_]*_TOOLS" backend/app/graph/tools/carbon_tools.py`) et **documente** la substitution dans le README de l'eval.

### 2. Le champ s'appelle `current_page` (pas `page_context`)

Verrou story 10.2 §1 : pas d'alias `page_context`. Le YAML golden set DOIT utiliser **`current_page`** comme cle (path Nuxt brut, ex `/esg/results`, `/profile`, `/financing`, `/`, `null`). Le runner normalise via `normalize_page` (`backend/app/graph/tool_selector_config.py`) — donc le YAML reflete ce que le frontend envoie, pas le slug interne.

### 3. Le LLM voit deja une liste filtree de tools (story 10.2 cablee)

Critique pour le runner : si on invoque le graphe avec `current_page="/profile"`, le LLM ne verra **que** les tools de `PAGE_TOOL_MAPPING["profile"] ∪ GLOBAL_WHITELIST`. Le runner DOIT donc reutiliser `select_tools_for_node` pour construire la liste vue par le LLM, **identique a la prod**. Sans ca, l'eval testerait un univers de tools different du runtime (faux negatifs systematiques).

**Decision** : invocation **noeud LLM isolee** pour le runner (pas le graphe complet). On capture l'`AIMessage.tool_calls` retourne par `llm.bind_tools(filtered).invoke([HumanMessage(message)])`. Aucun `ToolNode.invoke` n'est appele. Les cas piege (`expected_tool: null`) verifient que le LLM repond en texte libre (pas de tool_call).

### 4. `tool_call_logs` ne doit PAS etre ecrit par l'eval

L'eval est offline. Aucun side-effect (pas d'INSERT, pas de mutation profil, pas de creation candidature). Implications :
- Mock systematique de `get_db_and_user` dans `common.py` (monkeypatch local au runner).
- Mock de `log_tool_call`.
- Le runner peut etre lance hors connexion DB (CI sans postgres).

### 5. Modele courant et determinisme

Modele LLM via OpenRouter (cf. `backend/app/llm/llm.py`). Story 10.1/10.2 ont fige `request_timeout=60` + `temperature=0`. **Verrou determinisme** : pas de seed disponible chez la plupart des modeles OpenRouter — un cas peut basculer de « bon tool » a « texte libre » d'un run a l'autre. **Recommandation** : la baseline est un **snapshot informatif** (pas un test bloquant), et le seuil >=90% de l'epic est verifie **en moyenne sur 3 runs consecutifs** dans le rapport.

### 6. Pyproject vs pytest.ini

Le backend utilise **`pytest.ini`** (pas `pyproject.toml`). Le marker `eval` doit etre declare dans `backend/pytest.ini` (cf. `pytest.ini:6-7`). Deja present : `unit`. A ajouter : `eval`, `integration` (cf. story 10.2 qui utilise `integration` sans declaration explicite — l'ajouter ici evite le warning `PytestUnknownMarkWarning`).

### 7. Format YAML — `expected_payload_partial` (subset match)

Le planning dit « subset match : tous les champs `expected_payload_partial` doivent etre presents avec la bonne valeur ; le LLM peut ajouter des champs additionnels valides ». **Decision** : valider en plus que **tous les champs additionnels** restent dans le **schema Pydantic strict du tool** (story 10.1 a fige les schemas). Un payload qui contient un champ hors schema est un echec, meme si tous les `expected_payload_partial` matchent.

### 8. Baseline et chemin de fichier

Le planning propose `backend/tests/llm_eval/baselines/2026-04-29_<modele>.json`. Comme le modele OpenRouter peut changer (env var `OPENROUTER_MODEL` ou config `app/llm/llm.py`), le `<modele>` du nom de fichier doit etre **derive runtime** : `slugify(get_llm_model_id())`. Le runner imprime le nom de fichier choisi.

## Acceptance Criteria

1. **AC1 — Arborescence eval-set creee.**
   - `backend/tests/llm_eval/__init__.py` (vide).
   - `backend/tests/llm_eval/golden_set_v1.yaml` — 30 cas exactement, format ci-dessous.
   - `backend/tests/llm_eval/run_eval.py` — runner CLI + lib.
   - `backend/tests/llm_eval/test_eval_runner.py` — pytest qui execute le set quand `-m eval` actif.
   - `backend/tests/llm_eval/baselines/.gitkeep` (repertoire versionne).
   - `backend/tests/llm_eval/README.md` — documentation (cf. AC8).

2. **AC2 — Schema YAML golden set v1.**
   - Chaque entree :
     ```yaml
     - id: case_001
       message: "Mon entreprise est une SARL avec 12 salaries dans l'agroalimentaire."
       current_page: "/profile"            # path Nuxt brut, ou null pour chat global
       node_name: "chat"                    # noeud LangGraph cible (selection de tools)
       expected_tool: "update_company_profile"   # null si cas piege (texte libre)
       expected_payload_partial:                # ignore si expected_tool est null
         legal_form: "SARL"
         employee_count: 12
         sector: "agroalimentaire"
       notes: "Mutation profil, 3 champs canoniques"
     ```
   - 30 entrees au total, repartition exacte cf. contexte §1.
   - Ids `case_001` a `case_030`, format 3 chiffres avec zero-padding.
   - `current_page` couvre >=6 pages distinctes parmi : `/profile`, `/esg`, `/esg/results`, `/carbon`, `/financing`, `/financing/<id>`, `/candidatures`, `/dashboard`, `/action_plan`, `/`, `null`.
   - `node_name` ∈ `{"chat", "esg_scoring", "carbon", "financing", "application", "credit", "action_plan"}` (verrou story 10.2 mapping).

3. **AC3 — Runner `run_eval.py` (mode CLI).**
   ```
   python -m tests.llm_eval.run_eval --golden tests/llm_eval/golden_set_v1.yaml \
       [--save-baseline] [--limit N] [--cases case_001,case_005]
   ```
   - Charge le YAML, itere chaque cas.
   - Pour chaque cas : construit `ConversationState` minimal, appelle `select_tools_for_node(node_name, current_page, all_tools_for_node)` (story 10.2), invoque `llm.bind_tools(filtered).invoke([HumanMessage(message)])` avec `temperature=0`.
   - **Aucune execution de `ToolNode`**. Aucune ecriture en base. Mock `get_db_and_user` + `log_tool_call` via monkeypatch local au runner.
   - Capture l'`AIMessage.tool_calls`. Calcule 4 metriques par cas et globales :
     - `bon_tool` : `tool_calls[0].name == expected_tool` OU `expected_tool is None and tool_calls == []`.
     - `payload_valide` : `tool.args_schema(**tool_calls[0].args)` sans levee Pydantic. N/A si pas de tool attendu.
     - `payload_partial_match` : tous les champs `expected_payload_partial` matchent par egalite (`==`). N/A si pas de tool attendu.
     - `fallback_texte` : `tool_calls == []` ET `expected_tool is not None` (echec).
   - Imprime un rapport markdown stdout :
     ```
     # Eval golden_set_v1 — 2026-04-29 — modele=<id>
     Cas : 30
     - Bon tool      : 28/30 (93.3%)  ✓ >=90%
     - Payload valide: 27/28 (96.4%)
     - Subset match  : 25/28 (89.3%)
     - Fallback texte: 2/30  (6.7%)   ⚠ >5%
     ## Echecs detailles
     - case_007 : expected=update_company_profile, got=ask_interactive_question. Message : "..."
     - case_023 : payload manquant `legal_form`. Got : {...}
     ```
   - Avec `--save-baseline` : ecrit `backend/tests/llm_eval/baselines/<YYYY-MM-DD>_<modele_slug>.json` contenant pour chaque cas l'AIMessage capture (name, args), les 4 metriques, le timestamp ISO 8601 UTC, le model_id, le hash SHA-256 du golden YAML.
   - Exit code : `0` si bon_tool >= 90% ET fallback_texte <= 10%, sinon `1`.

4. **AC4 — Integration pytest `-m eval`.**
   - Marker `eval` ajoute a `backend/pytest.ini` :
     ```ini
     markers =
         unit: tests unitaires sans I/O (DB/LLM/reseau)
         integration: tests qui invoquent le graphe LangGraph (mock LLM)
         eval: golden set LLM (skippe par defaut, lance via -m eval, requiert OPENROUTER_API_KEY)
     ```
   - `test_eval_runner.py` :
     ```python
     @pytest.mark.eval
     def test_golden_set_meets_baseline():
         result = run_eval(golden_path="tests/llm_eval/golden_set_v1.yaml")
         assert result.bon_tool_rate >= 0.90
         assert result.fallback_text_rate <= 0.10
     ```
   - Skip explicite si `OPENROUTER_API_KEY` absente : `pytest.skip("OPENROUTER_API_KEY missing")` (eviter rouge en CI sans secret).

5. **AC5 — Baseline initiale enregistree.**
   - Un fichier `backend/tests/llm_eval/baselines/2026-04-29_<modele_slug>.json` est commite dans cette PR. Il est genere via `python -m tests.llm_eval.run_eval --save-baseline`.
   - Le hash du golden set au moment du run est inclus dans le JSON. Si le hash diverge a un run futur, le runner imprime un WARNING (la baseline n'est plus comparable).

6. **AC6 — Aucun side-effect base / fichier hors `baselines/`.**
   - `pytest backend/ -m "not eval"` reste vert (regression). Verifier que `golden_set_v1.yaml` n'est pas parse, que `test_eval_runner.py` est bien skippe sans `-m eval`.
   - Aucun INSERT dans `tool_call_logs` lors d'un run eval (mock systematique).
   - Aucun appel externe autre que l'API OpenRouter (pas de RAG, pas de DB read).

7. **AC7 — Runner robuste aux echecs LLM.**
   - Timeout par cas : 30s. Depassement -> cas marque `bon_tool=False, error="timeout"`, report continue.
   - Erreur reseau (HTTPError, RateLimitError) : retry 1x avec backoff 2s. Si echec : cas marque `error=<exc.__class__.__name__>`.
   - Le runner ne crash JAMAIS sur 30 cas — un cas en erreur ne fait pas tomber les 29 autres.

8. **AC8 — README `backend/tests/llm_eval/README.md`.**
   - Section « Comment ajouter un cas » : 4 etapes (ouvrir YAML, copier le template, choisir id `case_NNN`, ajouter notes).
   - Section « Comment lancer » : 3 commandes (CLI, `pytest -m eval`, `--save-baseline`).
   - Section « Verrous a respecter » : reprend explicitement les ecarts §1 (`ask_qcu/qcm/show_*` n'existent pas) pour eviter qu'un futur dev les inscrive.
   - Section « Limites » : determinisme imparfait, baseline informative, gates >=90% / <=10%.

9. **AC9 — Non-regression.**
   - `pytest backend/ -m "not eval"` : >=1259 tests verts (baseline story 10.2). Aucun nouveau test cassant la suite normale.
   - `python -c "from app.main import app"` : OK, aucun warning supplementaire.
   - Aucune modification de prompt module (`app/prompts/*.py`) — verrou epic.
   - Aucune modification de tool, mapping, ou selecteur (verrou stories 10.1 + 10.2).
   - Aucun renommage de tool.

10. **AC10 — Sprint status & docs.**
    - `_bmad-output/implementation-artifacts/sprint-status.yaml` : `10-3-eval-set-30-cas` -> `ready-for-dev` (cette story), puis `in-progress` au demarrage, puis `review` apres implementation.
    - Section ajoutee au `backend/app/graph/tools/README.md` : « § Eval set v1 — 30 cas (story 10.3). Voir `backend/tests/llm_eval/README.md`. ».

## Tasks / Subtasks

- [x] **Tache 1 — Audit prealable (AC2)**
  - [x] 1.1 `grep -rn "^[A-Z_]*_TOOLS" backend/app/graph/tools/*.py` — confirmer la liste exacte des tools/module.
  - [x] 1.2 Verifier l'existence d'un tool de mutation carbone (`carbon_tools.py`). `create_carbon_assessment` existe (carbon_tools.py:15) — utilise pour cas 021/022 ; aucune substitution necessaire.
  - [x] 1.3 Lister les `tool.name` reels (= nom de fonction Python) pour les tools cibles : `update_company_profile`, `create_fund_application`, `batch_save_esg_criteria`, `ask_interactive_question`, `trigger_guided_tour`, `get_company_profile_chat`, `get_user_dashboard_summary`.
- [x] **Tache 2 — Arborescence et marker pytest (AC1, AC4)**
  - [x] 2.1 Creer `backend/tests/llm_eval/{__init__.py, baselines/.gitkeep}`.
  - [x] 2.2 Ajouter le marker `eval` (et `integration`) dans `backend/pytest.ini`.
- [x] **Tache 3 — Golden set YAML 30 cas (AC2)**
  - [x] 3.1 Ecrire `golden_set_v1.yaml` selon repartition contexte §1.
  - [x] 3.2 Couvrir >=6 pages distinctes (`/profile`, `/esg`, `/esg/results`, `/carbon`, `/financing`, `/financing/<uuid>`, `/candidatures`, `/dashboard`, `/`) ; phrasings varies.
  - [x] 3.3 Inclure 5 cas piege (salutation, off-topic geographie, opinion ouverte, message court remerciement, question pedagogique).
- [x] **Tache 4 — Runner CLI (AC3, AC7)**
  - [x] 4.1 `run_eval.py` : argparse, parsing YAML, invocation LLM par cas.
  - [x] 4.2 Neutralisation `get_db_and_user` + `log_tool_call` via `_patch_no_side_effect()` (defense en profondeur).
  - [x] 4.3 Boucle de retry (1x backoff 2s) + timeout 30s (`asyncio.wait_for`).
  - [x] 4.4 Output rapport markdown stdout + `--save-baseline` JSON.
  - [x] 4.5 Exit code selon gates (>=90% bon_tool, <=10% fallback).
- [x] **Tache 5 — Test pytest eval (AC4, AC6)**
  - [x] 5.1 `test_eval_runner.py` : 17 tests `unit` (parsing, verrous, metriques, baseline) + 1 test `eval` skippe sans API key.
  - [x] 5.2 Verifie : `pytest -m "not eval"` ne collecte pas le test marker `eval` (deselectionne).
- [ ] **Tache 6 — Baseline initiale (AC5)** — **MERGE-BLOCKER : a executer localement par le dev avec `OPENROUTER_API_KEY` avant l'ouverture de la PR. Status=review n'autorise PAS le merge sans ce JSON commite (AC5 explicite).**
  - [ ] 6.1 Lancer `python -m tests.llm_eval.run_eval --save-baseline` localement (la session courante n'a pas de cle API).
  - [ ] 6.2 Commiter le JSON dans `baselines/`.
- [x] **Tache 7 — Documentation (AC8, AC10)**
  - [x] 7.1 Ecrire `backend/tests/llm_eval/README.md` (sections : Lancer, Ajouter un cas, Verrous, Limites, Architecture).
  - [x] 7.2 Ajouter section « Eval set v1 — 30 cas (story 10.3) » dans `backend/app/graph/tools/README.md`.
- [x] **Tache 8 — Validation finale (AC9)**
  - [x] 8.1 `pytest backend/ -m "not eval"` : 1278 verts (3 echecs preexistants `test_guided_tour_*` non lies a 10.3 — confirme via `git stash` avant cette story). 18 nouveaux tests `unit` ajoutes.
  - [x] 8.2 `python -c "from app.main import app"` : OK, aucun warning supplementaire.
  - [ ] 8.3 PR avec recap : 30 cas, taux baseline initial, modele utilise, exit code 0 — **a faire apres baseline (6.1/6.2)**.

## Dev Notes

### Architecture & guardrails

- **Versions** (CLAUDE.md confirmees) : Python 3.12, pytest, pytest-asyncio, LangChain >=0.3.0, LangGraph >=0.2.0, langchain-openai. PyYAML est deja installe (verifier `requirements.txt` — sinon ajouter).
- **Pas d'execution de tool** : on capture seulement l'intent du LLM (`AIMessage.tool_calls`). Test de **selection + payload**, pas d'execution. Permet de runner offline sans Postgres.
- **Determinisme limite** : `temperature=0` mais pas de seed garanti -> baseline = snapshot informatif. Le **gate epic** (>=90%) est verifie **en moyenne sur 3 runs**, pas sur un seul.
- **Mock minimal** : monkeypatch local au runner pour `get_db_and_user` et `log_tool_call`. NE PAS modifier les tools (verrou story 10.1).
- **Selection de tools** : reutiliser `select_tools_for_node` story 10.2 — coherence prod / eval. Sans ca, faux negatifs systematiques.

### Sources de verite (paths et lignes)

- `backend/app/graph/tools/interactive_tools.py:75,201` — `ask_interactive_question`, `INTERACTIVE_TOOLS`.
- `backend/app/schemas/interactive_question.py:47-73` — enum `InteractiveQuestionType` (QCU, QCM, QCU_JUSTIFICATION, QCM_JUSTIFICATION).
- `backend/app/graph/tools/profiling_tools.py:53,162` — `update_company_profile`, `get_company_profile`.
- `backend/app/graph/tools/application_tools.py:132,383` — `create_fund_application`, `APPLICATION_TOOLS`.
- `backend/app/graph/tools/esg_tools.py:331,419` — `batch_save_esg_criteria`, `ESG_TOOLS`.
- `backend/app/graph/tools/guided_tour_tools.py` — `trigger_guided_tour`.
- `backend/app/graph/tools/common.py` — `log_tool_call`, `get_db_and_user` (a mocker).
- `backend/app/graph/tool_selector.py` (story 10.2) — `select_tools_for_node`.
- `backend/app/graph/tool_selector_config.py` (story 10.2) — `PAGE_TOOL_MAPPING`, `MODULE_TOOL_MAPPING`, `normalize_page`.
- `backend/app/llm/llm.py` — `get_llm()` (a confirmer via `find backend/app -name "llm*.py"`).
- `backend/pytest.ini:1-7` — config pytest, ajouter marker `eval`.
- Story 10.1 : `_bmad-output/implementation-artifacts/10-1-tool-descriptions-pydantic-strict.md` (verrous schemas).
- Story 10.2 : `_bmad-output/implementation-artifacts/10-2-tool-filtering-by-page-context.md` (selecteur, mapping pages).

### Source tree a toucher

```
backend/tests/llm_eval/
  __init__.py                          [CREE — vide]
  golden_set_v1.yaml                   [CREE — 30 cas]
  run_eval.py                          [CREE — runner CLI + lib]
  test_eval_runner.py                  [CREE — pytest marker eval]
  README.md                            [CREE — doc add/lancer/verrous]
  baselines/
    .gitkeep                           [CREE]
    2026-04-29_<modele_slug>.json      [CREE — baseline initiale]
backend/
  pytest.ini                           [MODIFIE — markers eval + integration]
backend/app/graph/tools/
  README.md                            [MODIFIE — section eval set v1]
_bmad-output/implementation-artifacts/
  sprint-status.yaml                   [MODIFIE — 10-3 -> review en fin de PR]
```

**Hors scope (NE PAS toucher)** :
- `backend/app/graph/tools/*.py` (les tools — verrou story 10.1).
- `backend/app/graph/tool_selector*.py` (le selecteur — verrou story 10.2).
- `backend/app/prompts/*.py` (les prompts — verrou epic).
- `backend/app/graph/nodes.py` (les noeuds — verrou stories 10.1 + 10.2).
- Frontend.
- Modele LLM ou env vars (pas de basculement de modele dans cette PR — ca declencherait une nouvelle baseline).

### Anti-patterns a eviter (LLM dev mistakes)

1. **NE PAS** inventer `ask_qcu`, `ask_qcm`, `show_kpi_card`, `show_radar_chart`, `show_pie_chart` ou tout tool `show_*` — ils n'existent pas (verrou stories 10.1 + 10.2).
2. **NE PAS** utiliser `page_context` comme cle YAML — c'est `current_page` (verrou story 10.2).
3. **NE PAS** executer les tools (`ToolNode.invoke`) dans le runner — capture d'intent uniquement (sinon side effects DB).
4. **NE PAS** appeler `log_tool_call` reel dans l'eval — mocker (sinon insert tool_call_logs en base de test).
5. **NE PAS** oublier de declarer le marker `eval` dans `pytest.ini` — sinon `PytestUnknownMarkWarning` en CI.
6. **NE PAS** rendre le test `test_eval_runner.py` actif par defaut — il DOIT etre marque `@pytest.mark.eval` et skippe si pas d'API key.
7. **NE PAS** depasser 30 cas dans v1 — extension >50 cas est explicitement post-MVP (story 5 backlog, epic M10 §hors scope).
8. **NE PAS** ajouter de nouvelle dependance Python — PyYAML est deja installe ; sinon utiliser JSON pour le golden (mais YAML est explicite dans le planning AC).
9. **NE PAS** baser le gate >=90% sur 1 run — la baseline est informative, le gate est evalue en moyenne 3 runs (preciser dans le README).
10. **NE PAS** modifier la signature du selecteur, des tools, ou de `log_tool_call` — verrous stories 10.1/10.2.
11. **NE PAS** committer la cle API OpenRouter dans la baseline JSON ou le YAML — security.md.
12. **NE PAS** ecrire le rapport markdown ailleurs que stdout — la baseline JSON est versionnee intentionnellement, mais pas le rapport.

### Methodologie suggeree (TDD)

1. Ecrire 2-3 cas YAML representatifs (1 mutation, 1 question, 1 piege).
2. Ecrire le squelette `run_eval.py` qui lit le YAML, invoque LLM avec mock, capture tool_calls. RED.
3. Implementer la metrique `bon_tool` -> GREEN sur 3 cas.
4. Ajouter `payload_valide` + `payload_partial_match` -> GREEN.
5. Etendre a 30 cas YAML.
6. Implementer `--save-baseline`.
7. Ajouter le test pytest marker eval.
8. Lancer baseline, commit.

### Standards de tests (rappel)

- `pytest` + `pytest-asyncio` + `asyncio_mode=auto` (cf. `pytest.ini:2`).
- Marker existant : `unit`. Markers a ajouter : `eval`, `integration`.
- Activer le venv : `source backend/venv/bin/activate` avant `pytest` (cf. CLAUDE.md).
- Couverture minimale 80% — le runner lui-meme doit etre couvert par `test_eval_runner.py` (parsing YAML, calcul des metriques, subset match).

### Project Structure Notes

- `backend/tests/__init__.py` existe deja. Le sous-package `tests.llm_eval` est nouveau.
- `backend/tests/conftest.py` existe — verifier qu'il ne force pas une fixture DB qui contaminerait le runner eval (sinon scoper la fixture par dossier).
- `backend/scripts/` existe (story 10.2). On NE met PAS le runner ici — il est dans `tests/llm_eval/` pour cohabiter avec le golden set et beneficier des markers pytest.

### References

- `_bmad-output/planning-artifacts/module-10-tool-use-reliability/story-3-eval-set-30-cas.md` (lignes 28-77 : repartition origine, criteres ; **lecture critique** car repartition 30 cas a ete corrigee dans cette story — voir contexte §1).
- `_bmad-output/planning-artifacts/module-10-tool-use-reliability/epic.md` (lignes 64-86 : architecture cible ; lignes 88-96 : critere succes >=90%).
- `_bmad-output/implementation-artifacts/10-1-tool-descriptions-pydantic-strict.md` — schemas Pydantic stricts (utiliser pour `payload_valide`).
- `_bmad-output/implementation-artifacts/10-2-tool-filtering-by-page-context.md` — selecteur reutilise dans le runner ; mapping `PAGE_TOOL_MAPPING` reference pour le choix de `current_page` dans le YAML.
- `CLAUDE.md` § Active Technologies : 012 (32 tools), 013 (active_module), 015 (request_timeout=60), 018 (interactive widgets QCU/QCM/QCU_JUSTIFICATION/QCM_JUSTIFICATION).
- `~/.claude/rules/common/testing.md` — TDD + 80% coverage.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) via Claude Code CLI (bmad-create-story workflow).

### Debug Log References

- `pytest tests/llm_eval/ -m "not eval" -v` : 18/18 verts (parsing YAML, verrous M10, 4 metriques, serialisation baseline).
- `pytest backend/ -m "not eval" -q` : 1278 passed, 3 echecs PREEXISTANTS sur `test_guided_tour_*` (confirme via `git stash` : memes echecs avant le merge des changements story 10.3 — non lies, hors scope).
- `python -c "from app.main import app"` : OK, sans warning supplementaire.

### Completion Notes List

- **Catalogue de tools verifie** : `create_carbon_assessment` confirme dans `carbon_tools.py` ; aucune substitution de cas necessaire (cf. note Tache 1.2).
- **Verrous M10 valides cote runner** : `load_golden` leve `ValueError` sur `expected_tool` valant `ask_qcu`/`ask_qcm`/`ask_qcu_justification`/`ask_qcm_justification` (constante `_FORBIDDEN_TOOL_NAMES`) et sur tout `expected_tool` commencant par `show_`. Tests unitaires `test_load_golden_rejects_forbidden_ask_qcu` et `test_load_golden_rejects_show_prefix` couvrent ces deux verrous.
- **Le runner reutilise `select_tools_for_node` (story 10.2)** pour batir la liste vue par le LLM, identique a la prod ; pas d'`active_entities` (V1).
- **Aucun side-effect** : le runner appelle `_patch_no_side_effect()` qui transforme `log_tool_call` en no-op et `get_db_and_user` en stub levant une `RuntimeError`. Aucun `ToolNode.invoke` n'est jamais execute, on capture seulement `AIMessage.tool_calls`.
- **Baseline initiale (Tache 6)** : non generee dans cette session faute d'`OPENROUTER_API_KEY` accessible dans l'env. Etape OPERATOIRE pour le dev avant la PR :
  1. `export OPENROUTER_API_KEY=...` (ou source du .env local)
  2. `cd backend && source venv/bin/activate`
  3. `python -m tests.llm_eval.run_eval --save-baseline`
  4. Verifier `bon_tool_rate >= 0.90` et `fallback_text_rate <= 0.10`. Si ko, capturer le rapport stdout et investiguer avant la PR.
  5. `git add backend/tests/llm_eval/baselines/<YYYY-MM-DD>_<modele_slug>.json`
- **Note determinisme** : le seuil epic >=90% est verifie en moyenne sur 3 runs consecutifs (cf. README), pas sur 1.
- **Pas de modification interdite** : aucun tool, prompt, mapping selecteur, ou noeud LangGraph touche (verrous epic + stories 10.1/10.2 respectes).

### File List

Crees :
- `backend/tests/llm_eval/__init__.py`
- `backend/tests/llm_eval/golden_set_v1.yaml` (30 cas)
- `backend/tests/llm_eval/run_eval.py` (runner CLI + lib + 4 metriques + baseline JSON)
- `backend/tests/llm_eval/test_eval_runner.py` (17 tests `unit` + 1 test `eval`)
- `backend/tests/llm_eval/README.md`
- `backend/tests/llm_eval/baselines/.gitkeep`

Modifies :
- `backend/pytest.ini` (markers `eval` + `integration` ajoutes)
- `backend/app/graph/tools/README.md` (section « Eval set v1 — 30 cas (story 10.3) »)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (`10-3-eval-set-30-cas` : `ready-for-dev` → `in-progress` → `review`)

A creer hors session (operatif) :
- `backend/tests/llm_eval/baselines/<YYYY-MM-DD>_<modele_slug>.json` (cf. completion notes ci-dessus)

### Change Log

- 2026-04-29 : Story 10.3 contextualisee et passee en `ready-for-dev` (bmad-create-story). Repartition des 30 cas corrigee vs planning origine pour refleter la realite du catalogue de tools (verrous stories 10.1/10.2).
- 2026-04-29 : Implementation (bmad-dev-story). Arborescence `tests/llm_eval/` creee, golden set 30 cas, runner CLI deterministe (timeout 30s + retry 1x, defense en profondeur sur les side-effects DB), 17 tests unit + 1 test eval (skip auto sans API key), markers pytest declares, README + section graph/tools/README. 18/18 nouveaux tests verts ; 1278 verts au total ; 3 echecs preexistants `test_guided_tour_*` non lies. Status -> `review`. Baseline initiale + PR a executer hors-session avec `OPENROUTER_API_KEY`.
