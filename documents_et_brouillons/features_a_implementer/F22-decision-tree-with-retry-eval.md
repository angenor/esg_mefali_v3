# F22 — Decision Tree dans System Prompt + with_retry Effectif + Golden Set 50 cas

**Module(s) source(s)** : Module 10.3 (System prompt avec arbre de décision), Module 10.5 (Validation + boucle correction), Module 10.6 (Évaluation continue)
**Priorité** : P1 — qualité tool-use, fiabilité LLM, prévention régressions
**Dépendances** : F01 (decision tree mentionne cite_source), F10 (decision tree mentionne nouveaux widgets), F11 (decision tree mentionne tools visualisation)
**Estimation** : 1.5 sprints

## Contexte & motivation

**Module 10 — État actuel** :
- ✅ Filtrage par page (Module 10.4) : excellent (story 10.2 complète)
- ✅ Schémas Pydantic stricts (Module 10.2) : 14/24 tools conformes au gabarit 5 sections
- ⚠️ Inconsistance sur les 10 tools restants (carbon, financing, credit, action_plan, document, guided_tour, chat) : docstrings au format ancien
- ❌ **Decision tree dans system prompt absent** : `prompts/system.py` contient seulement « Cite les sources quand c'est pertinent » et `## REGLE ABSOLUE — TOOL CALLING OBLIGATOIRE` (textes prescriptifs sans arbre)
- ❌ Anti-exemples partiels : présents dans 14 docstrings mais pas dans system prompt général
- ❌ Pas d'exemples de chaînage de tools dans les prompts
- ⚠️ `with_retry()` (`backend/app/graph/tools/common.py:103`) avec `max_retries=1` codé MAIS **n'est utilisé par AUCUN tool actuel**
- ❌ Pas de fallback texte explicite après 2 retry échoués
- ❌ **Golden set vide** : `backend/tests/llm_eval/` contient uniquement des `.pyc` orphelins (aucun fichier `.py`, aucun `.json` golden set)
- ❌ Pas de métriques (taux bon tool, payload valide, hallucination, fallbacks)
- ❌ Pas d'exécution auto au changement de prompt/modèle/tool en CI

**Conséquences** :
- Pas de visibilité régression quand on change un prompt
- Tool selection peut dégrader sans qu'on s'en aperçoive
- LLM peut produire des chiffres sans `cite_source` (F01 dépend) sans qu'on le détecte
- Pas de boucle correction → erreurs de payload remontent comme ça à l'utilisateur

## User stories

- **Architecte** : « Je veux un golden set de 50 cas (message + page → tool + payload) qui s'exécute en CI à chaque changement de prompt, avec rapport de régression. »
- **Architecte** : « Je veux que `with_retry` soit effectif sur les tools de mutation critique : si le LLM produit un payload invalide, retry 1x puis fallback texte. »
- **Architecte** : « Je veux que le system prompt contienne un decision tree explicite : `Question fermée ? → ask_qcu`, `Visualisation utile ? → catalogue typé`, `Mutation métier ? → tool d'action + confirmation`, `Chiffre ? → JAMAIS sans Source`. »
- **Architecte** : « Je veux les 10 docstrings non conformes alignées sur le gabarit 5 sections. »

## Périmètre fonctionnel

### Decision tree dans system prompt

Modifier `backend/app/prompts/system.py:BASE_PROMPT` :

```python
DECISION_TREE = """
## ARBRE DE DÉCISION TOOL — RÈGLES OBLIGATOIRES

### 1. QUESTION FERMÉE ?
- 2-7 options exclusives → ask_qcu
- Plus de 7 options → ask_select (avec recherche)
- Multiples options sélectionnables → ask_qcm
- Oui/Non → ask_yes_no (ATTENTION: pour actions destructives, utilise ask_yes_no(destructive=True))
- Numérique avec unité → ask_number
- Date → ask_date / ask_date_range
- Note 1-5 ou 1-10 → ask_rating
- Upload de fichier → ask_file_upload
- Plusieurs champs en une fois → show_form

### 2. VISUALISATION UTILE ?
- Chiffre clé important (score, total) → show_kpi_card
- Évolution temporelle → show_line_chart (richblock chart)
- Répartition catégorielle → show_pie_chart / show_donut_chart
- Comparaison de plusieurs entités → show_comparison_table
- Match projet ↔ offre → show_match_card
- Position géographique → show_map
- Process / décision → show_mermaid (fallback)
- Sinon → texte

### 3. MUTATION MÉTIER ?
- Création → create_*
- Mise à jour → update_*
- Suppression / Révocation → demande d'abord ask_yes_no(destructive=True)
- Toute mutation passe par les services qui auditent (F03)
- JAMAIS de mutation sur le catalogue (Fund, Intermediary, Source, Skill, Indicator) — réservé Admin

### 4. AFFIRMATION FACTUELLE (chiffre, critère, formule, seuil) ?
- TOUJOURS invoquer cite_source(source_id) avant
- Si pas de source disponible → flag_unsourced(claim, reason)
- Si besoin de chercher dans le catalogue → search_source(query)
- JAMAIS afficher un chiffre sans source (validation backend rejettera)

### 5. CHAÎNAGE DE TOOLS DANS UN MÊME TOUR
Exemple : Réponse riche après calcul carbone
1. cite_source(source_id_ademe_v23) — référence le facteur d'émission
2. show_kpi_card({"title": "Empreinte 2026", "value": "45 tCO2e", "delta": -12})
3. show_pie_chart({...répartition})
4. ask_qcu({...question suite})
"""

ANTI_PATTERNS = """
## ANTI-PATTERNS À ÉVITER

❌ NE FAIS PAS : produire un chiffre dans la réponse sans cite_source.
   → Le backend va rejeter et te demander de retry.

❌ NE FAIS PAS : poser une question fermée en texte libre alors qu'un tool ask_* convient.
   → Mauvaise UX, perte de payload structuré.

❌ NE FAIS PAS : delete_project() ou delete_application() directement.
   → Tu dois d'abord invoquer ask_yes_no(destructive=True).

❌ NE FAIS PAS : show_radar_chart pour 1 seul chiffre.
   → Utilise show_kpi_card.

❌ NE FAIS PAS : modifier le catalogue (funds, intermediaries, indicators).
   → C'est réservé aux admins.
"""

BASE_PROMPT = f"""
{base existant}

{DECISION_TREE}

{ANTI_PATTERNS}
"""
```

