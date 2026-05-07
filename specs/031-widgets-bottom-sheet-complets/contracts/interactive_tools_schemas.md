# Contract — Tools LangChain Schémas

**Date** : 2026-05-07
**Phase** : 1

Schémas Pydantic des 9 nouveaux tools LangChain, exposés dans `backend/app/graph/tools/interactive_tools.py`. Tous les schémas utilisent `model_config = ConfigDict(extra="forbid")`.

## 1. ask_yes_no

```python
class AskYesNoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    confirm_label: str = Field("Oui", max_length=50)
    deny_label: str = Field("Non", max_length=50)
    destructive: bool = False

@tool(args_schema=AskYesNoArgs)
async def ask_yes_no(
    question: str,
    confirm_label: str = "Oui",
    deny_label: str = "Non",
    destructive: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Pose une question oui/non.

    Use when:
    - confirmation simple (avant suppression, avant action sensible).
    - choix booléen explicite.
    Don't use when:
    - 3+ options possibles (utiliser ask_qcu).
    Exemple: "Êtes-vous certain de vouloir supprimer ce projet ?"
    -> ask_yes_no(question='...', destructive=True).
    """
    ...
```

**Comportement** :
- Crée une `InteractiveQuestion(question_type="yes_no", payload=YesNoPayload(...))`.
- Marque les pending questions de la conversation comme expired.
- Retourne string + marker SSE.

## 2. ask_select

```python
class SelectOptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    sublabel: str | None = Field(None, max_length=200)
    group: str | None = Field(None, max_length=100)

class AskSelectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    options: list[SelectOptionInput] = Field(..., min_length=1, max_length=200)
    min_selections: int = Field(1, ge=1, le=200)
    max_selections: int = Field(1, ge=1, le=200)
    allow_other: bool = False
```

**Comportement** : valide `min_selections <= max_selections`. Refuse si > 200 options (LLM doit filtrer en amont).

## 3. ask_number

```python
class AskNumberArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    unit: str = Field(..., max_length=20)
    min: float | None = None
    max: float | None = None
    step: float = Field(1, gt=0)
    currency: Literal["XOF", "EUR", "USD", "CDF"] | None = None
    default: float | None = None
```

**Comportement** : valide `min <= max` si les deux fournis ; valide `default in [min, max]` si fourni.

## 4. ask_date

```python
class AskDateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    min: date | None = None
    max: date | None = None
    default: date | None = None
```

## 5. ask_date_range

```python
class AskDateRangeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    min: date | None = None
    max: date | None = None
```

## 6. ask_rating

```python
class AskRatingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    scale: int = Field(5, ge=2, le=10)
    labels: list[str] | None = Field(None, max_length=10)
```

**Comportement** : valide `len(labels) == scale` si labels fourni.

## 7. ask_file_upload

```python
class AskFileUploadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    accept: list[str] = Field(
        default=[".pdf", ".docx", ".xlsx", ".png", ".jpg"],
        min_length=1,
        max_length=20,
    )
    max_size_mb: int = Field(10, ge=1, le=10)
    multi: bool = False
    doc_type_hint: str | None = Field(None, max_length=100)
```

## 8. show_form

```python
class FormFieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=200)
    type: Literal["text", "number", "select", "date", "textarea", "money"]
    required: bool = True
    placeholder: str | None = Field(None, max_length=200)
    default: str | float | bool | None = None
    validation: dict | None = None  # FormFieldValidation strictement validé en interne

class ShowFormArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=200)
    fields: list[FormFieldInput] = Field(..., min_length=1, max_length=10)
    submit_label: str = Field("Enregistrer", max_length=50)
```

## 9. show_summary_card

```python
class SummaryCardItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(..., min_length=1, max_length=200)
    value: str | float | bool | None
    editable: bool = False

class ShowSummaryCardArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=200)
    items: list[SummaryCardItemInput] = Field(..., min_length=1, max_length=20)
    confirm_label: str = Field("Valider", max_length=50)
    correct_label: str = Field("Corriger", max_length=50)
```

## Pattern uniforme d'implémentation

Chaque tool :
1. Récupère db, user_id via `get_db_and_user(config)`.
2. Extrait `conversation_id`, `module_name` depuis `RunnableConfig.configurable`.
3. Valide les args via le schéma Pydantic (déjà fait par LangChain via `args_schema`).
4. Construit le `payload` BDD : `payload = <Type>Payload(question_type="<type>", **args).model_dump()`.
5. Marque toutes les questions `pending` de la conversation comme `expired` (UPDATE).
6. Insère la nouvelle `InteractiveQuestion` avec `state="pending"`, `payload=payload`.
7. Sérialise pour SSE : `_serialize_for_sse(question)` + marker `<!--SSE:{...}-->`.
8. Journalise via `log_tool_call(...)`.
9. Retourne string `"Question posée à l'utilisateur." + marker`.

## Tools tools_offered exposés

```python
INTERACTIVE_TOOLS = [
    ask_interactive_question,  # Existant F18, conservé
    ask_yes_no,
    ask_select,
    ask_number,
    ask_date,
    ask_date_range,
    ask_rating,
    ask_file_upload,
    show_form,
    show_summary_card,
]
```
