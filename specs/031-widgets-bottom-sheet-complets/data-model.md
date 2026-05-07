# Data Model — F10 Widgets Interactifs Bottom Sheet Complets

**Date** : 2026-05-07
**Phase** : 1 (Design & Contracts)

## Vue d'ensemble

F10 étend la table satellite `interactive_questions` (introduite F18) sans créer de nouvelle table. Trois changements de schéma :

1. Enum `interactivequestiontype` étendu avec 9 nouvelles valeurs.
2. Colonne `payload jsonb NOT NULL DEFAULT '{}'` ajoutée pour les paramètres spécifiques par variante.
3. Colonne `response_payload jsonb NULL` ajoutée pour les réponses structurées.
4. Contrainte `ck_iq_max_le_8` relâchée pour autoriser `max_selections > 8` quand `question_type IN ('select', 'form')`.

## Entité : InteractiveQuestion (étendue)

### Table `interactive_questions`

| Colonne | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| id | uuid | NO | gen_random_uuid() | PK (UUIDMixin) |
| conversation_id | uuid | NO | — | FK conversations(id) ON DELETE CASCADE, INDEXED |
| account_id | uuid | YES | NULL | FK accounts(id) ON DELETE RESTRICT, INDEXED (F02) |
| assistant_message_id | uuid | YES | NULL | FK messages(id) ON DELETE SET NULL |
| response_message_id | uuid | YES | NULL | FK messages(id) ON DELETE SET NULL |
| module | varchar(32) | NO | — | Nom du noeud LangGraph |
| question_type | varchar(24) | NO | — | Enum élargi (cf. ci-dessous) |
| prompt | text | NO | — | Question affichée |
| options | jsonb | NO | — | Liste options (legacy F18, vide pour widgets non-QCU/QCM) |
| min_selections | smallint | NO | 1 | Legacy F18 |
| max_selections | smallint | NO | 1 | Legacy F18 |
| requires_justification | bool | NO | false | Legacy F18 |
| justification_prompt | text | YES | NULL | Legacy F18 |
| state | varchar(16) | NO | 'pending' | pending\|answered\|abandoned\|expired |
| response_values | jsonb | YES | NULL | Legacy F18 |
| response_justification | varchar(400) | YES | NULL | Legacy F18 |
| **payload** | **jsonb** | **NO** | **'{}'** | **NEW F10 — paramètres variante-specific** |
| **response_payload** | **jsonb** | **YES** | **NULL** | **NEW F10 — réponse structurée variante-specific** |
| created_at | timestamptz | NO | now() | — |
| answered_at | timestamptz | YES | NULL | — |

### Index (inchangés)

- `ix_interactive_questions_conversation_pending` ON (conversation_id, state)
- `ix_interactive_questions_assistant_message` ON (assistant_message_id)
- `ix_interactive_questions_module_state` ON (module, state)

### Contraintes

| Contrainte | Avant F10 | Après F10 |
|---|---|---|
| `ck_iq_min_selections` | `min_selections >= 1` | inchangé |
| `ck_iq_max_ge_min` | `max_selections >= min_selections` | inchangé |
| `ck_iq_max_le_8` | `max_selections <= 8` | **REMPLACÉE par** `ck_iq_max_le_8_or_select_form` : `max_selections <= 8 OR question_type IN ('select', 'form')` |

## Enum `interactivequestiontype`

### Valeurs existantes (F18, conservées)

- `qcu`
- `qcm`
- `qcu_justification`
- `qcm_justification`

### Nouvelles valeurs (F10)

- `yes_no`
- `select`
- `number`
- `date`
- `date_range`
- `rating`
- `file_upload`
- `form`
- `summary_card`

## Lifecycle (inchangé F18)

```
[Tool LLM appelé] → state=pending
   ↓
[User répond via widget] → state=answered, answered_at, response_payload
   ↓ ou
[User clique "Répondre librement"] → state=abandoned
   ↓ ou
[Nouvelle question pending posée] → state=expired
```

Invariant : 1 question `pending` max par conversation (déjà actif F18).

## Schémas Pydantic — Payload BDD (variante-specific)

Chaque widget a un schéma Pydantic strict avec `model_config = ConfigDict(extra="forbid")`.

### YesNoPayload

