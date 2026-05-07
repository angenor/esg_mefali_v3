# Phase 0 — Research: F22 Decision Tree + with_retry + Golden Set

**Date** : 2026-05-07
**Auteur** : SpecKit Phase A (autonome)

## R1 — Pattern décorateur `@with_retry` LangChain

**Question** : comment intercepter `pydantic.ValidationError` dans le décorateur sans casser le retour structuré `requires_destructive_confirmation` (F10) ?

**Décision** : `with_retry` reçoit déjà l'exception via `try/except Exception as e`. Pour distinguer :

- Une `ValidationError` Pydantic → on extrait `e.errors()` et on l'enregistre dans `tool_call_logs.validation_error` (jsonb).
- Une exception runtime quelconque (`ValueError`, `RuntimeError`, etc.) → on enregistre `e` dans `error_message` (TEXT, déjà existant), pas dans `validation_error`.
- Le retour `requires_destructive_confirmation` est une string JSON sérialisée (pas une exception) → `with_retry` ne déclenche pas de retry, c'est un succès au sens du décorateur. Le tool a retourné une valeur valide.

**Implémentation** :

```python
from pydantic import ValidationError

@wraps(func)
async def wrapper(*args, **kwargs):
    last_validation_error = None
    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            # ... log success (avec validation_error=last_validation_error si retry réussi)
            return result
        except ValidationError as ve:
            last_validation_error = [dict(err) for err in ve.errors()]
            if attempt < max_retries:
                # log retry avec validation_error
                continue
            # last attempt failed → fallback
            if fallback_message:
                return json.dumps({"success": False, "fallback_message": fallback_message})
            return f"Erreur : {ve}"
        except Exception as e:
            # ... log error_message classique
            if attempt < max_retries:
                continue
            if fallback_message:
                return json.dumps({"success": False, "fallback_message": fallback_message})
            return f"Erreur : {e}"
```

**Alternative rejetée** : utiliser un gestionnaire `tenacity` externe → ajout dépendance, complique débogage des cas LangGraph spécifiques.

## R2 — Format `eval-report.json`

**Question** : aligner sur conventions LangSmith / promptfoo ou format custom ?

**Décision** : format custom minimaliste (pas de dépendance externe). Schéma documenté dans `contracts/eval_report_schema.json`.

**Justification** :
- Pas besoin d'intégration LangSmith pour MVP
- promptfoo a un format `.yaml`, plus complexe que ce dont on a besoin
- Format JSON simple = facilement parsable côté CI + dashboard futur

**Format** :

```json
{
  "run_id": "uuid",
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "model": "claude-3-5-sonnet-20241022",
  "total_cases": 50,
  "passed": 47,
  "failed": 3,
  "results": [
    {
      "case_id": "01-profile-set-sector",
      "status": "pass",
      "actual_tool": "update_company_profile",
      "expected_tool": "update_company_profile",
      "payload_diff": null,
      "latency_ms": 1234,
      "tokens_used": 567
    },
    {
      "case_id": "23-esg-finalize",
      "status": "fail",
      "actual_tool": "ask_qcu",
      "expected_tool": ["finalize_esg_assessment", "ask_yes_no"],
      "payload_diff": {"missing": ["assessment_id"]},
      "latency_ms": 1856,
      "tokens_used": 612
    }
  ],
  "metrics": {
    "tool_match_rate": 0.94,
    "payload_valid_rate": 0.96,
    "hallucination_rate": 0.0,
    "fallback_rate": 0.02
  }
}
```

## R3 — Path-filter GitHub Actions

**Question** : comment déclencher le step LLM eval uniquement si certains chemins changent ?

**Décision** : utiliser l'action `dorny/paths-filter@v3` (standard, > 10k stars).

**Implémentation** :

```yaml
  changes:
    runs-on: ubuntu-22.04
    outputs:
      llm-relevant: ${{ steps.filter.outputs.llm-relevant }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            llm-relevant:
              - 'backend/app/prompts/**'
              - 'backend/app/graph/tools/**'
              - 'backend/tests/llm_eval/**'

  llm-eval:
    needs: changes
    if: ${{ needs.changes.outputs.llm-relevant == 'true' }}
    runs-on: ubuntu-22.04
    # ... reste comme avant
```

**Alternative rejetée** : `github.event.pull_request.changed_files` direct (syntaxe peu portable et fragile).

## R4 — Calibrage golden set (50 cas)

**Question** : quels cas sont vraiment représentatifs ?

**Décision** : panier équilibré couvrant les 8 modules métier + cas génériques :

| Module | Nb cas | Exemples |
|--------|--------|----------|
| Profilage (entreprise + projets F06) | 10 | « Mon entreprise est dans l'agriculture », « Crée un projet de panneaux solaires », « Mets à jour le CA », « Supprime ce projet » |
| ESG (saisie + finalize + multi-réf F13) | 8 | « Mon score énergie est de 70 », « Finalise l'évaluation », « Compare GCF et IFC standards » |
| Carbone (saisie + facteurs F17) | 6 | « 1200 L de diesel », « C'est quoi le facteur diesel ? », « Quel est mon bilan ? » |
| Financement (matching F14, simulateur F16, comparateur) | 6 | « Quel fonds pour mon projet ? », « Compare BOAD vs UNDP », « Simule un prêt à 6,5 % » |
| Applications (création F15, statut, génération section) | 6 | « Crée un dossier GCF », « Statut de ma candidature », « Génère la section budget » |
| Crédit (Mobile Money, photos, attestation F08) | 5 | « Génère mon score crédit », « Voici 3 mois de relevés MoMo », « Génère mon attestation » |
| Plan d'action | 4 | « Génère mon plan », « Marque cette action faite », « Voir mon plan » |
| Conversationnel | 5 | « Oui », « Non », « Récapitule notre échange précédent », greeting, mots ambigus |
| **Total** | **50** | |

