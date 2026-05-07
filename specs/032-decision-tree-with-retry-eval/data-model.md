# Phase 1 — Data Model: F22

## Entité 1 — `tool_call_logs.validation_error` (extension)

**Table existante** : `tool_call_logs`

**Colonne ajoutée** : `validation_error: jsonb | null`

**Schéma** :

```python
# backend/app/models/tool_call_log.py — extension
class ToolCallLog(Base):
    # ... colonnes existantes ...
    validation_error: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Pydantic ValidationError.errors() liste, null si succès du premier coup",
    )
```

**Format `validation_error`** : liste Python sérialisée jsonb.

```json
[
  {
    "type": "missing",
    "loc": ["sector"],
    "msg": "Field required",
    "input": {"company_name": "Acme"}
  },
  {
    "type": "string_too_short",
    "loc": ["company_name"],
    "msg": "String should have at least 1 character",
    "input": ""
  }
]
```

**Index** : pas d'index dédié (volume estimé < 5 % des logs, table partitionnable plus tard).

**Migration** : `032_add_validation_error_tool_call_logs.py` (nullable, default null, zero-downtime).

## Entité 2 — Golden Case (JSON file)

**Fichier** : `backend/tests/llm_eval/golden_set.json`

**Schéma JSON Schema** : `contracts/golden_case_schema.json`

**Structure** :

```typescript
type GoldenSet = {
  version: string;          // "1.0"
  description: string;
  generated_at: string;     // ISO8601
  cases: GoldenCase[];      // 50 cas
};

type GoldenCase = {
  id: string;               // ex: "01-profile-set-sector"
  category: "profilage" | "esg" | "carbon" | "financing" | "applications" | "credit" | "action_plan" | "conversational";
  context: {
    current_page: string | null;        // ex: "/profile", "/esg", null
    active_module: string | null;        // ex: "esg_scoring", null
    user_profile?: object;               // payload partiel (sector, country, etc.)
  };
  user_message: string;
  expected: {
    tool_called: string | string[];      // un seul nom OU whitelist
    payload_contains?: object;           // subset attendu dans tool_args
    fallback_acceptable?: boolean;       // si true, accepte un fallback comme succès
  };
  tags: string[];           // ex: ["mutation", "destructive"]
};
```

**Exemple** :

```json
{
  "id": "01-profile-set-sector",
  "category": "profilage",
  "context": {
    "current_page": "/profile",
    "active_module": null
  },
  "user_message": "Mon entreprise est dans l'agriculture biologique",
  "expected": {
    "tool_called": "update_company_profile",
    "payload_contains": {"sector": "agriculture"}
  },
  "tags": ["mutation", "profile"]
}
```

## Entité 3 — Eval Report (JSON output)

**Fichier généré** : `backend/eval-report.json` (gitignored, artifact CI)

**Schéma JSON Schema** : `contracts/eval_report_schema.json`

**Structure** :

```typescript
type EvalReport = {
  run_id: string;           // uuid
  started_at: string;       // ISO8601
  completed_at: string;     // ISO8601
  duration_seconds: number;
  model: string;            // ex: "anthropic/claude-3-5-sonnet-20241022"
  total_cases: number;
  passed: number;
  failed: number;
  results: CaseResult[];
  metrics: Metrics;
};

type CaseResult = {
  case_id: string;
  status: "pass" | "fail" | "partial";
  actual_tool: string | null;          // null si aucun tool invoqué
  expected_tool: string | string[];
  payload_diff: object | null;          // null si payload OK
  latency_ms: number;
  tokens_used: number;
  error?: string;
};

type Metrics = {
  tool_match_rate: number;       // 0.0 - 1.0
  payload_valid_rate: number;    // 0.0 - 1.0
  hallucination_rate: number;    // 0.0 - 1.0
  fallback_rate: number;         // 0.0 - 1.0
  by_category: {
    [category: string]: {
      cases: number;
      tool_match_rate: number;
      payload_valid_rate: number;
    };
  };
};
```

**Gates CI** :

- `metrics.tool_match_rate < 0.90` → CI échoue
- `metrics.payload_valid_rate < 0.95` → CI échoue
- `metrics.hallucination_rate > 0.01` → CI échoue
- `metrics.fallback_rate > 0.05` → warning (non bloquant)

## Entité 4 — Decision Tree (constante Python)

**Fichier** : `backend/app/prompts/system.py`

**Type** : `str` (constante)

**Section ajoutée à `BASE_PROMPT`** : voir spec FR-001/FR-002.

```python
DECISION_TREE: str = """
## ARBRE DE DÉCISION TOOL — RÈGLES OBLIGATOIRES
...
"""

ANTI_PATTERNS: str = """
## ANTI-PATTERNS À ÉVITER
...
"""

BASE_PROMPT = f"""
{base_existant}

{DECISION_TREE}

{ANTI_PATTERNS}
"""
```

**Validation** : test `test_decision_tree_present_in_prompt` (présence + budget tokens < +25 %).

## Entité 5 — Endpoint réponse (admin metrics)

**Endpoint** : `GET /api/admin/metrics/validation-failures`

**Query params** :
- `period: str = "7d"` — valeurs : `"24h" | "7d" | "30d"`
- `limit: int = 10` — top N tools

**Response Pydantic** :

```python
class TopToolFailure(BaseModel):
    tool_name: str
    count: int
    rate: float = Field(..., description="failures / total calls of this tool")

class ValidationFailuresResponse(BaseModel):
    period: Literal["24h", "7d", "30d"]
    from_iso: datetime
    to_iso: datetime
    total_calls: int
    failure_count: int
    failure_rate: float
    top_tools: list[TopToolFailure]
    alert: bool
    alert_threshold: float = 0.05
```

**Auth** : `Depends(require_admin_role)`.

**Index utilisés** : `idx_tool_call_logs_created_at_status` (déjà existant), filtre `WHERE validation_error IS NOT NULL`.

## Relations

```text
[utilisateur LLM] → invoque tool → [@with_retry] →
                                       ↓ (succès)
                                  [tool_call_logs row, validation_error=null]
                                       ↓ (échec ValidationError)
                                  [retry] →
                                       ↓ (succès retry)
                                  [tool_call_logs row, validation_error=<errors[]>, status="retry_success"]
                                       ↓ (échec retry)
                                  [tool_call_logs row, validation_error=<errors[]>, status="error"]
                                  + return {"success": False, "fallback_message": "..."} (si décoré avec fallback_message)

[Admin] → GET /api/admin/metrics/validation-failures?period=7d
       → SELECT FROM tool_call_logs WHERE validation_error IS NOT NULL AND created_at > now() - 7 days
       → agrégation par tool_name + global rate
```
