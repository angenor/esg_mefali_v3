# Eval set v1 — Golden set 30 cas (story 10.3 / epic M10)

Mini eval-driven sur le tool-calling LLM : 30 cas
`(message_utilisateur, current_page) -> (tool_attendu, payload_attendu)`,
runner pytest deterministe, baseline JSON versionnee.

But : verifier objectivement qu'aucune modif de prompt, de tool description, de
modele LLM ou de mapping `tool_selector_config` ne fait regresser le tool-calling
en silence avant la demo MVP. Critere epic : **>=90% bon tool + payload valide**.

---

## Comment lancer

```bash
# Activer le venv
source backend/venv/bin/activate
cd backend

# 1. Run CLI rapide (rapport markdown stdout, exit code 0/1)
OPENROUTER_API_KEY=... python -m tests.llm_eval.run_eval

# 2. Run + ecriture baseline JSON dans tests/llm_eval/baselines/
OPENROUTER_API_KEY=... python -m tests.llm_eval.run_eval --save-baseline

# 3. Subset (debug)
python -m tests.llm_eval.run_eval --limit 5
python -m tests.llm_eval.run_eval --cases case_001,case_009,case_023

# 4. Via pytest (test marque @pytest.mark.eval, skippe par defaut)
OPENROUTER_API_KEY=... pytest -m eval tests/llm_eval/
```

Sans `OPENROUTER_API_KEY`, le test pytest est skippe (CI sans secret reste vert).

---

## Comment ajouter un cas

1. Ouvrir `tests/llm_eval/golden_set_v1.yaml`.
2. Copier le template ci-dessous a la fin du fichier.
3. Choisir un id `case_NNN` (3 chiffres zero-pad, sequentiel).
4. Remplir `notes:` avec ce que le cas verifie.

Template :

```yaml
- id: case_031
  message: "Le message de l'utilisateur en francais."
  current_page: "/profile"          # path Nuxt brut, ou null pour chat global
  node_name: "chat"                   # noeud LangGraph cible
  expected_tool: "update_company_profile"   # null si cas piege
  expected_payload_partial:           # ignore si expected_tool est null
    employee_count: 25
  accepted_alternatives:              # optionnel ; tools alternatifs juges acceptables
    - "get_company_profile"           # ex : LLM peut prudemment lire avant d'ecrire
  notes: "Pourquoi ce cas est interessant."
```

### Champ `accepted_alternatives` (optionnel)

Certains LLM modernes adoptent un workflow defensif (read-before-write,
clarify-before-act) qui produit un tool different de l'outil canonique
mais semantiquement valide. Pour eviter de surevaluer ces cas comme des
regressions, ajouter les outils alternatifs dans la liste.

Regles :

- Ne jamais y mettre un tool interdit (`ask_qcu`, `ask_qcm`, `show_*`).
- Ne jamais y dupliquer `expected_tool` (le runner leve `ValueError`).
- Un match via alternative compte comme `bon_tool=True` mais reste
  trace via `matched_alternative=True` dans le `CaseResult` et dans
  le baseline JSON. Le rapport markdown affiche `[dont N via accepted_alternatives]`.
- `payload_valide` et `subset_match` ne sont evalues QUE sur match exact
  de `expected_tool` (l'alternative a un schema different, donc on ne
  peut pas comparer).

Verifier ensuite que le golden charge bien :

```bash
pytest -m unit tests/llm_eval/test_eval_runner.py
```

---

## Verrous a respecter (CRITIQUE)

Plusieurs hypotheses du planning original sont fausses. Ne **pas** les
reintroduire :

1. **`ask_qcu` / `ask_qcm` n'existent PAS.** Il n'y a qu'**un** tool
   `ask_interactive_question` avec un champ `question_type:
   InteractiveQuestionType` (enum a 4 valeurs : `qcu`, `qcm`, `qcu_justification`,
   `qcm_justification`). Source : `app/schemas/interactive_question.py`,
   `app/graph/tools/interactive_tools.py`.
2. **`show_kpi_card`, `show_radar_chart`, `show_pie_chart`, `show_mermaid` n'existent
   PAS.** Les visualisations sont produites via blocs JSON inline + SSE
   markers, **pas** via tool call. Le runner LEVE une erreur si
   `expected_tool` commence par `show_`.
