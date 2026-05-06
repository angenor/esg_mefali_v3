# Contract — Validator middleware `source_required.py`

**Feature** : F01
**Fichier** : `backend/app/graph/validators/source_required.py`
**Point d'injection** : hook dans `stream_graph_events` (`backend/app/api/chat.py`) après collecte de la réponse finale et des `tool_calls` du tour, avant émission de l'event SSE final.

## Objectif

Garantir qu'aucune affirmation factuelle (chiffre, score, pourcentage, montant, équivalent CO2e) n'est transmise à l'utilisateur sans soit :
1. une invocation `cite_source(source_id)` correspondante (sur une source `verified`), soit
2. une invocation `flag_unsourced(claim, reason)` correspondante.

Si une affirmation détectée n'est couverte par ni l'un ni l'autre, le validator rejette la réponse, demande à l'agent une seule correction, et substitue par un libellé de repli si la correction échoue.

## Signature

```python
@dataclass(frozen=True)
class NumericClaim:
    """Une grappe « chiffre + unité » détectée dans le texte de l'agent."""
    text: str           # ex: "0,41 kgCO2e/kWh"
    span_start: int     # index dans le texte
    span_end: int
    paragraph_index: int  # numéro du paragraphe contenant la grappe


@dataclass(frozen=True)
class ValidationResult:
    """Résultat d'une validation source-required."""
    passed: bool
    detected_claims: list[NumericClaim]
    cite_source_calls: list[UUID]            # source_ids cités dans le tour
    flag_unsourced_calls: list[str]          # claims flaggés explicitement
    missing_citations: list[NumericClaim]    # grappes non couvertes
    substituted_text: str | None             # texte de fallback si rejet


async def validate_response(
    final_text: str,
    tool_calls: list[ToolCallRecord],
    db: AsyncSession,
    *,
    retry_count: int = 0,
) -> ValidationResult:
    """Valide la réponse de l'agent contre les invariants de sourçage F01."""
    ...
```

Où `ToolCallRecord` est un namedtuple `(name: str, arguments: dict, result: dict)` extrait de l'historique LangGraph du tour.

## Algorithme

### Étape 1 — Strip des motifs ignorés

```python
IGNORED_NUMERIC_PATTERNS = [
    re.compile(r"\bISO\s?(?:9001|14001|14064|14067|26000|27001|50001)\b"),
    re.compile(r"\barticle\s+\d+\.\d+\b"),
    re.compile(r"\b802\.1[A-Z]?\b"),
    re.compile(r"\bPCI[-\s]?DSS\s?\d+\.\d+\b"),
    re.compile(r"\bIFRS\s?\d+\b"),
    re.compile(r"\bGRI\s?\d+\b"),
    # extensible itérativement
]

def _strip_ignored(text: str) -> str:
    for pattern in IGNORED_NUMERIC_PATTERNS:
        text = pattern.sub("", text)
    return text
```

### Étape 2 — Détection des chiffres factuels

```python
NUMERIC_CLAIM_RE = re.compile(
    r"\b(\d{1,3}(?:[\s ]?\d{3})*(?:[.,]\d+)?)\s*"
    r"(%|tCO2e|kgCO2e|FCFA|XOF|EUR|USD|/100|/10|kWh|km|tonne|MW)\b",
    re.IGNORECASE,
)

def _detect_claims(stripped_text: str) -> list[NumericClaim]:
    claims: list[NumericClaim] = []
    paragraph_starts = _compute_paragraph_starts(stripped_text)
    for match in NUMERIC_CLAIM_RE.finditer(stripped_text):
        start, end = match.span()
        para_idx = _resolve_paragraph(start, paragraph_starts)
        claims.append(NumericClaim(
            text=match.group(0),
            span_start=start,
            span_end=end,
            paragraph_index=para_idx,
        ))
    return claims
```

### Étape 3 — Extraction des invocations `cite_source` et `flag_unsourced`

