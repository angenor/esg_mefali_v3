# Prompt BMAD — Fix routage LangGraph chat → esg_scoring_node + invocation effective du scoring

---

## CONTEXTE

- **Repo** : `/Users/mac/Documents/projets/2025/esg_mefali_v3`
- **Stack** : FastAPI (backend Python 3.12) + LangGraph + LangChain + Nuxt 4 (frontend)
- **Branche cible** : créer `fix/esg-scoring-node-routing` depuis `main`
- **Stories existantes pertinentes** :
  - Story 005 — Module ESG scoring + node `esg_scoring_node`
  - Story 012 — LangGraph tool calling (32 tools dont `batch_save_esg_criteria`)
  - Story 013 — Routing multi-tour avec `active_module` dans `ConversationState`
  - Story 015 — Prompts ESG renforcés (ROLE, OUTILS, REGLE ABSOLUE)
  - Story 018 — Widgets interactifs (`interactive_questions`)

## BUG OBSERVÉ EN CONDITION RÉELLE (E2E LIVE le 2026-04-30)

**Symptôme** : malgré 6 confirmations utilisateur explicites via widgets interactifs (« finaliser mon évaluation », « oui, créer l'évaluation », « voir résultats »), **aucune row n'est créée dans la table `esg_assessments`**.

**Trace mesurée** :

```
SELECT module, state, COUNT(*) FROM interactive_questions
WHERE created_at > NOW() - INTERVAL '30 minutes' GROUP BY module, state;

 module |   state   | count
--------+-----------+-------
 chat   | answered  |     6
 chat   | abandoned |     1
 chat   | pending   |     1

SELECT count(*) FROM esg_assessments;  -- 0
```

**Diagnostic présumé** :
1. Le routeur LangGraph (`router_node`) ne bascule jamais `active_module` de `chat` vers `esg_scoring`, même après que l'utilisateur a explicitement validé le démarrage de l'évaluation.
2. Le `chat_node` continue à poser des widgets de confirmation en boucle (« voulez-vous créer ? », « voulez-vous finaliser ? », « voulez-vous voir les résultats ? ») sans appeler le tool `batch_save_esg_criteria` ni transférer le contrôle.
3. La page UI `/esg` ne propose aucun chemin alternatif : le bouton « Nouvelle évaluation » ouvre simplement le chat (`pages/esg/index.vue`).

**Preuves** : voir `_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/REPORT.md` (section « Extension »).

## OBJECTIF

Garantir qu'une demande utilisateur du type **« lance mon évaluation ESG »** ou la confirmation **« oui, créer l'évaluation »** produise effectivement :
1. Un transfert de `active_module` vers `esg_scoring`
2. L'invocation du tool `batch_save_esg_criteria` (et/ou création directe via service)
3. Une row `esg_assessments` avec `status='completed'` et les 4 scores (overall + E + S + G)

## PÉRIMÈTRE

### Backend (priorité haute)

- **`backend/app/graph/router.py`** (ou équivalent — fichier qui contient `router_node`) :
  - Renforcer la classification LLM continuation/changement pour reconnaître les intentions « démarrer/finaliser/créer évaluation ESG » comme une transition vers `esg_scoring`.
  - Détecter les widgets de confirmation déjà répondus dans la conversation et forcer le routage.

- **`backend/app/graph/nodes/chat.py`** :
  - Empêcher le `chat_node` de poser de nouveaux widgets de confirmation ESG quand `active_module=chat` mais que l'utilisateur a déjà confirmé l'intention (anti-boucle).
  - Déléguer immédiatement à `esg_scoring_node` au lieu de demander une N+1ème confirmation.

- **`backend/app/graph/nodes/esg_scoring.py`** :
  - Vérifier que le node crée bien la row `esg_assessments` au démarrage (status=draft) et la finalise (status=completed) après scoring.
  - S'assurer que le tool `batch_save_esg_criteria` est appelé dans tous les cas, y compris en mode « hypothèses prudentes ».

- **`backend/app/graph/tools/esg_tools.py`** :
  - Si nécessaire, ajouter un tool `start_esg_assessment` invocable depuis `chat_node` pour bootstrap l'évaluation et déclencher la transition.

### Frontend (priorité moyenne)

- **`frontend/app/pages/esg/index.vue`** :
  - Le bouton « Nouvelle évaluation » doit appeler un endpoint backend `POST /api/esg/assessments` (création directe, status=draft) avant d'ouvrir le chat — pas se contenter d'ouvrir le chat.

### Tests (obligatoires, TDD)

- **`backend/tests/integration/test_esg_routing.py`** (nouveau) :
  - Test 1 : message « lance mon évaluation ESG » → après 1 tour, `active_module='esg_scoring'`.
  - Test 2 : confirmation widget « créer l'évaluation » → row `esg_assessments` créée en DB.
  - Test 3 : choix « hypothèses prudentes » → assessment finalisée (status=completed, 4 scores non null).
  - Test 4 : anti-boucle — `chat_node` ne doit pas poser plus de 1 widget de confirmation ESG par conversation.

- **`backend/tests/unit/test_router_node.py`** :
  - Test classification : 8 phrases d'intention ESG (incluant « finaliser », « créer », « démarrer », « commencer mon scoring », « calculer mes scores ») → toutes routent vers `esg_scoring`.

## CRITÈRES D'ACCEPTATION (Given/When/Then)

**AC1 — Transition module au premier signal d'intention**
- **Given** une conversation neuve avec `active_module=null` ou `chat`
- **When** l'utilisateur envoie « je veux faire mon évaluation ESG » ou « lance mon évaluation »
- **Then** après le tour suivant, `active_module='esg_scoring'` dans `ConversationState`
- **And** le prochain message assistant est généré par `esg_scoring_node` (pas `chat_node`)

**AC2 — Création effective de l'assessment**
- **Given** l'utilisateur a confirmé une intention ESG explicite
- **When** il clique « ✅ Oui, créer l'évaluation » sur un widget
- **Then** une row `esg_assessments` existe en DB avec `status='draft'` ou `'in_progress'`
- **And** elle est liée à la `conversation_id` courante

**AC3 — Finalisation avec hypothèses prudentes**
- **Given** un assessment `in_progress`
- **When** l'utilisateur clique « ⚡ Hypothèses prudentes pour aller vite »
- **Then** le tool `batch_save_esg_criteria` est invoqué avec 30 critères (scores 4-5/10 par défaut)
- **And** la row `esg_assessments` passe à `status='completed'`
- **And** `overall_score`, `environment_score`, `social_score`, `governance_score` sont tous non-null

**AC4 — Anti-boucle widget**
- **Given** une conversation où l'utilisateur a déjà répondu « oui » à un widget de confirmation ESG
- **When** le tour suivant est traité
- **Then** `chat_node` ne pose pas une nouvelle question de confirmation ESG
- **And** la conversation a `active_module='esg_scoring'` (le contrôle est transféré)

**AC5 — Validation E2E live (replay du scénario v3)**
- **Given** la session de test du 2026-04-30
- **When** l'utilisateur exécute la même séquence : « lance mon évaluation ESG » → secteur → taille → « hypothèses prudentes » → « finaliser »
- **Then** `SELECT count(*) FROM esg_assessments WHERE created_at > NOW() - INTERVAL '5 minutes'` retourne ≥ 1
- **And** la row a les 4 scores remplis

## RÈGLES DE RÉALISATION

- **TDD strict** : écrire les tests AVANT le code (RED → GREEN → REFACTOR)
- **Lecture seule sur la migration story 018** : ne PAS modifier le schéma `interactive_questions`
- **Pas de breaking change** sur les nodes existants : préserver le contrat `ConversationState`
- **Coverage ≥ 80%** sur le code modifié
- **Couleurs/dark mode** : aucune modification UI hors `pages/esg/index.vue` (changement minimal du handler du bouton)
- **Pas de skip de tests existants** : les 935+ tests backend doivent rester verts
- **Branche dédiée** : `fix/esg-scoring-node-routing` — PR séparée

## VALIDATION FINALE

Avant de demander review, exécuter :

```bash
cd backend && source venv/bin/activate
pytest tests/integration/test_esg_routing.py tests/unit/test_router_node.py -v
pytest --cov=app/graph --cov-report=term-missing  # >= 80% sur graph/
```

Puis re-jouer le scénario E2E live :

```bash
agent-browser --headed open http://localhost:3000/dashboard
# Reproduire les 6 étapes du REPORT.md section Extension
PGPASSWORD=postgres psql -h localhost -U postgres -d esg_mefali_v3 \
  -c "SELECT id, status, overall_score FROM esg_assessments ORDER BY created_at DESC LIMIT 1;"
# DOIT retourner une row avec overall_score non-null
```

## LIVRABLES

1. PR sur GitHub (base `main`, head `fix/esg-scoring-node-routing`)
2. Description PR avec :
   - Lien vers REPORT.md (preuve du bug)
   - Tableau des 5 AC avec verdict PASS
   - Capture E2E DB montrant la row `esg_assessments` créée
3. Tests verts (CI green)
4. Coverage ≥ 80% confirmé

## RÉFÉRENCES

- Bug observable : `_bmad-output/implementation-artifacts/widget-esg-fix-evidence-v3/REPORT.md` (section « Extension »)
- Artefacts E2E : `13-final-state.txt`, `09-create-assessment.png`, `10-show-results.png`
- DB : `esg_mefali_v3` (et non `esg_mefali` — voir Note 1 du REPORT)
- Compte test : moussa1@gmail.com / Moussa2026!
