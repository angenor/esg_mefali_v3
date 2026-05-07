# Feature Specification: F22 — Decision Tree dans System Prompt + with_retry Effectif + Golden Set 50 cas

**Feature Branch**: `feat/F22-decision-tree-with-retry-eval`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "F22 — decision tree explicite + with_retry/fallback + golden set 50 cas + standardisation 10 docstrings + métriques validation"

## Clarifications

### Session 2026-05-07

- **Périmètre tools `@with_retry`** : 11 tools de mutation critique (la fiche en cite 12 mais `update_application_status` n'est pas exposé en tool LangChain — c'est une fonction service interne). Le tool `generate_attestation` (F08) n'est pas encore exposé comme tool LangChain, il est documenté pour activation future ; il sera décoré dès qu'il sera ajouté à un `*_TOOLS` group.
- **Standardisation docstrings** : les 10 docstrings restantes correspondent aux groupes `chat_tools` (4 tools), `carbon_tools` (4 tools), `financing_tools` (7 tools), `credit_tools` (3 tools), `action_plan_tools` (3 tools), `document_tools` (3 tools), `guided_tour_tools` (1 tool). Soit 25 tools à aligner sur le gabarit 5 sections (le chiffre « 10 » dans la fiche F22 est le nombre de groupes/fichiers, pas de tools individuels). Décision : toutes les docstrings de TOUS les tools doivent passer le test de conformité (déjà vert pour les 26 tools du périmètre 10.1 + F10 + F13).
- **Golden set 50 cas** : créé dans `backend/tests/llm_eval/golden_set.json` (nouveau fichier, distinct de `golden_set_50.json` qui appartient à F01 et reste tel quel). Le fichier F01 existant est conservé sans modification.
- **Test runner LLM eval** : marqueur `pytest.mark.eval` (NON intégré au run par défaut), exécuté manuellement ou en CI sur changement de prompts/tools (déclencheur `pyproject.toml` config + tag `slow`/`expensive`). Cache LLM responses possible via `pytest-recording` ou cassette (hors-scope phase 1, run unique en CI).
- **Migration Alembic 032** : ajoute `validation_error: jsonb | null` à `tool_call_logs`. `down_revision="031_extend_interactive_questions"`, `revision="032_add_validation_error_tool_call_logs"`. La colonne `retry_count` existe déjà (cf. `54432e29b7f3_add_tool_call_logs_table.py` + révisions postérieures).
- **Endpoint admin `/api/admin/metrics/validation-failures`** : protégé par rôle Admin (F02 multitenant), retourne agrégation hebdomadaire des échecs validation avec taux et top 10 tools concernés. Garde-fou : taux d'échec < 5 % par défaut, alerte si dépassement.
- **Metrics SC** : taux bon tool > 90 % (P1), payload valide > 95 % (P1), taux hallucination < 1 % (P1), taux fallback < 2 % (P2). Ces métriques sont calculées par le test runner et écrites dans un rapport JSON `eval-report.json`.
- **CI conditionnel** : un step GitHub Actions exécute `pytest tests/llm_eval/ -m eval --golden-report=eval-report.json` uniquement si le diff PR touche `app/prompts/**`, `app/graph/tools/**` ou `tests/llm_eval/golden_set.json` (path-filter). Sinon le job est skippé pour éviter la consommation LLM excessive.
- **Decision tree dans `app/prompts/system.py`** : nouvelles constantes `DECISION_TREE` et `ANTI_PATTERNS` injectées dans `BASE_PROMPT` après le bloc « ARBRE DE DÉCISION VISUALISATION (F11) » existant. La structure est PRÉSERVÉE : on n'écrase rien, on ajoute. Le budget tokens est gated par `_tokens_baseline.json` (gate +25 % max — voir Risques).
- **`with_retry` paramétrable** : signature étendue avec `fallback_message: str | None = None`. Quand le retry échoue ET qu'un `fallback_message` est fourni, le tool retourne un JSON `{"success": False, "fallback_message": "<message>"}` sérialisé. Sinon (cas `chat_tools`/`document_tools` non destructifs), comportement actuel conservé (`f"Erreur : {e}"`).

## User Scenarios & Testing

### User Story 1 — Decision Tree explicite dans le system prompt (Priority: P1)

En tant qu'**Architecte de la plateforme**, je veux que le system prompt contienne un arbre de décision explicite « Question fermée ? → tool ask_* », « Visualisation utile ? → tool typé », « Mutation métier ? → tool d'action + confirmation destructive », « Chiffre ? → JAMAIS sans cite_source ». Cela force le LLM à choisir le bon tool plutôt que de produire du texte libre ou un fence markdown générique.

