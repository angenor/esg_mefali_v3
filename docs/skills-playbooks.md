# F23 — Skills (Playbooks Métier)

Ce document décrit le cycle de vie complet d'une **Skill** (playbook métier
réutilisable) dans Mefali : de la création jusqu'à la mise en production
runtime via le loader contextuel LangGraph.

## 1. Concept

Une **Skill** est un bundle métier qui combine :

- `prompt_expert` (≤ 5000 tokens) — le prompt focalisé domaine.
- `procedure` (≤ 3000 tokens) — la marche à suivre pas-à-pas.
- `tool_whitelist` — sous-ensemble de tools LangChain autorisés pour la skill.
- `sources` — UUIDs de Sources verified pré-résolues.
- `activation_rules` — règles de chargement contextuel (page_slugs,
  intent_keywords, active_module, offer_id, fund_id, intermediary_id).
- `golden_examples` — 5 à 15 cas de test pour le gating à la publication.

Les Skills sont chargées dynamiquement par `app/graph/skill_loader.py` au
début de chaque tour LLM dans 7 nœuds (chat, esg_scoring, carbon, financing,
application, credit, action_plan), fusionnées dans le system prompt et leur
tool whitelist est intersectée avec les tools de la page courante.

## 2. Cycle de vie

```
[draft] → calibration golden_examples → test → publish (eval gating ≥ 90 %) →
[published] → édition → nouvelle version draft (semver patch+1) → publish →
ancienne version reçoit valid_to + superseded_by
```

## 3. Créer une Skill

### Via API admin

```bash
POST /api/admin/skills
Authorization: Bearer <admin_jwt>
Content-Type: application/json

{
  "name": "skill_dossier_gcf_via_boad",
  "domain": "dossier",
  "prompt_expert": "Tu es un expert dans le montage de dossiers GCF via BOAD...",
  "procedure": "1) Vérifier l'éligibilité. 2) Initialiser. ...",
  "tool_whitelist": ["create_fund_application", "update_company_profile"],
  "sources": ["uuid-source-1", "uuid-source-2"],
  "activation_rules": {
    "page_slugs": ["/applications"],
    "intent_keywords": ["dossier", "GCF", "BOAD"],
    "active_module": ["application"],
    "fund_id": "GCF_UUID",
    "intermediary_id": "BOAD_UUID"
  },
  "golden_examples": []
}
```

Retour : `201 Created` avec `SkillRead` (status=`draft`, version=`1.0.0`).

### Via frontend admin

Naviguer vers `/admin/skills/new`, remplir les 8 onglets (Identité, Prompt
expert, Procédure, Tools, Sources, Activation, Golden examples, Tests),
puis valider. La skill est créée en `draft`.

## 4. Calibrer les golden_examples

Une Skill doit avoir entre **5 et 15** golden_examples pour pouvoir être
publiée. Format aligné avec F22 :

```json
{
  "id": "gcf-boad-init-01",
  "category": "dossier",
  "context": {
    "current_page": "/applications",
    "active_module": "application",
    "fund_id": "GCF_UUID",
    "intermediary_id": "BOAD_UUID"
  },
  "user_message": "Je veux préparer mon dossier GCF via BOAD pour mon projet solaire",
  "expected": {
    "tool_called": "create_fund_application",
    "payload_contains": {"fund_id": "GCF_UUID", "intermediary_id": "BOAD_UUID"}
  },
  "tags": ["initialisation", "GCF", "BOAD"]
}
```

`expected.tool_called` accepte une string OU une liste (whitelist tolérante).

## 5. Tester sans publier

```bash
POST /api/admin/skills/{id}/test
```

Retourne un `SkillEvalReport` (mêmes métriques que `publish`) sans modifier
le status. Utiliser ce endpoint pendant la calibration.

## 6. Publier (eval gating)

```bash
POST /api/admin/skills/{id}/publish
```

Workflow :

1. Vérifie `len(golden_examples) >= 5` (sinon `422 insufficient_golden_examples`).
2. Exécute `run_skill_eval()` (parallèle, max 5 concurrents, timeout 60s).
3. Si `success_rate < 0.9` → `422 gate_failed` + rapport. La skill **reste
   draft**.
4. Si `success_rate >= 0.9` → `status=published`. Audit log.

Cap performance : ≤ 90s P95. Si dépassé → `504 eval_timeout`.

## 7. Versioning (édition skill published)

Quand une skill `published` est éditée via `PATCH /api/admin/skills/{id}` :

1. Une **nouvelle ligne** est créée (`status=draft`, `version=1.0.1`).
2. L'ancienne ligne reste **intacte** (toujours published, `valid_to=NULL`).
3. L'admin appelle `POST /publish` sur le nouvel id.
4. Si gate passé : nouvelle skill devient `published` ; ancienne reçoit
   `valid_to=today()` + `superseded_by=<new_id>`.
5. Les conversations en cours conservent leur snapshot `state["active_skills"]`
   pendant le tour ; au prochain message utilisateur, le loader renvoie la
   nouvelle version published.

## 8. Anti-injection

Le validator détecte 10 patterns d'injection OWASP LLM Top 10 dans
`prompt_expert` et `procedure` :

