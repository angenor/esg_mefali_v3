# Tools LangChain — F13 Scoring Multi-Référentiels

**Date** : 2026-05-07
**Module** : `backend/app/graph/tools/esg_tools.py`
**Instrumentation** : `tool_call_logs` (F12)

## Convention

Tous les tools sont des fonctions Python décorées avec `@tool` (LangChain) et exposent :
- Un nom snake_case ;
- Une signature typée Pydantic v2 ;
- Une description en français destinée au LLM (qui doit savoir quand l'appeler) ;
- Un retour structuré Pydantic (jamais de dict non-typé) ;
- Une instrumentation automatique via le decorator `@instrumented_tool` (F12) qui persiste dans `tool_call_logs`.

## Tool 1 — `finalize_esg_assessment` (REFACTORÉ)

### Signature

```python
@tool(args_schema=FinalizeEsgAssessmentArgs)
@instrumented_tool
async def finalize_esg_assessment(
    assessment_id: UUID,
    referentials_to_compute: list[str] | None = None,
) -> FinalizeAssessmentResult:
    """Finalise une évaluation ESG en calculant les scores des référentiels demandés.

    Appelle ce tool quand la PME indique qu'elle a fini de renseigner ses indicateurs
    et qu'elle veut voir ses scores. Si referentials_to_compute n'est pas fourni,
    calcule tous les référentiels actifs (Mefali + GCF + IFC PS + BOAD ESS + GRI 2021).
    """
```

### Args Schema

```python
class FinalizeEsgAssessmentArgs(BaseModel):
    """Arguments du tool finalize_esg_assessment."""
    assessment_id: UUID = Field(description="UUID de l'évaluation ESG à finaliser.")
    referentials_to_compute: list[str] | None = Field(
        default=None,
        description=(
            "Codes des référentiels à calculer (ex : ['mefali', 'ifc_ps']). "
            "Si None, calcule tous les référentiels actifs."
        ),
    )
```

### Retour

```python
class FinalizeAssessmentResult(BaseModel):
    assessment_id: UUID
    finalized_at: datetime
    referential_scores: list[ReferentialScoreRead]
    failures: list[dict]  # référentiels qui ont échoué (atomicité par référentiel)
```

### Comportement

1. Vérifie que `assessment_id` existe et appartient à l'account courant (RLS).
2. Si `referentials_to_compute=None`, charge tous les `referentials.is_active=true`.
3. Sinon, valide chaque code et lève une erreur typée si un code est inconnu.
4. Appelle `compute_all_referential_scores(assessment_id, only_referentials_using_indicators=None)` avec atomicité par référentiel (asyncio.gather + return_exceptions).
5. Met à jour `esg_assessments.status='finalized'` et `esg_assessments.finalized_at=now()`.
6. Met à jour les colonnes legacy avec le score Mefali (cohérence F11/F06 2 sprints).
7. Retourne la liste des scores calculés + éventuelles failures.

### Erreurs

- `INVALID_REFERENTIAL_CODE` : code invalide dans `referentials_to_compute`.
- `ASSESSMENT_NOT_FOUND` : RLS rejette ou ID inexistant.
- `ASSESSMENT_ALREADY_FINALIZED` : si `status='finalized'` (le LLM doit demander confirmation pour refaire un calcul).

---

## Tool 2 — `recompute_score` (NOUVEAU)

### Signature

```python
@tool(args_schema=RecomputeScoreArgs)
@instrumented_tool
async def recompute_score(
    entity_id: UUID,
    referentiel_id: UUID,
) -> RecomputeRequestResponse:
    """Déclenche un recalcul ciblé d'un seul référentiel pour une évaluation.

    Appelle ce tool quand la PME demande explicitement « Recalcule mon score IFC »
    ou quand un nouvel indicateur a été renseigné et qu'elle veut voir l'impact
    sur un référentiel précis. Le calcul est asynchrone : retourne un
    recompute_request_id pour suivre l'avancement.
    """
```

### Args Schema

```python
class RecomputeScoreArgs(BaseModel):
    entity_id: UUID = Field(
        description=(
            "UUID de l'entité à recalculer. En MVP, accepte uniquement un assessment_id. "
            "Post-MVP : extensible à d'autres entités (Module 1.1.3)."
        ),
    )
    referentiel_id: UUID = Field(description="UUID du référentiel à recalculer.")
```

### Retour

```python
class RecomputeRequestResponse(BaseModel):
    status: str = "accepted"
    recompute_request_id: UUID
    referentials_to_recompute: list[str]
    estimated_duration_seconds: int = 5
```

### Comportement

1. Vérifie que `entity_id` correspond à un `assessment_id` existant et accessible (RLS).
2. Vérifie que `referentiel_id` correspond à un `referentials.is_active=true`.
3. Génère un `recompute_request_id` UUID.
4. Enqueue un `BackgroundTask` qui appelle `compute_all_referential_scores(entity_id, only_referentials_using_indicators=...)` filtré sur le référentiel ciblé.
5. Retourne immédiatement `RecomputeRequestResponse` avec le `recompute_request_id` et le code du référentiel.

### Erreurs

- `ENTITY_NOT_FOUND` : `entity_id` inexistant ou inaccessible.
- `REFERENTIAL_NOT_FOUND` : `referentiel_id` inactif ou inexistant.
- `RECOMPUTE_ENQUEUE_FAILED` : erreur lors de l'enqueue (rare, retry automatique 1x).

---

## Tool 3 — `compare_referentials` (NOUVEAU)

### Signature

```python
@tool(args_schema=CompareReferentialsArgs)
@instrumented_tool
async def compare_referentials(
    assessment_id: UUID,
    referentials: list[str],
) -> ComparisonResult:
    """Compare les scores entre N référentiels pour une évaluation donnée.

    Appelle ce tool quand la PME demande « Compare mes scores selon Mefali et IFC »
    ou « Quelle est la différence entre mon score GCF et mon score BOAD ? ».
    Retourne les scores, les écarts (gaps), et les critères divergents (couverts par
    un ref mais pas l'autre).
    """
```

### Args Schema

```python
class CompareReferentialsArgs(BaseModel):
    assessment_id: UUID = Field(description="UUID de l'évaluation ESG.")
    referentials: list[str] = Field(
        description=(
            "Codes des référentiels à comparer (minimum 2, maximum 5). "
            "Ex : ['mefali', 'ifc_ps']."
        ),
        min_items=2,
        max_items=5,
    )
```

### Retour

```python
class ComparisonResult(BaseModel):
    scores: list[ReferentialScoreRead]
    gaps: dict[str, Decimal]  # ex: {"mefali_vs_ifc_ps": 26.0}
    divergent_criteria: dict[str, list[CoveredCriterion]]
    summary_text: str  # phrase pédagogique en français pour le LLM
```

### Comportement

1. Vérifie que `assessment_id` existe et appartient à l'account courant (RLS).
2. Pour chaque code dans `referentials`, charge le `ReferentialScore` courant (`superseded_by IS NULL`).
3. Si un référentiel n'a pas encore été calculé, déclenche un calcul synchrone (latence acceptée car l'utilisateur attend la réponse comparative).
4. Calcule les `gaps` deux à deux (`scores[A].overall_score - scores[B].overall_score`).
5. Calcule les `divergent_criteria` : pour chaque ref, liste les critères couverts par lui mais pas par les autres.
6. Génère un `summary_text` formaté pour le LLM, ex : « Votre score Mefali est de 78/100, votre score IFC PS est de 52/100. L'écart de 26 points est dû à 3 critères IFC non couverts par Mefali : PS6 Biodiversité, PS7 Peuples autochtones, PS8 Patrimoine culturel. ».
7. Retourne `ComparisonResult`.