### `with_retry` effectif

Décorer les tools de mutation critique avec `@with_retry`:
- `update_company_profile`
- `batch_save_esg_criteria`
- `finalize_esg_assessment`
- `finalize_carbon_assessment`
- `create_fund_application`
- `update_application_status`
- `generate_credit_score`
- `generate_action_plan`
- `update_action_item`
- `update_project` (F06)
- `delete_project` (F06)
- `generate_attestation` (F08)

```python
from app.graph.tools.common import with_retry

@tool(args_schema=UpdateCompanyProfileArgs)
@with_retry(max_retries=1, fallback_message="Je n'arrive pas à formaliser cette mise à jour de profil. Pouvez-vous me reformuler ?")
async def update_company_profile(...):
    ...
```

Quand le tool échoue 1x avec erreur Pydantic ou exception runtime :
- Retry 1x avec contexte d'erreur structuré envoyé au LLM
- Si retry échoue : retourner `{"success": False, "fallback_message": "..."}` qui s'affiche dans le chat

### Standardisation docstrings (10 tools restants)

Pour chaque tool dans :
- `chat_tools.py`
- `carbon_tools.py`
- `financing_tools.py`
- `credit_tools.py`
- `action_plan_tools.py`
- `document_tools.py`
- `guided_tour_tools.py`

Réécrire les docstrings au gabarit 5 sections :
```python
"""
[Verbe d'action en une phrase]

Use when: [3-5 lignes max — quand c'est pertinent]

Don't use when: [3-5 lignes — anti-patterns]

Exemple positif:
[1 cas concret avec contexte + payload]

Anti-exemple:
[1 cas où il ne faut pas l'utiliser, avec alternative recommandée]
"""
```

Étendre le test meta `test_tools_meta_conformity.py` pour couvrir TOUS les tools :
```python
ALL_TOOL_GROUPS = [
    INTERACTIVE_TOOLS, PROFILING_TOOLS, ESG_TOOLS, APPLICATION_TOOLS,
    CHAT_TOOLS, CARBON_TOOLS, FINANCING_TOOLS, CREDIT_TOOLS,
    ACTION_PLAN_TOOLS, DOCUMENT_TOOLS, GUIDED_TOUR_TOOLS,
    SOURCING_TOOLS,  # F01
    PROJECT_TOOLS,  # F06
    OFFER_TOOLS,  # F07
    ATTESTATION_TOOLS,  # F08
    VISUALIZATION_TOOLS,  # F11
    MEMORY_TOOLS,  # F12
]

def test_all_tools_conform_to_5_sections():
    for group in ALL_TOOL_GROUPS:
        for tool in group:
            assert "Use when:" in tool.description
            assert "Don't use when:" in tool.description
            assert "Exemple" in tool.description or "Example" in tool.description
            assert "Anti" in tool.description
```

### Golden set 50 cas

Créer `backend/tests/llm_eval/golden_set.json` :
```json
{
  "version": "1.0",
  "cases": [
    {
      "id": "01-profile-set-sector",
      "context": {
        "current_page": "/profile",
        "active_module": null
      },
      "user_message": "Mon entreprise est dans l'agriculture biologique",
      "expected": {
        "tool_called": "update_company_profile",
        "payload_contains": {"sector": "agriculture"}
      }
    },
    {
      "id": "02-esg-finalize-confirmation",
      "context": {"current_page": "/esg", "active_module": "esg_scoring"},
      "user_message": "C'est bon je veux valider l'évaluation",
      "expected": {
        "tool_called": "ask_yes_no",
        "payload_contains": {"destructive": false}
      }
    },
    ...50 cas total
  ]
}
```

