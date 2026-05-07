# Phase 0 — Research: F23 Skills (Playbooks Métier)

## R1 — Skill loading runtime patterns

**Question** : comment charger dynamiquement 1-2 skills au runtime LangGraph en fonction du contexte utilisateur ?

**Approches considérées** :

1. **Approche statique par fichier** (rejeté) : lecture de fichiers Markdown du repo selon naming convention. Inconvénients : pas de versioning DB, pas de hot reload, pas d'audit, pas d'eval gating.
2. **Approche similaire Anthropic Skills** (référence) : SKILL.md + activation contextuelle. Compatible avec notre approche BDD-backed.
3. **Approche LangChain function plugin** (rejeté) : pas de mécanisme natif de "skill bundle" couplant prompt + tools + sources. Trop bas niveau.
4. **Approche custom BDD + matching score** (RETENU) : table `skills` en BDD, matching multi-critères au runtime via score de spécificité, fusion prompt + intersection tools.

**Score de spécificité** :

```python
def specificity_score(skill: Skill, ctx: Context) -> float:
    score = 0
    rules = skill.activation_rules

    # Niveau 4 : offer_id explicite (le plus spécifique)
    if rules.get("offer_id") == ctx.offer_id and ctx.offer_id is not None:
        score += 4

    # Niveau 3 : fund_id + intermediary_id combinés
    if rules.get("fund_id") == ctx.fund_id and rules.get("intermediary_id") == ctx.intermediary_id \
            and ctx.fund_id is not None and ctx.intermediary_id is not None:
        score += 3

    # Niveau 2 : fund_id seul OU intermediary_id seul
    if rules.get("fund_id") == ctx.fund_id and ctx.fund_id is not None:
        score += 2
    if rules.get("intermediary_id") == ctx.intermediary_id and ctx.intermediary_id is not None:
        score += 2

    # Niveau 1.5 : active_module
    if ctx.active_module and ctx.active_module in (rules.get("active_module") or []):
        score += 1.5

    # Niveau 1 : page_slug
    if ctx.page_slug and ctx.page_slug in (rules.get("page_slugs") or []):
        score += 1

    # Niveau 0.5 : intent_keywords (si match >= 1 keyword)
    keywords = rules.get("intent_keywords") or []
    if any(kw.lower() in (ctx.intent or "").lower() for kw in keywords):
        score += 0.5

    return score
```

**Décision** : approche custom, score additif, top-2 skills retournées.

## R2 — Format `golden_examples`

**Question** : quel format pour les golden_examples imbriqués dans `skills.golden_examples` ?

**Décision** : aligner sur le schéma F22 (`tests/llm_eval/golden_set.json`) pour réutiliser le runner LLM eval. Schéma JSON :

```typescript
type GoldenExample = {
  id: string;
  category: "diagnostic_esg" | "scoring_referentiel" | "carbon_calc" | "dossier" | "intermediaire" | "attestation" | "credit_score";
  context: {
    current_page: string | null;
    active_module: string | null;
    user_profile?: object;
    offer_id?: string | null;
    fund_id?: string | null;
    intermediary_id?: string | null;
  };
  user_message: string;
  expected: {
    tool_called: string | string[];   // accepte whitelist
    payload_contains?: object;
    fallback_acceptable?: boolean;
  };
  tags?: string[];
};
```

**Avantage** : le runner F22 (`tests/llm_eval/test_eval_runner.py`) peut être appelé comme librairie depuis `app/modules/skills/eval_runner.py` sans dupliquer la logique.

## R3 — Anti-injection patterns

**Question** : comment détecter les tentatives d'injection dans `prompt_expert` ?

**Approches** :

1. **Regex patterns** (RETENU pour MVP) : liste de patterns classiques OWASP LLM Top 10 (LLM01:2023). Avantages : rapide, déterministe, auditable. Inconvénients : faux positifs, contournable par paraphrase.
2. **ML-based classifier** (post-MVP) : modèle dédié type `prompt-guard-86M`. Avantages : meilleure couverture. Inconvénients : latence + coût + dépendance.
3. **LLM-based detection** (post-MVP) : appel d'un modèle "judge" pour classifier. Trop coûteux pour un save fréquent.

**Liste de patterns initiaux** (insensibles à la casse, regex Python) :