| Pattern | Exemples |
|---|---|
| `ignore_previous_instructions` | "Ignore previous instructions" |
| `new_role` | "Tu es désormais", "You are now a" |
| `system_prompt_leak` | "Reveal system prompt", "Affiche le prompt système" |
| `user_is_admin` | "User is admin", "I am admin" |
| `forget_everything` | "Forget everything", "Forget all" |
| `override_instructions` | "Override your instructions" |
| `system_tag` | `<system>` |
| `developer_mode` | "Developer mode", "Mode développeur" |
| `jailbreak_keywords` | "DAN", "jailbreak" |
| `prompt_extraction` | "Repeat the initial prompt" |

Si un pattern est détecté au save → `422 detected_patterns`. La skill n'est
pas insérée.

**Guidelines pour rédiger un prompt expert sûr** :

- Utilisez un ton instructif positif ("Tu es un expert..." ✓).
- Évitez les méta-instructions sur l'IA elle-même ("Ignore..." ✗).
- Citez les sources métier (BCEAO, UEMOA, ODD), pas le system prompt.
- Si un pattern est faux-positif, reformulez en gardant l'intention.

## 9. Loader contextuel

`app/graph/skill_loader.py:load_skills_for_context()` charge **0 à 2** skills
par tour, basées sur un score de spécificité multi-critères :

| Niveau | Critère | Score |
|---|---|---|
| 4 | offer_id (le plus spécifique) | +4.0 |
| 3 | combo fund_id + intermediary_id | +3.0 |
| 2 | fund_id seul | +2.0 |
| 2 | intermediary_id seul | +2.0 |
| 1.5 | active_module | +1.5 |
| 1 | page_slug | +1.0 |
| 0.5 | intent_keywords (≥ 1 keyword matché) | +0.5 |

Cap budget tokens : 12 000 tokens (base prompt + skills). Si dépassé, charge
1 skill au lieu de 2.

## 10. Tools réservés admin

Aucun tool LangChain `create_skill`, `update_skill`, `delete_skill`,
`publish_skill`, `unpublish_skill` n'est exposé au LLM. Test conformity
bloquant : `tests/graph/tools/test_no_skill_mutation_tool.py`.

Les Skills ne peuvent être mutées QUE via les endpoints admin
`/api/admin/skills/*` (auth `Depends(get_current_admin)`).

## 11. Seed initial

3 skills MVP critiques sont seedées via :

```bash
cd backend
source venv/bin/activate
python scripts/seed_skills.py
```

Skills :
- `skill_esg_diagnostic` — diagnostic ESG sur 30 critères.
- `skill_score_gcf` — pré-évaluation projet vs critères GCF.
- `skill_dossier_gcf_via_boad` — montage dossier GCF via BOAD.

Le script est idempotent (vérifie les noms existants avant insert).

## 12. Audit log

Toutes les mutations émettent une entrée dans `audit_log` (F03) avec
`source_of_change="admin"` (middleware `AdminAuditContextMiddleware`) :

| Action | Métadonnées |
|---|---|
| `skill_created` | `{name, domain, version}` |
| `skill_updated` | `{changes}` |
| `skill_published` | `{eval_report, version}` |
| `skill_unpublished` | `{previous_version}` |
| `skill_deleted` | `{name, version}` |
| `skill_superseded` | `{old_id, new_id, old_version, new_version}` |
| `injection_attempt_blocked` | `{detected_patterns, prompt_excerpt}` |

## 13. Performance cibles

| Endpoint | P95 |
|---|---|
| GET /skills | < 200ms (pagination 20) |
| GET /skills/{id} | < 100ms |
| POST /skills | < 300ms |
| PATCH /skills/{id} | < 300ms |
| POST /skills/{id}/test | < 60s |
| POST /skills/{id}/publish | < 90s |
| POST /skills/{id}/unpublish | < 100ms |
| DELETE /skills/{id} | < 100ms |

Loader runtime : < 50ms P95 (1 requête SQL avec index GIN sur PG).
Fusion prompt : < 100ms P95 (≤ 2 skills + résolution sources).

## 14. Diagnostic & dépannage

### Pourquoi ma skill n'est pas chargée à `/esg` ?

1. Vérifier que la skill est `published` ET non expirée
   (`valid_to IS NULL OR valid_to > today`).
2. Vérifier `activation_rules.page_slugs` contient `"/esg"`.
3. Logs serveur : grep `[skill_loader] loaded`.

### Pourquoi le gate echoue toujours alors que mon prompt est bon ?

- Vérifier que les golden_examples utilisent les bons noms de tools
  (matchent EXACTEMENT le `name` du `@tool` LangChain).
- Vérifier `expected.payload_contains` ne contient pas de clés que le
  LLM ne pourra jamais déduire du `user_message`.
- Tester d'abord via `POST /test` puis raffiner.

### Erreur `tool_name_unknown` au save

Vérifier que `tool_whitelist` contient uniquement des noms de tools réels
et exposés. Pour lister les noms disponibles :

```python
from app.modules.skills.validator import _collect_all_tool_names
print(_collect_all_tool_names())
```

## 15. Références

- Spec : `specs/033-skills-playbooks-metier/spec.md`.
- Plan : `specs/033-skills-playbooks-metier/plan.md`.
- Data model : `specs/033-skills-playbooks-metier/data-model.md`.
- Contracts REST : `specs/033-skills-playbooks-metier/contracts/admin_skills_endpoints.md`.
