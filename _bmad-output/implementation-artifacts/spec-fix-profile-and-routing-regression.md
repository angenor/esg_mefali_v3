---
title: 'Fix profilage non-persistant + routage ESG bloqué'
type: 'bugfix'
created: '2026-04-30'
status: 'done'
baseline_commit: 17dc29031cadd3d4757872eca7e448e2b397d40d
slug: fix-profile-and-routing-regression
parent_e2e_evidence: _bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/profil-esg-complet/REPORT.md
related_spec: _bmad-output/implementation-artifacts/spec-fix-esg-scoring-node-routing.md
related_pr: "#4"
branch: fix/esg-scoring-node-routing
context:
  - backend/app/graph/nodes.py
  - backend/app/graph/tool_selector_config.py
  - backend/app/graph/tools/profiling_tools.py
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Le run E2E `agent-browser --headed` du 2026-04-30 sur la branche `fix/esg-scoring-node-routing` (PR #4) révèle deux régressions bloquant le merge : (1) un message dense de profilage (« Moussa SARL, agroalimentaire, Dakar, 18 personnes, 85 M FCFA, ODD 8/12/13 ») n'appelle jamais `update_company_profile` et le profil reste à 6 % ; (2) « lance mon évaluation ESG » est routé vers `chat_node` au lieu de `esg_scoring_node`, alors que `_detect_esg_request` retourne `True` en isolation.

**Approach:** Restaurer le parcours user de bout en bout (inscription → profilage persisté → demande ESG → routage `esg_scoring_node` → 30 critères → finalisation) via trois correctifs ciblés : (a) renforcer les `profiling_instructions` du chat_node pour forcer l'appel de `update_company_profile`, (b) instrumenter `router_node` (logs DEBUG) pour identifier la cause du mauvais routage puis poser la garde appropriée, (c) ajouter tests unitaires + intégration verrouillant la séquence.

## Boundaries & Constraints

**Always:**
- Conserver l'anti-boucle widget ESG existant (spec parent `spec-fix-esg-scoring-node-routing.md`, AC10). Les tests `test_esg_router.py`/`test_esg_routing.py` doivent rester verts.
- Tronquer toute donnée utilisateur loggée à 80 chars (RGPD défense en profondeur).
- `LOG_LEVEL` par défaut reste `INFO` en prod ; les logs DEBUG du routeur ne sont actifs qu'en dev/test.
- Test négatif obligatoire : « lance mon évaluation ESG » seul ne doit PAS appeler `update_company_profile`.

**Ask First:**
- Si T1 (diagnostic Bug 2) révèle qu'il faut modifier l'ordre de priorité dans la classification du routeur d'une manière qui pourrait affecter d'autres modules (carbon, financing, application, credit, action_plan).
- Si le fix nécessite une migration de schéma BDD ou une modification du checkpointer.

**Never:**
- Refonte du prompt système global (juste ajustements ciblés sur `_build_profiling_instructions`).
- Migration vers un checkpointer Postgres (MemorySaver actuel reste).
- Refactor du système `active_module` (juste correctifs ciblés et instrumentation).
- AC8 dark mode (déjà couvert ailleurs).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Profilage dense | Message « Moussa SARL, agroalimentaire, Dakar, 18 personnes, 85 M FCFA, ODD 8/12/13 », profil à 6 % | Tool `update_company_profile` appelé avec `sector`, `city`, `country`, `employee_count=18`, `annual_revenue_xof=85000000` ; row `tool_call_logs` avec `status='success'` ; `_compute_identity_completion ≥ 70` | Si LLM ne call pas le tool : test échoue (régression) |
| Demande ESG après profilage | Profil ≥ 70 %, message « lance mon évaluation ESG » | `_route_esg=True` ; `esg_scoring_node` exécuté ; row `esg_assessments` créée (`status='draft'` puis `'in_progress'`) ; `tool_call_logs` avec `tool_name='create_esg_assessment'`, `status='success'` | N/A |
| Demande ESG seule (test négatif) | Profil incomplet, message « lance mon évaluation ESG » seul | `update_company_profile` NON appelé ; routage vers `esg_scoring_node` | N/A |
| Multi-tours profilage→ESG | Tour 1 profilage dense, tour 2 « lance ESG » | Au tour 2 : `state['_route_esg']==True`, `tool_call_logs` contient les deux tool calls (profile + ESG) | N/A |

</frozen-after-approval>

## Code Map

- `backend/app/graph/nodes.py` -- `router_node` (l. 482-614), `chat_node` (l. 1353-1447), `_build_profiling_instructions` (l. 445), `_compute_identity_completion` (l. 434), `_detect_esg_request` (l. 293), `_has_active_esg_assessment` (l. 421), `_has_unresolved_esg_widget_signal` (l. 330)
- `backend/app/graph/tools/profiling_tools.py` -- tool `update_company_profile` (l. 53), description et schéma Pydantic
- `backend/app/graph/tool_selector_config.py` -- `PAGE_TOOL_MAPPING['chat_global']` et `MODULE_TOOL_MAPPING['chat']` exposent déjà `update_company_profile` (vérifié)
- `backend/tests/test_router_node.py` -- tests unitaires existants du routeur (extension)
- `backend/tests/test_chat_profiling.py` -- tests unitaires profiling chat (extension)
- `backend/tests/test_esg_router.py`, `backend/tests/test_esg_routing.py` -- garantir non-régression anti-boucle widget
- `backend/tests/test_graph/` -- répertoire pour le nouveau test d'intégration
- `backend/tests/conftest.py` -- fixtures pytest existantes (LLM stub, DB session)
- `_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/profil-esg-complet/REPORT.md` -- evidence E2E du run échoué

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/graph/nodes.py` -- ajouter logs DEBUG dans `router_node` (`last_user_msg[:80]`, `is_esg_request`, `active_module`, `has_active_esg`, `_route_esg`, `is_continuation`) -- diagnostic Bug 2 + AC4
- [x] Reproduire E2E avec `LOG_LEVEL=DEBUG`, capturer le trace, identifier la cause exacte (active_module persistant ? has_active_esg fantôme ? autre flag ?) -- input du fix T2 *(diagnostic réalisé par lecture statique du code : cf. Spec Change Log)*
- [x] `backend/app/graph/nodes.py` -- appliquer le fix Bug 2 selon résultat T1 (garde « si `_detect_esg_request(last_user_msg)` ET `not has_active_esg` ET `active_module != 'esg_scoring'` ALORS forcer reset `active_module=None` AVANT la branche continuation »)
- [x] `backend/app/graph/nodes.py::_build_profiling_instructions` -- renforcer pour exiger explicitement « Tu DOIS appeler `update_company_profile` avec tous les champs détectés AVANT de répondre » -- fix Bug 1
- [x] `backend/tests/test_router_node.py` -- ajouter test `test_esg_priority_after_chat_turn` + `test_router_debug_logs`
- [x] `backend/tests/test_chat_profiling.py` -- ajouter test `test_chat_profiling_tool_call_dense_message` + test négatif `test_chat_no_profile_call_on_esg_request`
- [x] `backend/tests/test_graph/test_profile_to_esg_routing.py` (NEW) -- test intégration pytest-asyncio sur la séquence (profilage→ESG)
- [x] `_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/profil-esg-complet/REPORT.md` -- note datée 2026-04-30 ajoutée
- [ ] Cleanup DB via `/tmp/cleanup-moussa1.sql` puis re-run agent-browser session `profil-esg-complet-v2` sur les 8 ACs originaux *(à effectuer manuellement par l'humain — pas d'accès navigateur headed côté Claude CLI)*

**Acceptance Criteria:**
- Given un utilisateur authentifié avec profil à 6 %, when il envoie le message dense de profilage, then une row `tool_call_logs` existe avec `node_name='chat'`, `tool_name='update_company_profile'`, `status='success'`, ET `company_profiles` contient `sector`, `employee_count=18`, `country='Senegal'`, `city='Dakar'`, `annual_revenue_xof=85000000`, ET `_compute_identity_completion ≥ 70` (AC1).
- Given un utilisateur dont le profil est ≥ 70 % et un tour précédent de profilage, when il envoie « lance mon évaluation ESG », then `_route_esg=True`, le nœud suivant est `esg_scoring_node`, une row `esg_assessments` est créée (`status` `draft`→`in_progress`), `tool_call_logs` contient `node_name='esg_scoring'`, `tool_name='create_esg_assessment'`, `status='success'` (AC2).
- Given le test `tests/test_graph/test_profile_to_esg_routing.py`, when on exécute la séquence, then il passe avec `state['_route_esg']==True` au tour 2 ET `tool_call_logs` contient les deux appels attendus (AC3).
- Given `LOG_LEVEL=DEBUG`, when `router_node` s'exécute, then un log DEBUG par tour avec les 6 champs requis est émis (AC4).
- Given la suite de tests existante (935 tests), when on exécute `pytest`, then aucune régression (en particulier `test_esg_router.py` et `test_esg_routing.py` restent verts, R1).
- Given le test négatif, when on envoie « lance mon évaluation ESG » seul (sans contexte profilage), then `update_company_profile` n'est PAS appelé (R2).

## Design Notes

**Hypothèse Bug 2 (à confirmer par T1) :** `chat_node` ne définit PAS `active_module` (vérifié l. 1353-1447), donc l'`active_module` reste `None` entre le tour 1 (profilage) et le tour 2 (ESG). Le routeur devrait alors classer normalement et `is_esg_request=True` ⇒ `_route_esg=True`. Causes possibles à instrumenter :
- `_has_active_esg_assessment(state)` retourne `True` à cause d'un assessment fantôme (état orphelin du run précédent).
- `_has_unresolved_esg_widget_signal` déclenche le forçage anti-boucle, mais quelque chose d'autre invalide ensuite la décision.
- `has_document=True` (artefact d'un upload) qui prend priorité dans `_route_after_router` (à vérifier).

**Renforcement `_build_profiling_instructions` (golden example) :**
```python
"INSTRUCTIONS PROFILAGE — IMPÉRATIF :\n"
"Le profil de l'entreprise est incomplet ({pct}%). Si le message utilisateur "
"contient des informations factuelles (nom, secteur, ville, pays, effectif, "
"chiffre d'affaires, année de création, ODD ciblés), tu DOIS appeler le tool "
"`update_company_profile` avec tous les champs détectés AVANT toute autre "
"réponse. Ne réponds JAMAIS uniquement en texte si des champs sont extractibles."
```

## Verification

**Commands:**
- `cd backend && source venv/bin/activate && pytest tests/test_router_node.py tests/test_chat_profiling.py tests/test_graph/test_profile_to_esg_routing.py -v` -- expected: tous verts
- `cd backend && pytest --maxfail=1 -q` -- expected: 935+ tests verts, zero régression
- `cd backend && pytest tests/test_esg_router.py tests/test_esg_routing.py -v` -- expected: anti-boucle widget intact
- `LOG_LEVEL=DEBUG cd backend && pytest tests/test_router_node.py::test_router_debug_logs -v -s` -- expected: 6 champs présents dans la sortie

**Manual checks:**
- E2E agent-browser : re-run de la session `profil-esg-complet-v2` doit atteindre `esg_assessments.status='completed'` avec 4 scores non-null + 30 critères. Vérifier `REPORT.md` mis à jour avec verdicts ✅ sur AC1-AC8 du run E2E parent.
- CI verte sur PR #4.

## Suggested Review Order

**Garde défensive routeur (Bug 2)**

- Entry point — la garde qui force le reset `active_module` quand l'intention ESG est explicite et qu'aucune évaluation n'est en cours.
  [`nodes.py:520`](../../backend/app/graph/nodes.py#L520)

- Branche continuation : retour précoce avec log DEBUG des 6 champs (AC4) pour observabilité.
  [`nodes.py:560`](../../backend/app/graph/nodes.py#L560)

- Classification normale : log DEBUG final + retour avec `_route_esg=True` après reset.
  [`nodes.py:642`](../../backend/app/graph/nodes.py#L642)

**Renforcement profilage (Bug 1)**

- Chaîne impérative « DOIS appeler `update_company_profile` AVANT toute autre réponse » — fix du non-call du tool.
  [`nodes.py:454`](../../backend/app/graph/nodes.py#L454)

**Tests**

- Test guard ESG après chat turn + assertion `mock.assert_not_called()` (review patch).
  [`test_router_node.py:154`](../../backend/tests/test_router_node.py#L154)

- Test caplog DEBUG sur les 6 champs requis (AC4).
  [`test_router_node.py:182`](../../backend/tests/test_router_node.py#L182)

- Tests prompt impératif + négatif (AC1, R2).
  [`test_chat_profiling.py:118`](../../backend/tests/test_chat_profiling.py#L118)

- Test intégration multi-tours profilage→ESG (AC3) + note acceptance auditor sur scope `tool_call_logs`.
  [`test_profile_to_esg_routing.py:62`](../../backend/tests/test_graph/test_profile_to_esg_routing.py#L62)

## Spec Change Log

### 2026-04-30 — Diagnostic Bug 2 (lecture statique)

Sans accès au navigateur headed, le diagnostic a été réalisé par lecture statique de `router_node` et de `_is_topic_continuation`. Cause identifiée :

- `chat_node` ne réinitialise pas `active_module` (il retourne uniquement `{"messages": [response]}`).
- LangGraph persiste `active_module` entre les tours via le checkpointer.
- Si un tour précédent (par ex. confirmation widget ESG ou tour chat post-classification) a fixé `active_module='chat'` ou un autre module, alors au tour suivant `router_node` entre dans la branche `if active_module and last_user_msg:` (l. 510) et délègue la décision à `_is_topic_continuation` (LLM binaire).
- Le défaut sécuritaire de `_is_topic_continuation` (l. 240) est `True` — donc en cas de classification ambiguë ou d'erreur LLM, on reste dans le module précédent et l'intention ESG explicite est ignorée.

**Fix appliqué** : garde défensive AVANT la branche continuation, qui force `active_module=None` quand `_detect_esg_request(last_user_msg) is True` ET `not _has_active_esg_assessment(state)` ET `active_module != 'esg_scoring'`. La condition `active_module != 'esg_scoring'` préserve le cas légitime où l'utilisateur poursuit son évaluation ESG en cours.

### 2026-04-30 — Replay E2E reporté

Le replay `agent-browser --headed` de la session `profil-esg-complet-v2` (dernière étape de la liste Tasks) reste à effectuer manuellement par l'humain. Claude Code (CLI) n'a pas accès à un navigateur headed dans ce contexte. La validation par tests unitaires + intégration en mémoire (51 tests verts ciblés, 1291 tests verts au total) couvre les ACs T2/T3/T4 du fix.