**Why this priority** : sans arbre de décision explicite, le LLM dégrade silencieusement la qualité du tool calling (mauvais tool, payload texte, oubli de `cite_source`). L'arbre de décision réduit immédiatement le taux d'erreur sans coût d'infrastructure.

**Independent Test** : peut être validé en lançant 50 cas du golden set et en vérifiant que le tool attendu est invoqué dans > 90 % des cas. Si l'arbre de décision est désactivé (rollback du prompt), le taux dégrade.

**Acceptance Scenarios** :

1. **Given** le system prompt contient `DECISION_TREE` et `ANTI_PATTERNS`, **When** un utilisateur écrit « Quel est mon score ESG ? », **Then** le LLM invoque `show_kpi_card` (et non un fence markdown générique `gauge`).
2. **Given** un utilisateur écrit « Supprime ce projet », **When** le LLM répond, **Then** il invoque d'abord `ask_yes_no(destructive=True)` avant tout `delete_project`.
3. **Given** le LLM doit annoncer un chiffre métier (« le facteur d'émission diesel est 2,68 kgCO2e/L »), **When** il rédige sa réponse, **Then** il invoque `cite_source(source_id)` ou `flag_unsourced(claim, reason)` AVANT toute affirmation.
4. **Given** le système doit chaîner plusieurs tools (cite_source + show_kpi_card + show_pie_chart + ask_qcu), **When** la réponse est riche, **Then** le LLM invoque les tools dans l'ordre du chaînage documenté (et non un seul gros message texte).

---

### User Story 2 — `with_retry` effectif avec fallback explicite (Priority: P1)

En tant qu'**Architecte**, je veux que `with_retry` soit décoré sur les tools de mutation critique (~11 tools) : si le LLM produit un payload invalide (Pydantic ValidationError ou exception runtime), le système retry 1x, et si le retry échoue, retourne un fallback texte structuré au lieu d'une erreur opaque. Cela évite que des erreurs Pydantic remontent dans le chat utilisateur sous forme de stack trace.

**Why this priority** : sans `with_retry` actif, une erreur de payload remonte directement, dégrade l'UX et ne donne pas au LLM la chance de corriger. Le retry+fallback est un filet de sécurité standard pour les tools de mutation.

**Independent Test** : pour chaque tool décoré, simuler une exception `ValidationError` au premier appel (mock) et vérifier que (a) un second appel est tenté, (b) si le second échoue, la réponse contient `{"success": False, "fallback_message": "..."}`, (c) `tool_call_logs` enregistre `retry_count=1` et `validation_error` (jsonb) si applicable.

**Acceptance Scenarios** :

1. **Given** le tool `update_company_profile` est invoqué avec un payload manquant `sector`, **When** il échoue avec `ValidationError`, **Then** un retry est tenté avec contexte d'erreur, et si le retry échoue, le tool retourne `{"success": False, "fallback_message": "Je n'arrive pas à formaliser cette mise à jour de profil. Pouvez-vous me reformuler ?"}`.
2. **Given** le tool `delete_project` (F06) est invoqué sans `confirm=True`, **When** le service détecte le besoin de confirmation, **Then** le tool retourne le marker `requires_destructive_confirmation` (comportement F10 préservé) — `with_retry` n'interfère pas avec ce flux.
3. **Given** un tool décoré `@with_retry` réussit du premier coup, **When** il est journalisé, **Then** `retry_count=0`, `status="success"`, `validation_error=null`.
4. **Given** un tool décoré `@with_retry` réussit au second essai, **When** il est journalisé, **Then** `retry_count=1`, `status="retry_success"`, `validation_error` contient l'erreur du premier essai.

---

### User Story 3 — Standardisation docstrings 5 sections (tous tools) (Priority: P2)

En tant qu'**Architecte**, je veux que TOUS les tools (26 + 7 nouveaux F01/F06/F11/F12 = ~39 tools) aient une docstring conforme au gabarit 5 sections (verbe / Use when / Don't use when / Exemple / Anti). Cela améliore la qualité du tool selection (LLM lit la description) et homogénéise la base.

**Why this priority** : les 14 docstrings au gabarit (story 10.1) ont prouvé l'efficacité. Les 25 docstrings restantes au format ancien dégradent la cohérence et affaiblissent le tool selection sur ces modules (carbone, financement, crédit, action plan, etc.).

