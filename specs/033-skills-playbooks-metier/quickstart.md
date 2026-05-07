# Phase 1 — Quickstart: F23 Skills (Playbooks Métier)

## Pour les Admins (cycle de vie d'une Skill)

### 1. Créer une nouvelle Skill (draft)

```bash
curl -X POST https://api.example.com/api/admin/skills \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "skill_score_boad",
    "domain": "scoring_referentiel",
    "prompt_expert": "Tu es un expert du scoring BOAD. Pour chaque projet, tu vérifies les critères d'éligibilité de la Banque Ouest-Africaine de Développement : taille minimale 500k EUR, secteur prioritaire (énergies renouvelables, infrastructure verte, agriculture climato-intelligente), cofinancement requis ≥ 30 %, alignement avec les Objectifs de Développement Durable (ODD 7, 9, 13). Tu cites systématiquement les règlements BOAD via cite_source. Tu utilises le vocabulaire institutionnel BOAD : « plan de financement », « tour de table », « impact mesurable », « plan de gestion environnemental et social (PGES) ».",
    "procedure": "1. Demander le secteur du projet (ask_qcu).\n2. Demander le montant total (ask_number).\n3. Vérifier secteur ∈ {énergies renouvelables, infrastructure, agriculture}.\n4. Vérifier montant ≥ 500k EUR.\n5. Si OK → show_match_card avec score BOAD.\n6. Citer GFI BOAD via cite_source.",
    "tool_whitelist": ["search_funds", "get_fund_details", "show_match_card", "cite_source", "ask_yes_no", "ask_qcu", "ask_number"],
    "sources": ["uuid-boad-procedures-climat", "uuid-boad-conditions-financement"],
    "activation_rules": {
      "page_slugs": ["/financing"],
      "intent_keywords": ["BOAD", "Banque Ouest-Africaine"],
      "fund_id": "BOAD_FUND_UUID"
    },
    "golden_examples": [
      {
        "id": "boad-eligible-energy-01",
        "category": "scoring_referentiel",
        "context": {"current_page": "/financing", "fund_id": "BOAD_FUND_UUID"},
        "user_message": "Mon projet de centrale solaire 800k EUR au Sénégal",
        "expected": {
          "tool_called": "show_match_card",
          "payload_contains": {"score_match": "high"}
        }
      }
    ]
  }'
```

**Réponse** : `201 Created` avec `id` UUID.

**Erreurs courantes** :

- `422 detected_patterns: ["ignore_previous_instructions"]` → reformuler le `prompt_expert` (anti-injection).
- `422 prompt_expert_too_long: actual_tokens=6500` → réduire le prompt.
- `422 source_must_be_verified: source_id="..."` → la source doit avoir `verification_status='verified'` dans la table `sources`.
- `422 tool_name_unknown: tool_name="..."` → vérifier le nom dans le catalogue exposé.

### 2. Tester la Skill (sans publier)

```bash
curl -X POST https://api.example.com/api/admin/skills/{id}/test \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Réponse** : `SkillEvalReport` (200 OK, statut reste `draft`).

```json
{
  "skill_id": "uuid",
  "total_cases": 1,
  "passed": 1,
  "failed": 0,
  "success_rate": 1.0,
  "threshold": 0.9,
  "gate_passed": true,
  "failed_cases": []
}
```

### 3. Publier la Skill (gate eval obligatoire)

```bash
curl -X POST https://api.example.com/api/admin/skills/{id}/publish \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Si gate passé (≥ 90 % de réussite)** :
- `200 OK` : skill `published`, immédiatement chargée par le loader runtime.

**Si gate échoué** :
- `422` avec rapport. Skill reste `draft`. L'admin doit corriger le prompt ou les golden_examples.

```json
{
  "skill_id": "uuid",
  "total_cases": 5,
  "passed": 2,
  "failed": 3,
  "success_rate": 0.4,
  "gate_passed": false,
  "failed_cases": [
    {
      "case_id": "boad-eligible-energy-01",
      "expected_tool": "show_match_card",
      "actual_tool": "ask_yes_no",
      "payload_diff": {"missing": ["score_match"]}
    }
  ]
}
```

### 4. Éditer une Skill `published` (versioning)

```bash
curl -X PATCH https://api.example.com/api/admin/skills/{id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt_expert": "...nouveau prompt amélioré..."}'
```

**Comportement** :
- L'ancienne skill `1.0.0` reste `published` (pas de mutation).
- Nouvelle ligne créée : `version=1.0.1`, `status=draft`.
- Réponse contient le nouvel `id`.

L'admin doit alors publier la nouvelle version :

```bash
curl -X POST https://api.example.com/api/admin/skills/{new_id}/publish \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Si succès : nouvelle version devient `published`, ancienne reçoit `valid_to=today()`.

## Pour les Développeurs (intégration LangGraph)

### Charger les skills dans un nœud

```python
# Dans un node LangGraph (ex: app/graph/nodes.py:application_node)
from app.graph.skill_loader import load_skills_for_context
from app.graph.prompt_fusion import fuse_prompt, select_tools_with_skills