| Nom | Pattern |
|---|---|
| `ignore_previous_instructions` | `r"ignore\s+(all\s+)?previous\s+instructions?"` |
| `new_role` | `r"tu\s+es\s+désormais"` ou `r"you\s+are\s+now\s+a"` |
| `system_prompt_leak` | `r"reveal\s+(your\s+)?(system\s+)?prompt"` ou `r"affiche\s+(le\s+)?prompt\s+système"` |
| `user_is_admin` | `r"(user|i)\s+(am|is)\s+admin"` |
| `forget_everything` | `r"forget\s+(everything|all)"` |
| `override_instructions` | `r"override\s+(your\s+)?instructions"` |
| `system_tag` | `r"<\s*system\s*>"` |
| `developer_mode` | `r"developer\s+mode"` ou `r"mode\s+développeur"` |
| `jailbreak_keywords` | `r"DAN|jailbreak"` |
| `prompt_extraction` | `r"repeat\s+(the\s+)?(initial|first)\s+(message|prompt|instructions?)"` |

**Implémentation** :

```python
# app/core/prompt_injection_detector.py
import re

INJECTION_PATTERNS: dict[str, re.Pattern] = {
    "ignore_previous_instructions": re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    "new_role": re.compile(r"tu\s+es\s+désormais|you\s+are\s+now\s+a", re.IGNORECASE),
    "system_prompt_leak": re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt|affiche\s+(le\s+)?prompt\s+système", re.IGNORECASE),
    # ...
}

def detect_injection_patterns(text: str) -> list[str]:
    return [name for name, pattern in INJECTION_PATTERNS.items() if pattern.search(text)]
```

## R4 — Token counting

**Question** : comment mesurer la longueur du `prompt_expert` (limite 5000 tokens) ?

**Décision** : `tiktoken` avec encoding `cl100k_base` (compatible Claude 3.5/4 et GPT-4).

```python
import tiktoken

_encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(_encoder.encode(text))
```

**Performance** : ~1ms par 1000 tokens. Acceptable pour validation au save (rare, latence non critique).

**Vérifier** : `tiktoken` est-il déjà dans `requirements.txt` ? Si non, ajouter.

## R5 — JSONB GIN index PostgreSQL

**Question** : comment indexer `activation_rules` pour des requêtes rapides type `WHERE activation_rules->'page_slugs' ? '/esg'` ?

**Décision** : index GIN sur la colonne JSONB.

```sql
CREATE INDEX ix_skills_activation_rules_gin ON skills USING gin (activation_rules);
```

**Requête type** :

```sql
SELECT * FROM skills
WHERE status = 'published'
  AND (valid_to IS NULL OR valid_to > CURRENT_DATE)
  AND (
    activation_rules->'page_slugs' ? '/esg'
    OR activation_rules->'active_module' ? 'esg_scoring'
    OR (activation_rules->>'fund_id') = 'GCF_UUID'
  );
```

**Compatibilité tests SQLite** : SQLite 3.45+ supporte JSON1 mais pas l'opérateur `?`. Les tests SQLite utilisent `json_extract()` ou chargent toutes les skills `published` puis filtrent en Python. Acceptable car volumétrie test < 50 skills.

## R6 — Versioning semver auto-incrément

**Question** : comment incrémenter automatiquement la version semver à l'édition d'une skill `published` ?

**Décision** : `python-semver` lib (déjà disponible si F04 est mergé, sinon ajouter `semver>=3.0.0`).

```python
import semver

def increment_patch_version(version: str) -> str:
    return str(semver.Version.parse(version).bump_patch())

# 1.0.0 → 1.0.1
# 1.2.5 → 1.2.6
```

**Workflow édition skill `published`** :

1. PATCH `/api/admin/skills/{id}` avec body modifié
2. Service détecte `status=published` → appelle `_create_new_version(skill, body)` :
   - Nouvelle ligne : `id=uuid4()`, `version=increment_patch_version(skill.version)`, `status="draft"`, autres champs = body merged
   - **Ne touche PAS l'ancienne ligne** (reste published, valid_to=null pour le moment)
3. Retourne le nouveau `id` à l'admin
4. Admin appelle `POST /publish` sur le nouveau id → eval gating → si OK :
   - Nouvelle skill : `status="published"`
   - Ancienne skill : `valid_to=today()`, `superseded_by=new_id`

## R7 — Eval gating timeout & parallélisation

**Question** : comment tenir le seuil P95 < 60s pour 10 golden_examples (~6s/cas LLM) ?

**Approches** :

1. **Séquentiel** (rejeté) : 10 × 6s = 60s. Pas de marge.
2. **Parallèle asyncio.gather** (RETENU) : 10 cas en parallèle, max 5 concurrent (limite OpenRouter rate limit). Latence ~12s = max(2 batches × 6s).