**Independent Test** : exécuter `test_all_tools_conform_to_5_sections` et vérifier que tous les tools de TOUS les groupes passent. Si un seul tool est non conforme, le test échoue avec le nom du tool.

**Acceptance Scenarios** :

1. **Given** tous les tools sont importés, **When** on exécute le test conformity étendu, **Then** chaque tool a `Use when:`, `Don't use when:`, `Exemple:`, `Anti:` dans sa description, longueur >= 200 caractères, verbe d'action initial >= 10 caractères.
2. **Given** un nouveau tool est ajouté sans docstring conforme, **When** la CI exécute le test conformity, **Then** le test échoue avec un message clair indiquant le tool manquant.

---

### User Story 4 — Golden Set 50 cas + métriques eval (Priority: P1)

En tant qu'**Architecte**, je veux un golden set de 50 cas (message utilisateur + contexte page → tool attendu + payload contains) qui s'exécute en CI à chaque changement de prompt/tool. Métriques : taux bon tool > 90 %, taux payload valide > 95 %, taux hallucination < 1 %.

**Why this priority** : sans golden set, on ne détecte pas les régressions de tool selection lors d'un changement de prompt ou d'un upgrade modèle. C'est le filet de sécurité qualitatif principal.

**Independent Test** : lancer `pytest tests/llm_eval/ -m eval --golden-report=eval-report.json` localement et vérifier les métriques dans le rapport JSON. Le test échoue si taux bon tool < 90 % ou payload valide < 95 %.

**Acceptance Scenarios** :

1. **Given** 50 cas annotés (10 profilage + 8 ESG + 6 carbone + 6 financement + 6 applications + 5 crédit + 4 plan + 5 conversationnels), **When** le test runner exécute le graph LangGraph pour chaque cas, **Then** un rapport JSON est produit avec les métriques agrégées et la liste des cas en échec.
2. **Given** un changement de prompt augmente le taux d'erreur de tool selection à 15 %, **When** la CI exécute le golden set, **Then** le job échoue (gate 90 %) et bloque le merge.
3. **Given** un cas accepte plusieurs tools valides (whitelist), **When** le LLM en choisit un autorisé, **Then** le cas est compté comme succès (matching tolérant).

---

### User Story 5 — Logging échecs validation + endpoint admin (Priority: P2)

En tant qu'**Admin de la plateforme**, je veux qu'un endpoint `/api/admin/metrics/validation-failures` agrège les échecs de validation tools (par jour/semaine/tool) pour identifier les patterns récurrents et alerter quand un tool dépasse 5 % d'échec.

**Why this priority** : sans visibilité, on ne détecte pas les tools dont la définition est imprécise (LLM échoue souvent) ou les régressions modèle. Le tracking permet itération continue.

**Independent Test** : appeler `GET /api/admin/metrics/validation-failures?period=7d` avec rôle Admin et vérifier que la réponse contient `{"total_calls": int, "failure_count": int, "failure_rate": float, "top_tools": [...]}`.

**Acceptance Scenarios** :

1. **Given** la table `tool_call_logs` contient 1000 appels dont 50 avec `validation_error != null`, **When** un Admin appelle l'endpoint sur 7 jours, **Then** la réponse contient `failure_rate=0.05` et le top 5 des tools concernés.
2. **Given** un user non-Admin appelle l'endpoint, **When** la requête arrive, **Then** elle est rejetée avec 403.
3. **Given** la colonne `validation_error` est nulle pour un succès, **When** on agrège, **Then** seuls les enregistrements `validation_error != null` sont comptés comme échec.

---

### Edge Cases

