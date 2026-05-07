# Quickstart — F22 LLM Eval Loop

## 1. Lancer le golden set en local

```bash
cd backend
source venv/bin/activate
export OPENROUTER_API_KEY=sk-...

# Run complet (50 cas, ~5-10 min, ~$2)
pytest tests/llm_eval/ -m eval --golden-report=eval-report.json -v

# Run un seul cas (debug)
pytest tests/llm_eval/test_eval_runner.py::test_golden_case[01-profile-set-sector] -v

# Run par catégorie
pytest tests/llm_eval/ -m eval -k "profilage" -v
```

Le rapport `eval-report.json` est généré à la racine du backend.

## 2. Interpréter `eval-report.json`

```bash
# Lire les métriques globales
cat eval-report.json | jq '.metrics'

# Lister les cas en échec
cat eval-report.json | jq '.results[] | select(.status == "fail") | {case_id, expected_tool, actual_tool}'

# Vérifier les gates CI
python -c "
import json
r = json.load(open('eval-report.json'))
m = r['metrics']
assert m['tool_match_rate'] >= 0.90, f'tool_match_rate={m[\"tool_match_rate\"]} < 0.90'
assert m['payload_valid_rate'] >= 0.95, f'payload_valid_rate={m[\"payload_valid_rate\"]} < 0.95'
assert m['hallucination_rate'] < 0.01, f'hallucination_rate={m[\"hallucination_rate\"]} > 0.01'
print('✓ All gates passed')
"
```

## 3. Ajouter un nouveau cas au golden set

1. Identifier un scénario réel (depuis `conversations` table ou rapport bug).
2. Ajouter une entrée dans `backend/tests/llm_eval/golden_set.json` :

```json
{
  "id": "51-credit-momo-import",
  "category": "credit",
  "context": {"current_page": "/credit-score", "active_module": "credit"},
  "user_message": "J'ai 3 mois de relevés Mobile Money à uploader",
  "expected": {
    "tool_called": "ask_file_upload",
    "payload_contains": {"accept": ["application/pdf", "image/*"]}
  },
  "tags": ["credit", "upload"]
}
```

3. Exécuter le test : `pytest tests/llm_eval/test_eval_runner.py -k 51-credit -v`.
4. Si le cas passe (LLM invoque bien le tool attendu), commit.
5. Si le cas échoue, deux options :
   - Le LLM se trompe → améliorer le prompt / docstring tool, puis re-run
   - L'expected est mal calibré → ajuster (ajouter une whitelist `tool_called: ["ask_file_upload", "ask_qcu"]`)

## 4. Déclencher manuellement la CI eval

Sur GitHub :

```bash
gh workflow run llm-eval.yml --ref feat/F22-decision-tree-with-retry-eval
```

Ou en commit dummy sur fichier filtré :

```bash
echo "# trigger eval" >> backend/app/prompts/system.py
git commit -am "ci: trigger llm eval"
git push
```

## 5. Comprendre les métriques

| Métrique | Définition | Gate |
|----------|------------|------|
| `tool_match_rate` | % de cas où `actual_tool ∈ expected_tool` (whitelist supportée) | >= 0.90 |
| `payload_valid_rate` | % de cas où `subset_match(actual_payload, expected.payload_contains) == True` | >= 0.95 |
| `hallucination_rate` | % de cas où le LLM invoque un tool qui n'existe pas dans le registre | < 0.01 |
| `fallback_rate` | % de cas où `with_retry` retourne `{"success": False, "fallback_message": ...}` | < 0.05 (warning) |

## 6. Troubleshooting

### Le test échoue avec `OPENROUTER_API_KEY missing`

```bash
export OPENROUTER_API_KEY=sk-...
# OU dans .env (chargé via python-dotenv)
```

### Le test prend > 30 min

- Vérifier qu'on n'utilise pas Opus (cher et lent) : `LLM_MODEL` dans `app/core/config.py`
- Lancer en parallèle (phase 2) : `pytest -n 4 tests/llm_eval/ -m eval`

### Un cas légitime échoue à cause d'un tool synonyme

Convertir `expected.tool_called` en whitelist :

```json
"expected": {
  "tool_called": ["ask_qcu", "ask_select"],
  ...
}
```

### Comment monitorer les `validation_error` en production ?

```bash
# Endpoint admin
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://api.esg-mefali.com/api/admin/metrics/validation-failures?period=7d&limit=10"
```

Réponse :

```json
{
  "period": "7d",
  "total_calls": 12345,
  "failure_count": 234,
  "failure_rate": 0.019,
  "top_tools": [...],
  "alert": false
}
```

Si `alert: true` → alerter l'équipe et investiguer le top tool concerné.

## 7. Process de mise à jour

À chaque PR qui modifie :

- `app/prompts/**` → review obligatoire du golden set
- `app/graph/tools/**` → ajouter cas pour les nouveaux tools, retirer cas pour tools supprimés
- Modèle LLM (`LLM_MODEL`) → re-run complet attendu, calibrer si dérive

## 8. Références

- Spec : [spec.md](./spec.md)
- Plan : [plan.md](./plan.md)
- Schéma cas : [contracts/golden_case_schema.json](./contracts/golden_case_schema.json)
- Schéma rapport : [contracts/eval_report_schema.json](./contracts/eval_report_schema.json)
- Endpoint admin : [contracts/admin_metrics_endpoint.md](./contracts/admin_metrics_endpoint.md)