Cas couverts (équilibrés) :
- 10 cas profilage (entreprise + projets F06)
- 8 cas ESG (saisie indicateur, finalize, multi-référentiels F13)
- 6 cas carbone (saisie emission, choix catégorie, F17)
- 6 cas financement (matching F14, simulateur F16, comparateur)
- 6 cas applications (création F15, génération section, statut update)
- 5 cas crédit (Mobile Money F18, photos, attestation F08)
- 4 cas plan d'action (création, update, badges)
- 5 cas conversationnels génériques (yes/no, recall_history F12, etc.)

Test runner `backend/tests/llm_eval/test_eval_runner.py` :
```python
import pytest, json
from app.graph.graph import compile_graph

@pytest.mark.eval
@pytest.mark.parametrize("case", load_golden_set())
async def test_golden_case(case):
    graph = compile_graph()
    result = await graph.ainvoke({...case context...})
    assert result.tool_called == case.expected.tool_called
    assert subset_match(result.payload, case.expected.payload_contains)
```

Métriques calculées :
- Taux bon tool (% cas où le tool attendu est invoqué)
- Taux payload valide (% cas où le payload est conforme)
- Taux hallucination (% cas où un tool inexistant est invoqué)
- Distribution des fallbacks

Lancement :
- `pytest tests/llm_eval/ -m eval --golden-report=eval-report.json`
- En CI sur changement de prompts ou de tool definitions

### Logging échecs validation

Étendre `tool_call_logs` pour inclure :
- `validation_error: jsonb | null` (détail Pydantic)
- `retry_count: int` (existe déjà)

Endpoint admin (F09) `GET /api/admin/metrics/validation-failures` qui agrège.

## Hors-scope (post-MVP)

- ML-based intent classification (replace regex router)
- Cache sémantique des réponses tools (idempotent)
- Apprentissage en ligne sur les corrections utilisateurs
- A/B testing automatique de versions de prompts
- Auto-génération du golden set (LLM crée des cas)

## Exigences techniques

### Backend

- Modifier `app/prompts/system.py` : DECISION_TREE + ANTI_PATTERNS
- Refactor `app/graph/tools/common.py:with_retry` : ajouter `fallback_message` parameter
- Décorer ~12 tools avec `@with_retry`
- Standardiser 10 docstrings restantes (ToolGroups : chat, carbon, financing, credit, action_plan, document, guided_tour)
- Étendre `test_tools_meta_conformity.py`
- Créer `tests/llm_eval/test_eval_runner.py`
- Créer `tests/llm_eval/golden_set.json` (50 cas)
- CI : ajouter step `pytest tests/llm_eval/ -m eval` (peut être marqué `slow`/`expensive`, run sur changement prompts/tools)
- Tests :
  - Test with_retry : payload invalide → retry 1x → si toujours échec → fallback
  - Test conformity : tous les tools passent les 5 sections
  - Test golden : taux bon tool > 90 %
  - Test mesure performance : pas de régression > 5 % sur le golden set

### Frontend

- Pas de changement majeur
- (Optionnel) : afficher un message dégradé "Je n'arrive pas à formaliser, pouvez-vous reformuler ?" quand fallback (déjà géré par le tool retournant `{"success": False, ...}`)

### Base de données

- Colonne `validation_error: jsonb | null` sur `tool_call_logs`

## Critères d'acceptation

- [ ] DECISION_TREE et ANTI_PATTERNS ajoutés au system prompt
- [ ] `with_retry` actif sur 12+ tools de mutation critique
- [ ] Fallback texte structuré quand 2 retries échouent
- [ ] 10 docstrings restantes alignées sur 5 sections
- [ ] Test conformity étendu à tous les tools
- [ ] Golden set 50 cas créé en JSON
- [ ] Test runner fonctionnel
- [ ] CI exécute le golden set sur changement prompts/tools
- [ ] Rapport eval : taux bon tool > 90 %, taux payload valide > 95 %
- [ ] Couverture tests ≥ 80 %
- [ ] Documentation `docs/llm-eval-loop.md` : process, métriques, comment ajouter un cas

## Risques & garde-fous

- **Risque** : exécution golden set coûteuse (50 cas × LLM calls = $$$). **Garde-fou** : run uniquement sur changement prompts/tools (CI conditionnel), cache LLM responses pour les cas déterministes.
- **Risque** : decision tree trop verbeux dans le prompt augmente les tokens. **Garde-fou** : token budget tracking dans `_tokens_baseline.json`, gate +25 % max.
- **Risque** : `with_retry` masque des bugs réels (retry réussi cache la cause). **Garde-fou** : log retry_count dans `tool_call_logs`, alert si retry_count > seuil 5 % des appels.
- **Risque** : golden set se désaligne quand les tools évoluent. **Garde-fou** : process documenté pour mettre à jour le golden, review obligatoire à chaque PR qui change un tool ou un prompt.
- **Risque** : faux positifs eval (LLM choisit un autre tool valide pas attendu). **Garde-fou** : matching tolérant (whitelist de tools acceptables par cas), peut accepter plusieurs tools possibles.