### Erreurs

- `INVALID_REFERENTIAL_CODE` : code invalide.
- `INSUFFICIENT_REFERENTIALS` : moins de 2 référentiels (caught par Pydantic min_items).
- `ASSESSMENT_NOT_FOUND` : RLS rejette ou ID inexistant.

---

## Instrumentation `tool_call_logs` (F12)

Tous les 3 tools sont décorés avec `@instrumented_tool` (helper F12) qui persiste automatiquement :

```sql
INSERT INTO tool_call_logs (
    id, tool_name, account_id, assessment_id_context,
    arguments_json, response_json, success, error_message,
    duration_ms, called_at
) VALUES (...);
```

- `tool_name` ∈ {`finalize_esg_assessment`, `recompute_score`, `compare_referentials`}.
- `success` : TRUE si retour Pydantic conforme, FALSE si exception levée.
- `error_message` : type d'erreur structurée (cf. liste ci-dessus).

---

## Invariants

1. **Aucun tool ne mute le catalogue** (invariant n°7) : les 3 tools mutent uniquement `referential_scores` (artefact calculé).
2. **RLS multi-tenant strict** : chaque tool vérifie `account_id` via la session DB.
3. **Pas de PII exposée** au LLM : seuls les `score`, `coverage_rate`, et codes/noms de référentiels sont passés au LLM (jamais le détail des indicateurs PME).
4. **Erreurs structurées** : les tools retournent des erreurs typées Pydantic plutôt que des exceptions Python brutes (le LLM peut les interpréter pour formuler un message à l'utilisateur).
5. **Atomicité par référentiel** dans `finalize_esg_assessment` : un échec sur 1 référentiel ne fait pas perdre les calculs des autres (return_exceptions=True dans asyncio.gather).