```python
class YesNoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["yes_no"]
    confirm_label: str = Field("Oui", max_length=50)
    deny_label: str = Field("Non", max_length=50)
    destructive: bool = False
```

### SelectPayload

```python
class SelectOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    sublabel: str | None = Field(None, max_length=200)
    group: str | None = Field(None, max_length=100)

class SelectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["select"]
    options: list[SelectOption] = Field(..., min_length=1, max_length=200)
    min_selections: int = Field(1, ge=1, le=200)
    max_selections: int = Field(1, ge=1, le=200)
    allow_other: bool = False
```

### NumberPayload

```python
class NumberPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["number"]
    unit: str = Field(..., max_length=20)  # ex: "FCFA", "tCO2e", "employés"
    min: float | None = None
    max: float | None = None
    step: float = Field(1, gt=0)
    currency: Literal["XOF", "EUR", "USD", "CDF"] | None = None
    default: float | None = None
```

### DatePayload

```python
class DatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["date"]
    min: date | None = None  # ISO 8601
    max: date | None = None
    default: date | None = None
```

### DateRangePayload

```python
class DateRangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["date_range"]
    min: date | None = None
    max: date | None = None
```

### RatingPayload

```python
class RatingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["rating"]
    scale: int = Field(5, ge=2, le=10)
    labels: list[str] | None = Field(None, max_length=10)  # une étiquette par cran si fourni
```

### FileUploadPayload

```python
class FileUploadPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["file_upload"]
    accept: list[str] = Field(
        default=[".pdf", ".docx", ".xlsx", ".png", ".jpg"],
        min_length=1,
        max_length=20,
    )
    max_size_mb: int = Field(10, ge=1, le=10)  # Hard limit 10
    multi: bool = False
    doc_type_hint: str | None = Field(None, max_length=100)
```

### FormPayload

```python
class FormFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    DATE = "date"
    TEXTAREA = "textarea"
    MONEY = "money"

class FormFieldValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_length: int | None = None
    max_length: int | None = None
    min: float | None = None
    max: float | None = None
    pattern: str | None = None  # regex pour text/textarea
    options: list[SelectOption] | None = None  # pour select

class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=200)
    type: FormFieldType
    required: bool = True
    placeholder: str | None = Field(None, max_length=200)
    default: str | float | bool | None = None
    validation: FormFieldValidation | None = None

class FormPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["form"]
    title: str = Field(..., min_length=1, max_length=200)
    fields: list[FormField] = Field(..., min_length=1, max_length=10)  # Hard limit 10
    submit_label: str = Field("Enregistrer", max_length=50)
```

### SummaryCardPayload

```python
class SummaryCardItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(..., min_length=1, max_length=200)
    value: str | float | bool | None
    editable: bool = False

class SummaryCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["summary_card"]
    title: str = Field(..., min_length=1, max_length=200)
    items: list[SummaryCardItem] = Field(..., min_length=1, max_length=20)
    confirm_label: str = Field("Valider", max_length=50)
    correct_label: str = Field("Corriger", max_length=50)
```

### Union discriminée

```python
InteractiveQuestionPayload = Annotated[
    YesNoPayload
    | SelectPayload
    | NumberPayload
    | DatePayload
    | DateRangePayload
    | RatingPayload
    | FileUploadPayload
    | FormPayload
    | SummaryCardPayload,
    Field(discriminator="question_type"),
]
```

## Schémas Pydantic — Response payload (réponse structurée)

### YesNoResponse

```python
class YesNoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["yes_no"]
    value: bool
    label: str  # "Oui" ou "Non"
```

### SelectResponse

```python
class SelectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["select"]
    selected: list[SelectOption]  # 1 ou plusieurs selon max_selections
    other_value: str | None = None  # si allow_other et user a tapé "Autre"
```

### NumberResponse

```python
class NumberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["number"]
    value: float
    currency: Literal["XOF", "EUR", "USD", "CDF"] | None = None
    formatted: str  # ex: "1 200 000 FCFA"
```

### DateResponse / DateRangeResponse

```python
class DateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["date"]
    value: date  # ISO 8601
    label: str  # "15 mars 2026"

class DateRangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["date_range"]
    from_date: date  # serialise sous "from" via alias
    to_date: date    # serialise sous "to"
    label: str  # "Du 1 janvier au 31 décembre 2026"
```

### RatingResponse

