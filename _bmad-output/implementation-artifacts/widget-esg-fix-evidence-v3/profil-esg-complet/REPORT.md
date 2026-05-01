# REPORT — E2E Profil ESG complet

**Date** : 2026-04-30 05:53–05:58 UTC
**Branche** : `fix/esg-scoring-node-routing` (PR #4 en cours)
**Compte** : `moussa1@gmail.com` (user_id `6d9321a3-165d-4bc0-ab02-c3976d003d19`)
**Session agent-browser** : `profil-esg-complet` (mode `--headed`)
**Backend** : `uvicorn app.main:app --reload --port 8000` sur `esg_mefali_v3` (PID 50845)
**Cleanup pré-vol** : exécuté via `/tmp/cleanup-moussa1.sql` — backup `/tmp/moussa1-backup-1777528270.sql` (45 KB)

## Pré-requis vérifiés

| Item | Statut | Note |
|---|---|---|
| Frontend `:3000` | OK (200) | — |
| Backend `:8000` | OK (200) | **Initialement sur le mauvais repo** (`esg_mefali`, PID 26540) — kill + restart sur `esg_mefali_v3` |
| DB accessible | OK | `psql` direct |
| Compte test présent | OK | id `6d9321a3-…` |
| Cleanup DB | OK | conv=0, esg=0, profil reset |

## Verdicts par AC

| AC | Description | Verdict | Evidence |
|----|-------------|---------|----------|
| AC1 | Profil entreprise passe à ≥ 70 % completion après le message dense | **FAIL** | Profil reste à 6 % ; aucun appel `update_company_profile` dans `tool_call_logs`. Voir `02-profilage-chat.png`. Le LLM accuse réception (« informations très complètes ») mais ne persiste rien. |
| AC2 | `_detect_esg_request("lance mon évaluation ESG")` route vers `esg_scoring_node` | **FAIL** | Le message est routé à **`chat_node`** qui appelle `ask_interactive_question` (widget « régionalité »). Le regex `_detect_esg_request` retourne pourtant `True` (test isolé Python OK). Voir `04-esg-routed.png` + `db-final-state.txt`. |
| AC3 | Row `esg_assessments` créée en `status='draft'` puis `'in_progress'` | **FAIL** | Aucune row créée (cf. `db-final-state.txt` → 0 rows). |
| AC4 | `batch_save_esg_criteria` invoqué sans `TypeError` | **N/A** | Non atteint (AC3 préalable failed). |
| AC5 | `finalize_esg_assessment` produit 4 scores non-null + 30 critères | **N/A** | Non atteint. |
| AC6 | Page `/esg` affiche radar chart + scores après refresh | **FAIL** | Page chargée mais aucune évaluation à afficher (cohérent avec AC3 fail). Voir `09-esg-page-with-result.png`. |
| AC7 | Aucune erreur console JS, aucun stack trace dans logs | **PARTIAL** | Logs uvicorn propres (aucun Traceback / TypeError), niveau INFO seulement (logs router non visibles — hors WARNING). |
| AC8 | Dark mode toggle ne casse pas l'affichage | **N/A** | Tentative de toggle sur `/esg` exécutée mais index snapshot stale — capture `10-dark-mode.png` identique à `09` (toggle non confirmé). À retester manuellement. |

## Verdict global

**FAIL** — le parcours E2E n'a pas pu progresser au-delà de la Phase 2. Deux régressions critiques identifiées.

### Bug 1 — Profilage non-persistant (Phase 2)

Le message dense (nom, secteur, taille, CA, ODD) n'a déclenché **aucun tool call** vers `update_company_profile`. Le LLM répond textuellement comme s'il avait extrait les données, mais aucune écriture BDD n'a lieu.

**Hypothèse** : le prompt système chat ne force pas le tool calling pour le profilage initial, ou les tools de profilage sont absents de `filtered_tools` quand le profil est à < 10 %.

**À investiguer** : `select_tools_for_node(node_name="chat", current_page=…)`, `_propagate_tools_offered`, et la section « update_company_profile » du system prompt construit dans `build_system_prompt`.

### Bug 2 — Routage ESG bloqué par chat_node (Phase 3, AC2 PR #4)

`"lance mon évaluation ESG"` ne route PAS vers `esg_scoring_node`. Le message arrive à `chat_node` qui pose un widget interactif sur la régionalité.

**Faits** :
- Test Python isolé : `_detect_esg_request("lance mon évaluation ESG")` → `True`
- Simulation `router_node` (active_module=None) → `_route_esg=True`
- `chat_node` ligne 1384-1389 dégrade `ask_interactive_question` SI `_detect_esg_request(last_user)` est True — donc le widget posé n'aurait pas dû être ESG, et de fait il porte sur la région (clarification profilage), pas sur ESG. Cela confirme que **le routeur a envoyé le message au chat_node au lieu d'`esg_scoring_node`**.

**Hypothèse** : `active_module` était possiblement non-null suite au tour de profilage précédent (mais aucun code visible dans `chat_node` ne le set), OU une autre clause court-circuite la priorité ESG dans `_route_after_router`.

**À investiguer** :
- Tracer la valeur réelle de `state.active_module` au moment du 2e tour (logs DEBUG sur `router_node`).
- Vérifier si un autre flag (`has_document`, `should_extract`) court-circuite la priorité ESG dans `_route_after_router`.
- Vérifier si `messages` history embarque un `AIMessage` avec `tool_calls` non résolus laissés par le 1er tour.

## Artefacts

```
profil-esg-complet/
├── REPORT.md                       (ce fichier)
├── db-final-state.txt              (esg_assessments WHERE user_id=moussa1 → 0 rows)
├── 01-login.png                    (dashboard atteint après login)
├── 02-profilage-chat.png           (message dense envoyé ; réponse texte plat sans tool)
├── 04-esg-routed.png               (« lance mon évaluation ESG » → widget région chat_node)
├── 09-esg-page-with-result.png     (/esg vide, conforme à AC3 fail)
└── 10-dark-mode.png                (identique à 09 — toggle dark non confirmé)
```

## Prochaine action recommandée

Ouvrir un nouveau prompt BMAD `spec-fix-profile-and-routing-regression.md` ciblant :

1. **Bug 1** : Forcer `update_company_profile` à l'extraction ; ajouter test E2E pytest qui assert qu'après un message dense le profil est ≥ 70 % et qu'un `tool_call_log(node_name='chat', tool_name='update_company_profile')` existe.
2. **Bug 2** : Logger DEBUG `router_node` (`is_esg_request`, `active_module`, `_route_esg`) ; ajouter test d'intégration `tests/integration/test_esg_routing_after_profilage.py` qui simule la séquence (profilage → « lance ESG ») et assert que le 2e tour atteint `esg_scoring_node`.

Le PR #4 ne peut pas être mergé tant que AC2 reste FAIL.

## Cleanup post-test

- Backup pré-cleanup conservé : `/tmp/moussa1-backup-1777528270.sql`
- État final DB : conv=1 (créée par le test), esg=0, profil partiellement rempli (`company_name='Moussa SARL'` seulement)
- Aucune modification de code source.

## Mise à jour 2026-04-30 — Fixes appliqués (spec fix-profile-and-routing-regression)

- **Bug 1 (profilage non-persistant)** : `_build_profiling_instructions` renforcé dans `backend/app/graph/nodes.py` pour exiger explicitement « tu DOIS appeler le tool `update_company_profile` AVANT toute autre réponse ».
- **Bug 2 (routage ESG bloqué)** : garde défensive ajoutée dans `router_node` — si `_detect_esg_request(last_user_msg)` est `True` ET aucune évaluation ESG en cours, `active_module` est forcé à `None` AVANT la branche continuation. Cela empêche un module précédent (ex. `chat`) de capturer l'intention ESG via le classifieur LLM `_is_topic_continuation`.
- **AC4 (instrumentation)** : log `DEBUG` ajouté en fin de `router_node` listant les 6 champs requis (`last_user_msg[:80]`, `is_esg_request`, `active_module`, `has_active_esg`, `_route_esg`, `is_continuation`).
- **Tests** : 6 nouveaux tests verts (`test_router_node.py::test_esg_priority_after_chat_turn`, `::test_router_debug_logs` ; `test_chat_profiling.py::test_chat_profiling_tool_call_dense_message`, `::test_chat_no_profile_call_on_esg_request` ; `test_graph/test_profile_to_esg_routing.py::test_profile_to_esg_two_turn_routing`, `::test_esg_request_clean_slate`).
- **Suite complète** : 1291 tests verts, 3 échecs préexistants sur `test_guided_tour_*` (présents sur le baseline `17dc290`, sans rapport avec ces fixes).
- **Replay E2E `agent-browser` à effectuer manuellement par l'humain** : Claude Code (CLI) n'a pas accès au navigateur headed nécessaire pour rejouer la session `profil-esg-complet-v2`. Étapes : `cleanup-moussa1.sql` → re-run agent-browser → vérifier verdicts sur AC1-AC8.