- **Decision tree trop verbeux** : si l'arbre dépasse +25 % de tokens, le test `_tokens_baseline.json` échoue → forcer une révision du prompt.
- **Conflit `with_retry` + `requires_destructive_confirmation`** : le flux destructif F10 retourne le marker SANS lever d'exception → `with_retry` ne déclenche pas de retry inutile (le retour est un succès au sens du décorateur).
- **Cas golden ambigus** : un message comme « ok » peut être interprété comme `ask_yes_no` ou simple acknowledgment textuel. Solution : whitelist par cas (plusieurs tools valides acceptés).
- **Golden set drift** : quand un tool est renommé/supprimé, certains cas du golden set deviennent invalides → process documenté pour mise à jour, review obligatoire à chaque PR qui change un tool.
- **Modèle LLM upgrade** : un upgrade modèle peut changer le tool selection. Le golden set est exécuté en CI sur changement de modèle aussi (variable d'env `LLM_MODEL` dans path-filter).
- **Coût LLM** : 50 cas × ~500 tokens × prix Claude = ~$2 par run. CI conditionnel + cassettes cache pour réduire coût.
- **Fallback non destructif** : pour les tools `chat_tools`/`document_tools` qui ne sont pas critiques, on garde le comportement actuel (`Erreur : {e}`) sans fallback structuré pour éviter sur-ingénierie.
- **Migration 032 backward compatible** : la colonne `validation_error` est nullable et default null → pas de migration de données, deploy zero-downtime.

## Requirements

### Functional Requirements

- **FR-001** : Le system prompt MUST contenir une section `DECISION_TREE` listant les règles obligatoires (5 sections : Question fermée, Visualisation utile, Mutation métier, Affirmation factuelle, Chaînage de tools).
- **FR-002** : Le system prompt MUST contenir une section `ANTI_PATTERNS` listant 5 anti-exemples explicites (chiffre sans cite_source, question fermée en texte libre, delete sans confirmation, radar pour 1 chiffre, modification du catalogue).
- **FR-003** : Le décorateur `with_retry` MUST accepter un paramètre `fallback_message: str | None = None` ; si fourni et le retry échoue, retourner `{"success": False, "fallback_message": "..."}` sérialisé en JSON.
- **FR-004** : 11 tools de mutation critique MUST être décorés `@with_retry(max_retries=1, fallback_message="...")` : `update_company_profile`, `batch_save_esg_criteria`, `finalize_esg_assessment`, `finalize_carbon_assessment`, `create_fund_application`, `generate_credit_score`, `generate_action_plan`, `update_action_item`, `update_project` (F06), `delete_project` (F06), `generate_credit_certificate` (F22 ajout — proxy attestation pour F08 future).
- **FR-005** : Toutes les docstrings de TOUS les tools (26 + ~7 nouveaux issus F01/F06/F11/F12) MUST passer le test conformity étendu (5 sections, longueur >= 200, verbe d'action, etc.).
- **FR-006** : Le test conformity `test_tools_meta_conformity.py` MUST être étendu pour couvrir TOUS les groupes de tools (`SCOPE_TOOLS = INTERACTIVE + PROFILING + ESG + APPLICATION + CHAT + CARBON + FINANCING + CREDIT + ACTION_PLAN + DOCUMENT + GUIDED_TOUR + SOURCING + PROJECT + VISUALIZATION + MEMORY`).
- **FR-007** : Un nouveau fichier `backend/tests/llm_eval/golden_set.json` MUST contenir 50 cas annotés au schéma `{id, context: {current_page, active_module}, user_message, expected: {tool_called, payload_contains}}` — avec répartition 10/8/6/6/6/5/4/5.
- **FR-008** : Un nouveau fichier `backend/tests/llm_eval/test_eval_runner.py` MUST exposer un test paramétré `@pytest.mark.eval @pytest.mark.parametrize("case", load_golden_set())` qui invoque le graphe et compare le tool appelé + payload subset.
- **FR-009** : Le test runner MUST produire un rapport JSON `eval-report.json` (option `--golden-report`) avec métriques agrégées : `tool_match_rate`, `payload_valid_rate`, `hallucination_rate`, `fallback_rate`, et liste des cas en échec avec diff.
- **FR-010** : Une migration Alembic `032_add_validation_error_tool_call_logs.py` (revision=`032_add_validation_error_tool_call_logs`, down_revision=`031_extend_interactive_questions`) MUST ajouter une colonne `validation_error: jsonb | null` à la table `tool_call_logs`.
- **FR-011** : Un endpoint REST `GET /api/admin/metrics/validation-failures` MUST retourner l'agrégation des échecs (period=24h|7d|30d, default 7d), protégé par rôle Admin (F02), avec format `{"period": str, "total_calls": int, "failure_count": int, "failure_rate": float, "top_tools": [{tool_name, count, rate}]}`.
- **FR-012** : Le pipeline CI MUST exécuter `pytest tests/llm_eval/ -m eval` UNIQUEMENT si le diff PR touche `app/prompts/**`, `app/graph/tools/**` ou `tests/llm_eval/**` (path-filter GitHub Actions).
- **FR-013** : Une documentation `docs/llm-eval-loop.md` MUST décrire le process (ajouter un cas, calculer les métriques, interpréter le rapport, déclencher manuellement) — créée si absente.
- **FR-014** : Le matching golden set MUST être tolérant : un cas peut accepter une whitelist de tools valides (ex. `expected.tool_called: ["ask_yes_no", "ask_qcu"]`), et le payload comparison utilise `subset_match` (clés-valeurs présentes, autres ignorées).
- **FR-015** : `tool_call_logs.validation_error` MUST être peuplé quand `with_retry` capture une `pydantic.ValidationError` (sérialisée via `e.errors()`), null sinon.

### Key Entities

- **Decision tree (constante Python)** : bloc texte multi-sections injecté dans `BASE_PROMPT` après le bloc F11. Composants : `DECISION_TREE`, `ANTI_PATTERNS`. Pas de persistence — c'est un literal Python.
- **Golden case (JSON)** : `{id: str, context: {current_page: str | null, active_module: str | null}, user_message: str, expected: {tool_called: str | list[str], payload_contains: dict, fallback_acceptable?: bool}, tags?: list[str]}`. 50 entrées dans `golden_set.json`.
- **Eval report (JSON)** : `{run_id, started_at, completed_at, total_cases, results: [{case_id, status: pass|fail|partial, actual_tool, expected_tool, payload_diff, latency_ms}], metrics: {tool_match_rate, payload_valid_rate, hallucination_rate, fallback_rate}}`.
- **`tool_call_logs.validation_error`** : `jsonb | null`. Contient le résultat de `pydantic.ValidationError.errors()` (liste de dicts `{loc, msg, type}`) quand le retry échoue ou succède au 2e essai. Null pour les succès du premier coup.

## Success Criteria

### Measurable Outcomes

- **SC-001** : Taux de bon tool sur le golden set 50 cas > 90 % (mesure : nombre de cas où `actual_tool == expected_tool` ou ∈ whitelist) — gate CI bloquant.
- **SC-002** : Taux de payload valide sur le golden set > 95 % (mesure : `subset_match(actual_payload, expected.payload_contains)` retourne True) — gate CI bloquant.
- **SC-003** : Taux d'hallucination (tool inexistant invoqué) < 1 % — gate CI bloquant.
- **SC-004** : Taux de fallback (`with_retry` retourne `{"success": False, ...}`) sur les 11 tools décorés < 2 % — métrique de monitoring (alerte mais pas blocage).
- **SC-005** : 100 % des tools (39 estimés) passent le test conformity étendu.
- **SC-006** : Augmentation du nombre de tokens du system prompt < 25 % par rapport au baseline `_tokens_baseline.json` — gate testable.
- **SC-007** : 0 régression sur les ~935 tests backend existants (run pytest complet).
- **SC-008** : Endpoint admin `/api/admin/metrics/validation-failures` répond < 500ms en P95 sur un dataset de 100k logs.
- **SC-009** : Couverture tests >= 80 % sur les nouveaux modules (`with_retry` extension, `test_eval_runner`, endpoint admin).

## Assumptions

- L'environnement CI dispose d'une clé API LLM (variable `OPENROUTER_API_KEY`) avec un budget mensuel suffisant pour ~10-20 runs golden set par mois.
- Le modèle LLM cible est documenté dans `app/core/config.py` (constante `LLM_MODEL`) et le golden set est calibré pour ce modèle. Tout changement de modèle nécessite re-calibration.
- Les tools `update_application_status` (mentionné fiche F22) et `generate_attestation` (F08) ne sont PAS encore exposés comme tools LangChain — ils restent service-only. Le décorateur `with_retry` sera appliqué dès qu'ils seront promus en tools (hors-scope F22).
- Le rôle Admin existe déjà via F02 (`019_multitenant_and_roles.py`) et la dépendance FastAPI `require_admin_role()` est disponible.
- La table `tool_call_logs` existe et contient déjà `retry_count`, `tools_offered`, `status` (depuis `54432e29b7f3` + `10b2_add_tools_offered`).
- Les tests existants (`test_tools_meta_conformity.py`) restent verts — l'extension ajoute des tools au scope sans casser les assertions actuelles.
- Le matching tolérant golden set (whitelist tools acceptables) permet d'accepter les cas où le LLM choisit un tool synonyme valide (ex. `ask_qcu` au lieu de `ask_select` pour 5 options).
- Le path-filter GitHub Actions est supporté par le runner CI (déjà actif sur le projet).
- L'ajout d'une colonne nullable à `tool_call_logs` est zero-downtime sur PostgreSQL 16 (table volumétrie modérée < 10M rows attendu).