```python
def _extract_cite_source_calls(tool_calls: list[ToolCallRecord]) -> list[UUID]:
    return [
        UUID(call.arguments["source_id"])
        for call in tool_calls
        if call.name == "cite_source"
        and call.result.get("error") is None  # uniquement les citations réussies
    ]

def _extract_flag_unsourced_calls(tool_calls: list[ToolCallRecord]) -> list[str]:
    return [call.arguments["claim"] for call in tool_calls if call.name == "flag_unsourced"]
```

### Étape 4 — Couverture par grappes (FR-014)

Une grappe est couverte si :
- au moins 1 `cite_source` réussi a été invoqué dans le même tour (heuristique simple : on suppose que chaque cite_source couvre les chiffres du paragraphe le plus proche), OU
- au moins 1 `flag_unsourced` dont le `claim` couvre textuellement la grappe (substring match).

**Heuristique de proximité** :
- On groupe les grappes consécutives au sein d'un même paragraphe et séparées de moins de 200 caractères → une seule citation suffit.
- Si plusieurs paragraphes contiennent des chiffres, on requiert ≥ 1 cite_source par paragraphe (ou flag_unsourced explicite).

```python
def _check_coverage(
    claims: list[NumericClaim],
    cite_source_count: int,
    flag_unsourced_claims: list[str],
) -> list[NumericClaim]:
    """Retourne les grappes non couvertes."""
    grouped_by_paragraph: dict[int, list[NumericClaim]] = defaultdict(list)
    for claim in claims:
        grouped_by_paragraph[claim.paragraph_index].append(claim)

    missing: list[NumericClaim] = []
    available_citations = cite_source_count
    for para_idx, para_claims in grouped_by_paragraph.items():
        para_text_excerpt = " ".join(c.text for c in para_claims)
        # Couverture par flag_unsourced ?
        if any(c.text in flag_text or flag_text in para_text_excerpt
               for c in para_claims for flag_text in flag_unsourced_claims):
            continue
        # Sinon, exige 1 cite_source par paragraphe
        if available_citations >= 1:
            available_citations -= 1
            continue
        missing.extend(para_claims)
    return missing
```

> Note : l'heuristique ci-dessus est volontairement permissive (1 cite_source = 1 paragraphe couvert). Le golden set de 50 réponses (cf. spec.md FR-018) servira à vérifier le taux d'erreur ≤ 5 %. Si nécessaire, l'algorithme sera affiné en Phase B.

### Étape 5 — Décision

```python
async def validate_response(...) -> ValidationResult:
    stripped = _strip_ignored(final_text)
    claims = _detect_claims(stripped)
    cite_ids = _extract_cite_source_calls(tool_calls)
    flag_claims = _extract_flag_unsourced_calls(tool_calls)
    missing = _check_coverage(claims, len(cite_ids), flag_claims)

    if not missing:
        return ValidationResult(passed=True, detected_claims=claims,
                                cite_source_calls=cite_ids,
                                flag_unsourced_calls=flag_claims,
                                missing_citations=[],
                                substituted_text=None)

    # Échec — sollicite une correction (gérée par le caller, max 1 retry)
    if retry_count == 0:
        # signale au caller de demander une correction au LLM
        return ValidationResult(passed=False, detected_claims=claims,
                                cite_source_calls=cite_ids,
                                flag_unsourced_calls=flag_claims,
                                missing_citations=missing,
                                substituted_text=None)

    # Retry échoué — substitue par fallback
    fallback = _substitute_with_fallback(final_text, missing)
    return ValidationResult(passed=False, ..., substituted_text=fallback)
```

### Étape 6 — Substitution par fallback

```python
def _substitute_with_fallback(text: str, missing: list[NumericClaim]) -> str:
    """Remplace chaque grappe non sourcée par un libellé neutre."""
    FALLBACK = "[je ne dispose pas d'une source vérifiée pour ce chiffre]"
    # Substitution descendante (ordre des spans inversé pour ne pas déranger les indices)
    for claim in sorted(missing, key=lambda c: c.span_start, reverse=True):
        text = text[:claim.span_start] + FALLBACK + text[claim.span_end:]
    return text
```