**Sources** : conversations historiques (`conversations` table) anonymisées + cas synthétiques calibrés sur le decision tree.

## R5 — Token counting pour budget prompt

**Question** : comment mesurer la croissance de tokens du prompt ?

**Décision** : comparaison brute longueur caractères (proxy stable, indépendant du modèle).

**Justification** : `tiktoken` est lié à OpenAI ; Anthropic Claude utilise un autre tokenizer (BPE différent). Pour un gate +25 %, la longueur en caractères est un proxy suffisamment correlé (~3 chars/token en moyenne, ratio stable sur français).

**Implémentation** :

```python
# backend/tests/unit/prompts/test_system_prompt_decision_tree.py

import json
from pathlib import Path

BASELINE_PATH = Path(__file__).parent / "_tokens_baseline.json"

def test_decision_tree_token_budget():
    from app.prompts.system import BASE_PROMPT
    new_length = len(BASE_PROMPT)

    if not BASELINE_PATH.exists():
        BASELINE_PATH.write_text(json.dumps({"BASE_PROMPT": new_length}, indent=2))
        return  # bootstrap

    baseline = json.loads(BASELINE_PATH.read_text())["BASE_PROMPT"]
    growth = (new_length - baseline) / baseline
    assert growth < 0.25, f"BASE_PROMPT a grossi de {growth:.1%}, gate = +25 %"
```

**Process** : si on accepte la croissance, on régénère le baseline et on commit.

## R6 — Endpoint admin metrics

**Question** : quelle structure de réponse / quels filtres ?

**Décision** : endpoint `GET /api/admin/metrics/validation-failures?period=7d&limit=10`.

**Réponse** :

```json
{
  "period": "7d",
  "from_iso": "2026-04-30T00:00:00Z",
  "to_iso": "2026-05-07T00:00:00Z",
  "total_calls": 12345,
  "failure_count": 234,
  "failure_rate": 0.019,
  "top_tools": [
    {"tool_name": "batch_save_esg_criteria", "count": 89, "rate": 0.038},
    {"tool_name": "create_fund_application", "count": 45, "rate": 0.022}
  ],
  "alert": false,
  "alert_threshold": 0.05
}
```

**Garde-fou** : `alert=true` si `failure_rate > 0.05`.

## R7 — Cassette cache LLM (hors phase 1)

**Question** : faut-il cacher les réponses LLM pour réduire coût CI ?

**Décision** : **hors-scope F22**. À évaluer en F22b si le coût mensuel dépasse $100. Outils possibles :
- `pytest-recording` (cassettes VCR-like)
- `langchain.cache.SQLiteCache`
- Cache custom en JSON

Pour MVP : path-filter + run manuel suffisent.

## R8 — Compatibilité tests existants

**Question** : risque de casser `test_tools_meta_conformity.py` quand on étend SCOPE_TOOLS ?

**Décision** : extension incrémentale + verification phase par phase.

**Process** :

1. Étendre SCOPE_TOOLS avec un nouveau groupe (ex: CARBON_TOOLS)
2. Run le test → identifier les échecs (docstrings non conformes)
3. Corriger les docstrings une par une
4. Run le test à chaque correction
5. Merger le groupe quand toutes les assertions passent
6. Répéter pour le groupe suivant

L'ordre : `CARBON_TOOLS` → `CHAT_TOOLS` → `DOCUMENT_TOOLS` → `CREDIT_TOOLS` → `ACTION_PLAN_TOOLS` → `FINANCING_TOOLS` (le plus gros) → `GUIDED_TOUR_TOOLS` → `SOURCING_TOOLS` (F01) → `PROJECT_TOOLS` (F06) → `VISUALIZATION_TOOLS` (F11) → `MEMORY_TOOLS` (F12).

## R9 — Conflit `with_retry` + `requires_destructive_confirmation`

**Question** : comment garantir que le retour structuré F10 ne déclenche pas un retry inutile ?

**Décision** : `requires_destructive_confirmation` retourne une **chaîne JSON** (pas d'exception). Le décorateur `with_retry` ne voit pas d'exception → cas considéré comme succès, pas de retry.

**Vérification** : test unitaire `test_with_retry_destructive_confirmation_passthrough`.

## R10 — Format docstring 5 sections (rappel gabarit story 10.1)

**Question** : confirmer le gabarit applicable à tous les tools ?

**Décision** : gabarit story 10.1 actuel, validé par 14 tools déjà conformes.

```python
"""Verbe d'action en une phrase courte (>= 10 chars).

Use when:
- Bullet 1 : cas d'usage 1
- Bullet 2 : cas d'usage 2
- (>= 2 bullets requis)

Don't use when:
- Anti-cas 1 — utiliser `tool_alternatif1` à la place
- Anti-cas 2 — utiliser `tool_alternatif2` à la place
- (>= 2 bullets, doit nommer un tool alternatif via backticks)

Exemple:
[Cas concret avec contexte + payload]

Anti:
[Cas où il ne faut pas l'utiliser, avec alternative]
"""
```

Longueur totale >= 200 caractères.