```python
import asyncio
from itertools import islice

async def run_golden_examples_parallel(examples: list, max_concurrent: int = 5):
    semaphore = asyncio.Semaphore(max_concurrent)
    async def _run_one(ex):
        async with semaphore:
            return await run_single_case(ex)
    return await asyncio.gather(*(_run_one(ex) for ex in examples))
```

**Timeout global** : 60s via `asyncio.wait_for()`. Si dépassé, retourne 504 et la skill reste en `draft`.

## R8 — Réutilisation runner F22

**Question** : comment réutiliser le runner F22 (`tests/llm_eval/test_eval_runner.py`) depuis `app/modules/skills/eval_runner.py` (production code, pas test code) ?

**Décision** : extraire la logique de matching en module utilitaire `app/lib/eval_matching.py` :

```python
# app/lib/eval_matching.py (NOUVEAU)
def match_tool_called(actual: str | None, expected: str | list[str]) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected

def match_payload_contains(actual: dict, expected: dict | None) -> bool:
    if expected is None:
        return True
    return all(actual.get(k) == v for k, v in expected.items())
```

Le test runner F22 importe ce module. F23 `eval_runner.py` aussi. Ainsi, les deux flux (CI et production gating) partagent la même logique de comparaison.

## R9 — Snapshot active_skills dans LangGraph state

**Question** : comment persister `active_skills` à travers les redémarrages serveur (LangGraph checkpointer) ?

**Décision** : ajouter le champ dans `ConversationState` :

```python
class ConversationState(TypedDict):
    # ... champs existants ...
    active_skills: list[dict] | None  # [{id, name, version}]
```

Le LangGraph checkpointer (PostgreSQL) sérialise automatiquement les TypedDict. Pas de modification du checkpointer nécessaire.

**Lifecycle** :

- Début du tour : `state["active_skills"] = [{id, name, version} for s in load_skills_for_context(...)]`
- Pendant le tour : conservé tel quel (pas de re-load au milieu d'un tool call)
- Fin du tour (commit checkpoint) : sérialisé en BDD
- Reprise (next user message) : restauré, MAIS rappel `load_skills_for_context()` au début du nouveau tour → permet le switch vers nouvelle version published si la skill a été éditée entre-temps

## R10 — Frontend admin pages structure

**Question** : comment organiser le formulaire 8 onglets pour ne pas overwhelm l'admin ?

**Approches** :

1. **8 onglets fixes** (RETENU) : Identité, Prompt expert, Procédure, Tools whitelist, Sources, Activation rules, Golden examples, Tests. Navigation horizontale, validation par onglet.
2. **Wizard step-by-step** (rejeté) : trop rigide pour itérations.
3. **Page unique scroll** (rejeté) : trop long, perte de contexte.

**Composants par onglet** :

| Onglet | Composant principal |
|---|---|
| Identité | inputs name, domain, version (auto), valid_from/valid_to |
| Prompt expert | textarea avec compteur tokens en temps réel + alerte si > 5000 |
| Procédure | textarea markdown |
| Tools whitelist | `ToolWhitelistPicker` (multi-select avec recherche) |
| Sources | `SourceMultiPicker` (filter sources verified, multi-select) |
| Activation rules | `ActivationRulesEditor` (page_slugs/intent_keywords/active_module/offer_id/fund_id/intermediary_id) |
| Golden examples | `GoldenExamplesEditor` (liste de 5-15 cas, JSON form guidé) |
| Tests | `SkillEvalRunner` (bouton "Tester (sans publier)" + affichage rapport, "Publier" déclenche gating) |

## Décisions clés résumées

| ID | Décision | Justification |
|---|---|---|
| D1 | Score de spécificité multi-critères additif | Permet sélection granulaire offer_id > fund_id+intermediary_id > page_slug |
| D2 | Format golden_examples aligné F22 | Réutilisation du runner, cohérence des métriques |
| D3 | Anti-injection regex first | MVP rapide, déterministe, faux positifs acceptés |
| D4 | tiktoken cl100k_base | Compatible Claude/GPT-4, perf ~1ms/1k tokens |
| D5 | Index GIN sur activation_rules | Requêtes < 50ms P95 même avec 1000 skills |
| D6 | Patch version auto-incrément | Workflow édition publiée → nouvelle version transparent |
| D7 | Parallélisation asyncio max 5 concurrent | Timeout 60s P95 tenable |
| D8 | Module commun `app/lib/eval_matching.py` | DRY entre runner F22 et eval_runner F23 |
| D9 | Champ `active_skills` dans ConversationState | Snapshot multi-tour gratuit via checkpointer |
| D10 | 8 onglets fixes | Balance entre découpage et fluidité |