## Intégration dans `stream_graph_events`

Pseudocode de l'intégration côté API SSE :

```python
async def stream_graph_events(...) -> AsyncIterator[ServerSentEvent]:
    # ... streaming token-by-token comme avant ...
    final_text = ""  # accumulé au fil des chunks
    tool_calls: list[ToolCallRecord] = []  # accumulés sur tool_end events

    async for event in graph.astream_events(...):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            final_text += chunk.content
            yield ServerSentEvent(event="text_delta", data=chunk.content)
        elif event["event"] == "on_tool_end":
            tool_calls.append(_extract_tool_call(event))
            yield ServerSentEvent(event="tool_end", data=...)
        # ... autres events ...

    # Validation post-tour
    result = await source_required.validate_response(
        final_text=final_text,
        tool_calls=tool_calls,
        db=db,
        retry_count=0,
    )

    if not result.passed and result.missing_citations:
        # Demande une correction au LLM (1 retry)
        correction_prompt = _build_correction_prompt(result.missing_citations)
        async for event in graph.astream_events({"correction": correction_prompt}, ...):
            # ... ré-accumulation du texte et tool_calls ...
        result_retry = await source_required.validate_response(
            final_text=corrected_text,
            tool_calls=corrected_tool_calls,
            db=db,
            retry_count=1,
        )
        if not result_retry.passed:
            # Substitution finale
            yield ServerSentEvent(event="text_replace",
                                  data=result_retry.substituted_text or final_text)
            await _log_incident(db, conversation_id, result_retry)

    yield ServerSentEvent(event="done", data={})
```

## Performance

- **Cible** : ≤ 50 ms par tour (regex + lookups in-memory).
- Aucune requête BDD dans le validator (`tool_calls` viennent du contexte LangGraph en mémoire).
- Le retry max 1 ajoute un tour LLM complet (acceptable car uniquement quand le validator détecte un manque).

## Tests unitaires (`test_source_required_validator.py`)

1. `test_validate_response_passes_when_no_numeric_claim` — texte sans chiffre → passed=True.
2. `test_validate_response_passes_with_cite_source_for_each_paragraph` — happy path.
3. `test_validate_response_fails_when_number_without_citation` — passed=False, missing populated.
4. `test_validate_response_passes_with_flag_unsourced_covering_claim` — flag explicite.
5. `test_validate_response_ignores_iso_standards` — « ISO 14001 » non détecté comme chiffre.
6. `test_validate_response_handles_grouped_claims_in_same_paragraph` — 1 cite_source pour N grappes proches.
7. `test_validate_response_requires_separate_citations_for_different_paragraphs` — 2 paragraphes = 2 cite_source minimum.
8. `test_validate_response_substitutes_fallback_on_retry_failure` — `retry_count=1, missing=[...]` → `substituted_text` produit.
9. `test_validate_response_rejects_cite_source_with_error` — citation sur source `pending` ignorée.
10. `test_validate_response_handles_french_decimal_separator` — « 0,41 » correctement détecté.

## Tests d'intégration

`backend/tests/integration/test_source_required_in_chat.py` :

1. `test_chat_response_with_emission_factor_triggers_cite_source` — bout-en-bout simulé.
2. `test_chat_response_without_citation_returns_fallback_after_retry` — bout-en-bout simulé.
3. `test_chat_logs_incident_on_validator_substitution` — vérifier journal.

## Critères de succès du validator (SC-004 / FR-018)

- Sur un golden set de 50 réponses LLM annotées (`backend/tests/llm_eval/golden_set_50.json`), le taux d'erreur (faux positifs + faux négatifs) ≤ 5 %.
- Aucune réponse rejetée à tort sur les motifs `IGNORED_NUMERIC_PATTERNS`.
- Toute grappe « X% », « X tCO2e », « X FCFA », « X kgCO2e/kWh » qui n'a pas de citation correspondante est correctement rejetée.