async def application_node(state: ConversationState, config) -> ConversationState:
    db = get_db_session()  # ou via dépendance

    # 1. Détecter intent (depuis last user message)
    intent = state["messages"][-1].content if state["messages"] else ""

    # 2. Charger skills selon contexte
    skills = await load_skills_for_context(
        page_slug=state.get("current_page"),
        active_module=state.get("active_module"),
        intent=intent,
        offer_id=state.get("active_module_data", {}).get("offer_id"),
        fund_id=state.get("active_module_data", {}).get("fund_id"),
        intermediary_id=state.get("active_module_data", {}).get("intermediary_id"),
        db=db,
    )

    # 3. Snapshot dans state
    state["active_skills"] = [
        {"id": str(s.id), "name": s.name, "version": s.version} for s in skills
    ]

    # 4. Fusion prompt
    base_system_prompt = build_system_prompt(...)
    fused_prompt = await fuse_prompt(base_system_prompt, skills, db=db)

    # 5. Tools intersection
    base_tools = APPLICATION_TOOLS
    selected_tools = select_tools_with_skills(base_tools, skills)

    # 6. Bind LLM
    llm = get_llm().bind_tools(selected_tools)

    # 7. Invoke
    messages = [SystemMessage(content=fused_prompt)] + state["messages"]
    response = await llm.ainvoke(messages, config)

    # ...
    return state
```

### Ajouter une nouvelle skill au catalogue MVP (post-MVP)

1. Créer un draft via `POST /api/admin/skills`.
2. Calibrer les golden_examples (5-15 cas représentatifs).
3. Tester via `POST /test` jusqu'à atteindre ≥ 90 % de réussite.
4. Publier via `POST /publish`.
5. Vérifier en runtime : ouvrir le frontend, naviguer vers le contexte cible (page, fund, intermediary), envoyer un message → vérifier `state["active_skills"]` contient la nouvelle skill.

## Dépannage

### Le LLM ne charge pas ma skill

Vérifications :

1. **Status published** : `SELECT id, name, status FROM skills WHERE name='skill_xxx';`
2. **Non expirée** : `SELECT id, valid_to FROM skills WHERE name='skill_xxx';` → `valid_to IS NULL` ou `valid_to > today()`.
3. **Activation rules matchent** : vérifier que `page_slug`/`fund_id`/`intermediary_id` du contexte runtime correspondent.
4. **Score de spécificité** : si une skill plus spécifique existe, elle est prioritaire (top 2 max).
5. **Logs LangGraph** : chercher `[skill_loader] loaded skills: [...]` dans les logs serveur.

### Le test conformity échoue : "skill mutation tool detected"

Un développeur a accidentellement créé un tool LangChain avec un nom commençant par `create_skill|update_skill|delete_skill|publish_skill`. **Refuser le merge**. Les Skills ne sont mutables QUE via les endpoints admin.

### Eval gating timeout (504)

Solutions :
- Réduire le nombre de golden_examples (max 10 recommandé).
- Vérifier que le LLM n'est pas saturé (rate limit OpenRouter).
- Augmenter la concurrence parallèle dans `eval_runner.py` (mais attention rate limit).

### Anti-injection faux positif

Si un texte légitime contient un pattern (ex `system prompt` mentionné dans une procédure technique), reformuler. La détection est conservatrice par design (défense en profondeur).

## Métriques de monitoring (post-déploiement)

- **Couverture skills** : `SELECT COUNT(*) FROM skills WHERE status='published';` (objectif : 11 à terme)
- **Taux d'activation skill par tour LLM** : `% des tours où active_skills != []` (objectif : > 60 %)
- **Taux d'échec eval gating** : `% des tentatives publish qui échouent` (objectif : < 30 % — sinon les Admins ne savent pas calibrer)
- **Temps moyen eval gating** : P50, P95 (objectif : P95 < 60s)
- **Audit log injection_attempt_blocked** : alerte si > 5/jour

## Tests E2E (Playwright)

```typescript
// frontend/tests/e2e/admin/skills.spec.ts
test('admin can create, calibrate, publish skill', async ({ page }) => {
  await page.goto('/admin/skills/new');
  await page.fill('[data-test=skill-name]', 'skill_test_e2e');
  await page.selectOption('[data-test=skill-domain]', 'scoring_referentiel');
  // ... fill prompt_expert, procedure, tool_whitelist, sources, activation_rules, golden_examples
  await page.click('[data-test=skill-save]');
  await expect(page.locator('[data-test=skill-status]')).toHaveText('draft');

  // Test sans publier
  await page.click('[data-test=skill-test]');
  await expect(page.locator('[data-test=eval-report-success]')).toBeVisible();

  // Publier
  await page.click('[data-test=skill-publish]');
  await expect(page.locator('[data-test=skill-status]')).toHaveText('published');
});
```

## Références

- Spec F23 : `specs/033-skills-playbooks-metier/spec.md`
- Plan F23 : `specs/033-skills-playbooks-metier/plan.md`
- Data model F23 : `specs/033-skills-playbooks-metier/data-model.md`
- Runner LLM eval F22 : `backend/tests/llm_eval/test_eval_runner.py` (réutilisé)
- Décrire un workflow : `docs/skills-playbooks.md` (à créer)