3. **Le champ s'appelle `current_page`** (pas `page_context`). Verrou story 10.2.
4. **Le LLM voit deja une liste filtree de tools** par `select_tools_for_node`
   (story 10.2). Le runner reutilise cette fonction — sans ca, faux negatifs
   systematiques.
5. **Aucun side-effect base.** Le runner mocke `get_db_and_user` + `log_tool_call`
   et n'invoque jamais `ToolNode` : on capture seulement
   `AIMessage.tool_calls` (intent).
6. **30 cas v1 max.** Extension >=50 cas est explicitement post-MVP (story 5
   backlog). Ne pas etendre dans cette story.

Le runner valide ces verrous au load (`load_golden`) et leve `ValueError`
explicite si on tente de les contourner.

---

## Limites

- **Determinisme imparfait.** `temperature=0` mais pas de seed garanti chez
  OpenRouter — un cas peut basculer "bon tool" / "texte libre" entre runs.
  Le seuil >=90% epic est donc verifie **en moyenne sur 3 runs consecutifs**,
  pas sur un seul.
- **Baseline = snapshot informatif.** Le fichier
  `baselines/<YYYY-MM-DD>_<modele_slug>.json` est versionne pour tracer la
  derive — il ne sert pas de gate dur. Les vrais gates :
  - `bon_tool_rate >= 0.90`
  - `fallback_text_rate <= 0.10`
- **Hash golden.** Le JSON baseline contient le SHA-256 du YAML au moment du
  run. Si le YAML change entre deux baselines, la comparaison directe n'est
  plus valide.
- **Pas d'execution de tool.** On verifie la **selection** + le **payload
  Pydantic** ; aucun appel a la base, aucune mutation. C'est volontaire (eval
  offline, sans Postgres).
- **UUIDs dans payload.** Pour `create_fund_application`, `batch_save_esg_criteria`,
  l'argument requiert un UUID que le LLM ne peut pas inventer pour la cible
  reelle. `expected_payload_partial` reste vide pour ces cas — le test
  `payload_valide` (Pydantic strict) reste pertinent et echouera volontairement
  si le LLM ne respecte pas le format UUID.
- **Pas de system prompt.** Le runner appelle
  `llm.bind_tools(filtered).ainvoke([HumanMessage(case.message)])` SANS le
  system prompt module (cf. `app/prompts/*.py`) qui en prod injecte
  `WIDGET_INSTRUCTION`, le role specialise, et les instructions explicites
  d'appel d'outil. Consequence : l'eval mesure la **selection de tools + le
  format de payload** sur le message brut, pas la performance de bout-en-bout
  observee par l'utilisateur. Un `bon_tool_rate` <90% en single-run n'est donc
  pas necessairement une regression de prod — c'est aussi une mesure de la
  capacite du LLM a inferer l'intent sans prompt. Le gate epic >=90%
  (moyenne 3 runs) est documente comme **aspirational**, pas blocking.
- **Gate CI single-run relache.** Le test pytest `test_golden_set_meets_baseline`
  utilise `_CI_BON_TOOL_MIN=0.85` et `_CI_FALLBACK_MAX=0.15` pour eviter de
  faire tomber CI sur le bruit de determinisme. Le rapport markdown stdout
  conserve le gate strict 90%/10% pour signal humain.

---

## Architecture du runner

```
golden_set_v1.yaml
       |
       v
load_golden() -- valide les verrous M10
       |
       v
_invoke_llm_for_case() -- get_llm() + bind_tools(filtered) + ainvoke
       |   (timeout 30s, retry 1x, jamais ToolNode.invoke)
       v
_evaluate_case() -- 4 metriques :
       - bon_tool        : nom du 1er tool_call == expected_tool (ou texte libre si null)
       - payload_valide  : Pydantic args_schema(**args) ne leve pas
       - subset match    : tous les champs expected_payload_partial == args[k]
       - fallback_texte  : tool_calls vide alors qu'on attendait un tool
       v
render_report()       -- markdown stdout (exit code 0/1)
       v
serialize_baseline()  -- JSON dans baselines/<date>_<modele>.json
                         (uniquement si --save-baseline)
```