```python
class RatingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["rating"]
    value: int  # 1..scale
    scale: int
    label: str | None = None  # ex: "Très bien" si labels fourni
```

### FileUploadResponse

```python
class FileUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["file_upload"]
    documents: list[UploadedDocument]  # 1 si !multi, plusieurs sinon

class UploadedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID
    filename: str
    size: int  # bytes
    mime_type: str
```

### FormResponse

```python
class FormResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["form"]
    values: dict[str, str | float | bool | None]  # name → value
    summary_label: str  # ex: "Projet créé : Panneaux solaires, 5M FCFA, énergie"
```

### SummaryCardResponse

```python
class SummaryCardModification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    before: str | float | bool | None
    after: str | float | bool | None

class SummaryCardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["summary_card"]
    validated: bool
    modifications: list[SummaryCardModification]  # vide si validated sans corrections
```

### Union discriminée response

```python
InteractiveQuestionResponse = Annotated[
    YesNoResponse
    | SelectResponse
    | NumberResponse
    | DateResponse
    | DateRangeResponse
    | RatingResponse
    | FileUploadResponse
    | FormResponse
    | SummaryCardResponse,
    Field(discriminator="question_type"),
]
```

## Relations & integrity

- `account_id` hérité de `conversations.account_id` au moment de l'insertion (cohérent F02).
- `audit_log` (F03) tracé pour chaque mutation destructive : action=delete_*, metadata.confirm=True/False, metadata.required_confirmation=True.
- `documents` (F04) lié via `FileUploadResponse.documents[].document_id` ; F10 ne crée pas de nouvelle table documents, réutilise l'API `POST /api/documents/upload` existante.

## Migration Alembic 031 — résumé

```python
"""extend_interactive_questions for F10 widgets

Revision ID: 031_extend_interactive_questions
Revises: 030_create_referential_scores
Create Date: 2026-05-07
"""

revision = "031_extend_interactive_questions"
down_revision = "030_create_referential_scores"

def upgrade():
    # 1. Étendre l'enum (autocommit obligatoire pour ADD VALUE)
    with op.get_context().autocommit_block():
        for value in ["yes_no", "select", "number", "date", "date_range",
                      "rating", "file_upload", "form", "summary_card"]:
            op.execute(
                f"ALTER TYPE interactivequestiontype ADD VALUE IF NOT EXISTS '{value}'"
            )

    # 2. Ajouter colonnes payload + response_payload
    op.add_column(
        "interactive_questions",
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "interactive_questions",
        sa.Column("response_payload", postgresql.JSONB(), nullable=True),
    )

    # 3. Relâcher la contrainte max_selections <= 8
    op.drop_constraint("ck_iq_max_le_8", "interactive_questions", type_="check")
    op.create_check_constraint(
        "ck_iq_max_le_8_or_select_form",
        "interactive_questions",
        "max_selections <= 8 OR question_type IN ('select', 'form')",
    )

def downgrade():
    # 1. Vérifier qu'aucune ligne n'utilise les nouvelles valeurs d'enum
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM interactive_questions WHERE question_type IN "
            "('yes_no','select','number','date','date_range','rating','file_upload','form','summary_card')"
        )
    )
    count = result.scalar()
    if count > 0:
        raise RuntimeError(
            f"Downgrade impossible : {count} lignes utilisent les nouvelles valeurs d'enum. "
            "Migrez ces lignes manuellement (UPDATE state='expired' ou DELETE) avant downgrade."
        )

    # 2. Restaurer la contrainte initiale
    op.drop_constraint(
        "ck_iq_max_le_8_or_select_form", "interactive_questions", type_="check"
    )
    op.create_check_constraint(
        "ck_iq_max_le_8", "interactive_questions", "max_selections <= 8"
    )

    # 3. Retirer les colonnes (jsonb data perdue, log warning)
    op.drop_column("interactive_questions", "response_payload")
    op.drop_column("interactive_questions", "payload")

    # Note : les valeurs d'enum ne peuvent pas être retirées en PostgreSQL.
    # Une migration de remplacement de type complet est possible mais hors-scope F10.
```

## Test de migration

`backend/tests/integration/test_alembic_031_up_down_up.py` — vérifie up/down/up idempotent ET le refus du downgrade en présence de lignes utilisant les nouvelles valeurs.
