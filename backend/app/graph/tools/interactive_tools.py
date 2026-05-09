"""Tools LangChain pour les widgets interactifs (F18 + F10).

F18 — ``ask_interactive_question`` (4 variantes QCU/QCM ± justification).
F10 — 9 nouveaux tools ``ask_yes_no``, ``ask_select``, ``ask_number``,
``ask_date``, ``ask_date_range``, ``ask_rating``, ``ask_file_upload``,
``show_form``, ``show_summary_card``.

Chaque tool :
1. Valide ses args via Pydantic (``args_schema``, ``extra='forbid'``).
2. Marque les pending de la conversation comme ``expired`` (invariant 1 question
   pending max).
3. Insère une nouvelle ``InteractiveQuestion`` avec ``state='pending'``.
4. Émet un marker SSE ``<!--SSE:{...}-->`` intercepté par ``stream_graph_events``.
5. Journalise l'appel via ``log_tool_call``.

Réf : ``specs/031-widgets-bottom-sheet-complets/contracts/interactive_tools_schemas.md``.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select, update

from app.graph.tools.common import (
    _tools_offered_from_config,
    get_db_and_user,
    log_tool_call,
)
from app.models.conversation import Conversation
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
    InteractiveQuestionType,
)
from app.schemas.interactive_question import (
    InteractiveOption,
    InteractiveQuestionCreate,
)
from app.schemas.interactive_question_payload import (
    DatePayload,
    DateRangePayload,
    FileUploadPayload,
    FormField,
    FormPayload,
    NumberPayload,
    RatingPayload,
    SelectOption,
    SelectPayload,
    SummaryCardItem,
    SummaryCardPayload,
    SupportedCurrency,
    YesNoPayload,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════
#  Helpers communs F18 + F10 : résolution account_id et assistant_message_id
# ════════════════════════════════════════════════════════════════════════


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    """Coercer une valeur quelconque en UUID (str ou UUID), None si invalide."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


async def _resolve_account_id(
    db: Any,
    config: RunnableConfig | None,
    conversation_id: uuid.UUID,
) -> uuid.UUID | None:
    """Résoudre l'account_id du tenant courant (F02) avec fallback BDD.

    Priorité :
    1. ``config['configurable']['account_id']`` (pattern F12 — propagé par
       ``stream_graph_events`` côté API).
    2. ``SELECT account_id FROM conversations WHERE id = :conversation_id``
       (filet de sécurité si le config ne le contient pas, ex. tests).

    Retourne ``None`` si aucune des deux sources ne fournit un UUID valide.
    Le caller doit alors retourner une erreur claire au LLM (pas de 500).
    """
    configurable = (config or {}).get("configurable", {}) or {}
    account_id = _coerce_uuid(configurable.get("account_id"))
    if account_id is not None:
        return account_id

    # Fallback : lire depuis la conversation (toujours liée à un account
    # via F02 mig 019, sauf en tests SQLite où account_id peut être NULL).
    try:
        result = await db.execute(
            select(Conversation.account_id).where(
                Conversation.id == conversation_id,
            ),
        )
        row = result.scalar_one_or_none()
        return _coerce_uuid(row) if row is not None else None
    except Exception:  # pragma: no cover — defense en profondeur
        logger.debug("Echec résolution account_id depuis la conversation", exc_info=True)
        return None


def _resolve_assistant_message_id(config: RunnableConfig | None) -> uuid.UUID | None:
    """Lire `assistant_message_id` du config s'il a été pré-créé en amont.

    L'API ``send_message`` rattache déjà le ``assistant_message_id`` via
    ``UPDATE`` post-INSERT (cf. ``app/api/chat.py::generate_sse``). Ce helper
    couvre le cas où le message assistant est créé en amont du tool call et
    propagé via ``config['configurable']['assistant_message_id']`` (option 1
    du fix). Si absent, l'INSERT laisse la colonne à NULL et le UPDATE
    post-stream prend le relais.
    """
    configurable = (config or {}).get("configurable", {}) or {}
    return _coerce_uuid(configurable.get("assistant_message_id"))


# ════════════════════════════════════════════════════════════════════════
#  F18 — ask_interactive_question (legacy QCU/QCM, conservé sans modif)
# ════════════════════════════════════════════════════════════════════════


class AskInteractiveQuestionArgs(BaseModel):
    """Args strict pour le tool ask_interactive_question (F18).

    `module` n'est PAS dans le schema : il est injecte depuis le RunnableConfig
    (active_module), pas par le LLM.
    """

    model_config = ConfigDict(extra="forbid")

    question_type: InteractiveQuestionType
    prompt: str = Field(..., min_length=1, max_length=500)
    options: list[InteractiveOption] = Field(..., min_length=2, max_length=8)
    min_selections: int = Field(1, ge=1, le=8)
    max_selections: int = Field(1, ge=1, le=8)
    requires_justification: bool = False
    justification_prompt: str | None = Field(None, min_length=1, max_length=200)


def _serialize_for_sse(question: InteractiveQuestion) -> dict[str, Any]:
    """Sérialiser une question pour le payload SSE interactive_question (F18 legacy)."""
    return {
        "type": "interactive_question",
        "id": str(question.id),
        "conversation_id": str(question.conversation_id),
        "question_type": question.question_type,
        "prompt": question.prompt,
        "options": question.options,
        "min_selections": question.min_selections,
        "max_selections": question.max_selections,
        "requires_justification": question.requires_justification,
        "justification_prompt": question.justification_prompt,
        "module": question.module,
        "created_at": (
            question.created_at.isoformat()
            if question.created_at
            else datetime.now(timezone.utc).isoformat()
        ),
    }


def _serialize_for_sse_with_payload(question: InteractiveQuestion) -> dict[str, Any]:
    """F10 — Sérialiser une question avec son payload pour le SSE des nouveaux widgets."""
    return {
        "type": "interactive_question",
        "id": str(question.id),
        "conversation_id": str(question.conversation_id),
        "question_type": question.question_type,
        "prompt": question.prompt,
        "module": question.module,
        "created_at": (
            question.created_at.isoformat()
            if question.created_at
            else datetime.now(timezone.utc).isoformat()
        ),
        "payload": question.payload or {},
    }


@tool(args_schema=AskInteractiveQuestionArgs)
async def ask_interactive_question(
    question_type: str,
    prompt: str,
    options: list[dict],
    min_selections: int = 1,
    max_selections: int = 1,
    requires_justification: bool = False,
    justification_prompt: str | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question interactive cliquable (QCU/QCM, +/- justification).

    Use when:
    - choix structure parmi 2-8 options (secteur, format).
    - desambiguiser via widget plutot que texte libre.
    Don't use when:
    - consultation (utiliser `get_company_profile`).
    - reponse connue (utiliser `update_company_profile`).
    Exemple: "Quel secteur ?" -> ask_interactive_question(question_type='qcu', options=[...]).
    Anti: "Mon score ESG ?" -> NE PAS appeler.
    """
    try:
        db, _user_id = get_db_and_user(config)
    except ValueError as exc:
        logger.warning("ask_interactive_question: config manquante (%s)", exc)
        return "Erreur : contexte technique indisponible, retente."

    configurable = (config or {}).get("configurable", {})
    conversation_id_raw = configurable.get("conversation_id")
    if conversation_id_raw is None:
        logger.warning("ask_interactive_question: conversation_id absent")
        return "Erreur : conversation_id manquant dans le contexte."

    conversation_id = (
        uuid.UUID(conversation_id_raw)
        if isinstance(conversation_id_raw, str)
        else conversation_id_raw
    )

    active_module_data = configurable.get("active_module_data") or {}
    module_name = (
        configurable.get("active_module")
        or active_module_data.get("module")
        or "chat"
    )

    # F18 fix — multi-tenant : résoudre account_id (config → conversation BDD).
    account_id = await _resolve_account_id(db, config, conversation_id)
    if account_id is None:
        logger.warning(
            "ask_interactive_question: account_id introuvable "
            "(config + fallback BDD) pour conversation %s",
            conversation_id,
        )
        return (
            "Erreur : account_id du tenant introuvable, "
            "impossible de persister la question."
        )

    assistant_message_id = _resolve_assistant_message_id(config)

    try:
        payload = InteractiveQuestionCreate(
            question_type=question_type,  # type: ignore[arg-type]
            prompt=prompt,
            options=options,  # type: ignore[arg-type]
            min_selections=min_selections,
            max_selections=max_selections,
            requires_justification=requires_justification,
            justification_prompt=justification_prompt,
            module=module_name,
        )
    except ValidationError as exc:
        logger.info("ask_interactive_question validation: %s", exc)
        return f"Erreur : parametres invalides ({exc.errors()[0].get('msg', exc)})."
    except ValueError as exc:
        logger.info("ask_interactive_question validation: %s", exc)
        return f"Erreur : {exc}."

    try:
        now = datetime.now(timezone.utc)
        await db.execute(
            update(InteractiveQuestion)
            .where(
                InteractiveQuestion.conversation_id == conversation_id,
                InteractiveQuestion.state == InteractiveQuestionState.PENDING.value,
            )
            .values(
                state=InteractiveQuestionState.EXPIRED.value,
                answered_at=now,
            )
        )

        question = InteractiveQuestion(
            conversation_id=conversation_id,
            account_id=account_id,
            assistant_message_id=assistant_message_id,
            module=payload.module,
            question_type=payload.question_type.value,
            prompt=payload.prompt,
            options=[opt.model_dump(exclude_none=True) for opt in payload.options],
            min_selections=payload.min_selections,
            max_selections=payload.max_selections,
            requires_justification=payload.requires_justification,
            justification_prompt=payload.justification_prompt,
            state=InteractiveQuestionState.PENDING.value,
        )
        db.add(question)
        await db.flush()
        await db.refresh(question)

        sse_payload = _serialize_for_sse(question)
        sse_marker = json.dumps({"__sse_interactive_question__": True, **sse_payload})

        try:
            await log_tool_call(
                db,
                user_id=_user_id,
                conversation_id=conversation_id,
                node_name=module_name,
                tool_name="ask_interactive_question",
                tool_args={
                    "question_type": question_type,
                    "prompt": prompt[:200],
                    "options_count": len(options),
                },
                tool_result={"question_id": str(question.id), "state": "pending"},
                status="success",
                tools_offered=_tools_offered_from_config(config),
            )
        except Exception:  # pragma: no cover
            logger.debug("Echec journalisation tool ask_interactive_question", exc_info=True)

        return (
            "Question posee a l'utilisateur."
            f"\n\n<!--SSE:{sse_marker}-->"
        )

    except Exception as exc:
        logger.exception("Erreur dans ask_interactive_question")
        return f"Erreur lors de la creation de la question interactive : {exc}"


# ════════════════════════════════════════════════════════════════════════
#  F10 — Helpers communs pour les 9 nouveaux tools widgets
# ════════════════════════════════════════════════════════════════════════


async def _extract_context(
    config: RunnableConfig | None,
) -> tuple[Any, uuid.UUID, uuid.UUID, str, uuid.UUID, uuid.UUID | None] | str:
    """Extrait db, user_id, conversation_id, module_name, account_id et
    assistant_message_id depuis le RunnableConfig.

    F18 fix — résout systématiquement ``account_id`` (config → fallback
    BDD via ``conversations.account_id``) afin de garantir un INSERT sans
    NOT NULL violation côté multi-tenant.

    Retourne un tuple à 6 éléments ou un message d'erreur string si le
    contexte est incomplet.
    """
    try:
        db, user_id = get_db_and_user(config)
    except ValueError as exc:
        logger.warning("widget tool: config manquante (%s)", exc)
        return "Erreur : contexte technique indisponible, retente."

    configurable = (config or {}).get("configurable", {})
    conversation_id_raw = configurable.get("conversation_id")
    if conversation_id_raw is None:
        return "Erreur : conversation_id manquant dans le contexte."

    conversation_id = (
        uuid.UUID(conversation_id_raw)
        if isinstance(conversation_id_raw, str)
        else conversation_id_raw
    )

    active_module_data = configurable.get("active_module_data") or {}
    module_name = (
        configurable.get("active_module")
        or active_module_data.get("module")
        or "chat"
    )

    account_id = await _resolve_account_id(db, config, conversation_id)
    if account_id is None:
        logger.warning(
            "widget tool: account_id introuvable (config + fallback BDD) "
            "pour conversation %s",
            conversation_id,
        )
        return (
            "Erreur : account_id du tenant introuvable, "
            "impossible de persister la question."
        )

    assistant_message_id = _resolve_assistant_message_id(config)

    return db, user_id, conversation_id, module_name, account_id, assistant_message_id


async def _persist_widget_question(
    *,
    db: Any,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    module_name: str,
    account_id: uuid.UUID,
    assistant_message_id: uuid.UUID | None,
    tool_name: str,
    question_type: str,
    prompt: str,
    payload: dict[str, Any],
    config: RunnableConfig | None,
    min_selections: int = 1,
    max_selections: int = 1,
    log_args: dict[str, Any] | None = None,
) -> str:
    """Pattern uniforme F10 : expire pending → insert → journalise → marker SSE."""
    try:
        now = datetime.now(timezone.utc)
        # Marquer toutes les pending comme expired (invariant 1 pending max).
        await db.execute(
            update(InteractiveQuestion)
            .where(
                InteractiveQuestion.conversation_id == conversation_id,
                InteractiveQuestion.state == InteractiveQuestionState.PENDING.value,
            )
            .values(
                state=InteractiveQuestionState.EXPIRED.value,
                answered_at=now,
            )
        )

        question = InteractiveQuestion(
            conversation_id=conversation_id,
            account_id=account_id,
            assistant_message_id=assistant_message_id,
            module=module_name,
            question_type=question_type,
            prompt=prompt,
            options=[],  # legacy F18 — vide pour les widgets F10
            min_selections=min_selections,
            max_selections=max_selections,
            requires_justification=False,
            state=InteractiveQuestionState.PENDING.value,
            payload=payload,
        )
        db.add(question)
        await db.flush()
        await db.refresh(question)

        sse_payload = _serialize_for_sse_with_payload(question)
        sse_marker = json.dumps(
            {"__sse_interactive_question__": True, **sse_payload},
            ensure_ascii=False,
            default=str,
        )

        try:
            await log_tool_call(
                db,
                user_id=user_id,
                conversation_id=conversation_id,
                node_name=module_name,
                tool_name=tool_name,
                tool_args=log_args or {"prompt": prompt[:200]},
                tool_result={"question_id": str(question.id), "state": "pending"},
                status="success",
                tools_offered=_tools_offered_from_config(config),
            )
        except Exception:  # pragma: no cover
            logger.debug("Echec journalisation tool %s", tool_name, exc_info=True)

        return (
            "Question posée à l'utilisateur."
            f"\n\n<!--SSE:{sse_marker}-->"
        )

    except Exception as exc:
        logger.exception("Erreur dans %s", tool_name)
        return f"Erreur lors de la création de la question interactive : {exc}"


# ════════════════════════════════════════════════════════════════════════
#  1. ask_yes_no — Confirmation binaire (peut être destructive)
# ════════════════════════════════════════════════════════════════════════


class AskYesNoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    confirm_label: str = Field("Oui", min_length=1, max_length=50)
    deny_label: str = Field("Non", min_length=1, max_length=50)
    destructive: bool = False


@tool(args_schema=AskYesNoArgs)
async def ask_yes_no(
    question: str,
    confirm_label: str = "Oui",
    deny_label: str = "Non",
    destructive: bool = False,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question oui/non (avec mode destructif optionnel).

    Use when:
    - confirmation simple avant action irréversible (suppression, révocation).
    - choix booléen explicite par l'utilisateur (« On active la fonctionnalité ? »).
    Don't use when:
    - 3+ options possibles (utiliser `ask_interactive_question` ou `ask_select`).
    - simple consultation (utiliser `get_company_profile`).
    Exemple: ask_yes_no(question='Êtes-vous certain ?', destructive=True,
    confirm_label='Oui, supprimer', deny_label='Non, annuler').
    Anti: « Quel secteur ? » -> NE PAS appeler (utiliser ask_select).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        validated = YesNoPayload(
            question_type="yes_no",
            confirm_label=confirm_label,
            deny_label=deny_label,
            destructive=destructive,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_yes_no",
        question_type="yes_no",
        prompt=question,
        payload=validated.model_dump(),
        config=config,
        log_args={
            "question": question[:200],
            "destructive": destructive,
        },
    )


# ════════════════════════════════════════════════════════════════════════
#  2. ask_select — Sélection dans une liste (1-200 options)
# ════════════════════════════════════════════════════════════════════════


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

    @field_validator("max_selections")
    @classmethod
    def _check_max_ge_min(cls, v: int, info) -> int:
        min_s = info.data.get("min_selections", 1)
        if v < min_s:
            raise ValueError("max_selections doit être >= min_selections")
        return v


@tool(args_schema=AskSelectArgs)
async def ask_select(
    question: str,
    options: list[dict],
    min_selections: int = 1,
    max_selections: int = 1,
    allow_other: bool = False,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question avec sélection dans une liste de 1 à 200 options.

    Use when:
    - liste longue (8+ options) : pays, secteurs, fonds, devises.
    - sélection mono ou multi (max_selections > 1).
    - groupement par catégorie (option.group="UEMOA").
    Don't use when:
    - 2 options binaires (utiliser `ask_yes_no`).
    - 3-7 options simples (utiliser `ask_interactive_question` pour QCU/QCM).
    Exemple: ask_select(question="Quel pays UEMOA ?", options=[{id:"ci", label:"Côte d'Ivoire", group:"UEMOA"}, ...]).
    Anti: « Confirmer ? » -> NE PAS appeler (utiliser ask_yes_no).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        opts_validated = [
            SelectOption(**(o if isinstance(o, dict) else o.model_dump()))
            for o in options
        ]
        validated = SelectPayload(
            question_type="select",
            options=opts_validated,
            min_selections=min_selections,
            max_selections=max_selections,
            allow_other=allow_other,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_select",
        question_type="select",
        prompt=question,
        payload=validated.model_dump(exclude_none=True),
        config=config,
        min_selections=min_selections,
        max_selections=max_selections,
        log_args={
            "question": question[:200],
            "options_count": len(options),
            "allow_other": allow_other,
        },
    )


# ════════════════════════════════════════════════════════════════════════
#  3. ask_number — Saisie numérique formatée avec devise optionnelle
# ════════════════════════════════════════════════════════════════════════


class AskNumberArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    unit: str = Field(..., min_length=1, max_length=20)
    min: float | None = None
    max: float | None = None
    step: float = Field(1, gt=0)
    currency: SupportedCurrency | None = None
    default: float | None = None

    @field_validator("max")
    @classmethod
    def _check_max_gte_min(cls, v: float | None, info) -> float | None:
        if v is None:
            return v
        min_v = info.data.get("min")
        if min_v is not None and v < min_v:
            raise ValueError("max doit être >= min")
        return v

    @field_validator("default")
    @classmethod
    def _check_default_in_range(cls, v: float | None, info) -> float | None:
        if v is None:
            return v
        min_v = info.data.get("min")
        max_v = info.data.get("max")
        if min_v is not None and v < min_v:
            raise ValueError("default doit être >= min")
        if max_v is not None and v > max_v:
            raise ValueError("default doit être <= max")
        return v


@tool(args_schema=AskNumberArgs)
async def ask_number(
    question: str,
    unit: str,
    min: float | None = None,
    max: float | None = None,
    step: float = 1,
    currency: str | None = None,
    default: float | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question avec saisie numérique formatée (séparateurs milliers + devise).

    Use when:
    - montant monétaire (CA, capital, projet) : currency='XOF'/'EUR'/'USD'/'CDF'.
    - quantité avec unité (effectif, tCO2e, jours).
    - bornes connues : min/max, step pour incréments.
    Don't use when:
    - saisie texte libre (utiliser le mode chat).
    - choix entre 2-200 options listées (utiliser `ask_select`).
    Exemple: ask_number(question="CA annuel ?", unit="FCFA", min=0, max=1_000_000_000, currency="XOF").
    Anti: « Quel pays ? » -> NE PAS appeler (utiliser ask_select).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        validated = NumberPayload(
            question_type="number",
            unit=unit,
            min=min,
            max=max,
            step=step,
            currency=currency,  # type: ignore[arg-type]
            default=default,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_number",
        question_type="number",
        prompt=question,
        payload=validated.model_dump(exclude_none=True),
        config=config,
        log_args={
            "question": question[:200],
            "unit": unit,
            "currency": currency,
        },
    )


# ════════════════════════════════════════════════════════════════════════
#  4. ask_date — Saisie date unique (ISO 8601, format français)
# ════════════════════════════════════════════════════════════════════════


class AskDateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    min: date | None = None
    max: date | None = None
    default: date | None = None


@tool(args_schema=AskDateArgs)
async def ask_date(
    question: str,
    min: date | None = None,
    max: date | None = None,
    default: date | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question avec saisie date unique (date picker natif HTML5).

    Use when:
    - date d'échéance d'attestation, de soumission, de démarrage.
    - bornes min=today (futur), max=today (passé).
    Don't use when:
    - intervalle de dates (utiliser `ask_date_range`).
    - texte libre incertain (utiliser le mode chat).
    Exemple: ask_date(question="Validité jusqu'à ?", min=date.today()).
    Anti: « Pendant combien de jours ? » -> NE PAS appeler (utiliser ask_number).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        validated = DatePayload(
            question_type="date",
            min=min,
            max=max,
            default=default,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_date",
        question_type="date",
        prompt=question,
        payload=validated.model_dump(exclude_none=True, mode="json"),
        config=config,
        log_args={"question": question[:200]},
    )


# ════════════════════════════════════════════════════════════════════════
#  5. ask_date_range — Saisie intervalle de dates
# ════════════════════════════════════════════════════════════════════════


class AskDateRangeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    min: date | None = None
    max: date | None = None


@tool(args_schema=AskDateRangeArgs)
async def ask_date_range(
    question: str,
    min: date | None = None,
    max: date | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question avec saisie intervalle de dates (from/to).

    Use when:
    - période d'évaluation (début/fin de l'exercice fiscal).
    - durée projet de N à M (date_début, date_fin).
    Don't use when:
    - date unique (utiliser `ask_date`).
    - durée numérique en jours/mois (utiliser `ask_number`).
    Exemple: ask_date_range(question="Quelle période fiscale ?", min="2024-01-01").
    Anti: « Date d'échéance ? » -> NE PAS appeler (utiliser ask_date).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        validated = DateRangePayload(
            question_type="date_range", min=min, max=max,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_date_range",
        question_type="date_range",
        prompt=question,
        payload=validated.model_dump(exclude_none=True, mode="json"),
        config=config,
        log_args={"question": question[:200]},
    )


# ════════════════════════════════════════════════════════════════════════
#  6. ask_rating — Notation/évaluation (étoiles ou points 1-5/1-10)
# ════════════════════════════════════════════════════════════════════════


class AskRatingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=500)
    scale: int = Field(5, ge=2, le=10)
    labels: list[str] | None = Field(None, max_length=10)

    @field_validator("labels")
    @classmethod
    def _check_labels_match_scale(cls, v: list[str] | None, info) -> list[str] | None:
        if v is None:
            return v
        scale = info.data.get("scale", 5)
        if len(v) != scale:
            raise ValueError(f"len(labels)={len(v)} doit être égal à scale={scale}")
        return v


@tool(args_schema=AskRatingArgs)
async def ask_rating(
    question: str,
    scale: int = 5,
    labels: list[str] | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question d'auto-évaluation (étoiles 1-5 ou points 1-10).

    Use when:
    - auto-évaluation pratique (ESG, tri sélectif, gouvernance).
    - labels textuels par cran ("Très mauvais → Excellent").
    Don't use when:
    - oui/non binaire (utiliser `ask_yes_no`).
    - valeur numérique précise hors échelle (utiliser `ask_number`).
    Exemple: ask_rating(question="Évaluez votre tri sélectif", scale=5,
    labels=["Très mauvais", "Mauvais", "Moyen", "Très bien", "Excellent"]).
    Anti: « Quel score ESG ? » -> NE PAS appeler (utiliser get_esg_assessment).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        validated = RatingPayload(
            question_type="rating", scale=scale, labels=labels,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_rating",
        question_type="rating",
        prompt=question,
        payload=validated.model_dump(exclude_none=True),
        config=config,
        log_args={"question": question[:200], "scale": scale},
    )


# ════════════════════════════════════════════════════════════════════════
#  7. ask_file_upload — Drag-and-drop avec validation MIME backend
# ════════════════════════════════════════════════════════════════════════


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


@tool(args_schema=AskFileUploadArgs)
async def ask_file_upload(
    question: str,
    accept: list[str] | None = None,
    max_size_mb: int = 10,
    multi: bool = False,
    doc_type_hint: str | None = None,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Pose une question demandant l'upload d'un ou plusieurs fichiers.

    Use when:
    - demande de business plan, statuts, attestation, justificatifs.
    - widget contextualisé dans le bottom sheet (vs trombone séparé).
    Don't use when:
    - simple question texte libre (utiliser le mode chat).
    - liste de fichiers déjà uploadés (utiliser `list_user_documents`).
    Exemple: ask_file_upload(question="Envoyez-moi votre business plan",
    accept=[".pdf"], max_size_mb=10, doc_type_hint="business_plan").
    Anti: « Voir mes documents ? » -> NE PAS appeler (utiliser list_user_documents).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        validated = FileUploadPayload(
            question_type="file_upload",
            accept=accept or [".pdf", ".docx", ".xlsx", ".png", ".jpg"],
            max_size_mb=max_size_mb,
            multi=multi,
            doc_type_hint=doc_type_hint,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="ask_file_upload",
        question_type="file_upload",
        prompt=question,
        payload=validated.model_dump(exclude_none=True),
        config=config,
        log_args={
            "question": question[:200],
            "accept_count": len(validated.accept),
            "multi": multi,
        },
    )


# ════════════════════════════════════════════════════════════════════════
#  8. show_form — Mini-formulaire 1-10 champs validable en un clic
# ════════════════════════════════════════════════════════════════════════


class FormFieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=200)
    type: Literal["text", "number", "select", "date", "textarea", "money"]
    required: bool = True
    placeholder: str | None = Field(None, max_length=200)
    default: str | float | bool | None = None
    validation: dict[str, Any] | None = None


class ShowFormArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=200)
    fields: list[FormFieldInput] = Field(..., min_length=1, max_length=10)
    submit_label: str = Field("Enregistrer", min_length=1, max_length=50)


@tool(args_schema=ShowFormArgs)
async def show_form(
    title: str,
    fields: list[dict],
    submit_label: str = "Enregistrer",
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Affiche un mini-formulaire 1-10 champs validable en un clic.

    Use when:
    - création d'entité (projet, candidature, bilan) avec 3+ champs.
    - éviter les 8 questions séquentielles consécutives.
    Don't use when:
    - 1-2 champs (utiliser `ask_number` / `ask_select`).
    - 11+ champs (refus backend, à découper en 2 formulaires).
    Exemple: show_form(title="Nouveau projet", fields=[{name:"project_name", label:"Nom", type:"text"}, ...]).
    Anti: « Quel est ton secteur ? » -> NE PAS appeler (utiliser ask_select).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        # Tolérer dict ou pydantic model (LangChain convertit args_schema en model)
        fields_dicts = [
            f if isinstance(f, dict) else f.model_dump(exclude_none=True)
            for f in fields
        ]
        fields_validated = [
            FormField(
                name=f["name"],
                label=f["label"],
                type=f["type"],
                required=f.get("required", True),
                placeholder=f.get("placeholder"),
                default=f.get("default"),
                validation=f.get("validation"),
            )
            for f in fields_dicts
        ]
        validated = FormPayload(
            question_type="form",
            title=title,
            fields=fields_validated,
            submit_label=submit_label,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="show_form",
        question_type="form",
        prompt=title,
        payload=validated.model_dump(exclude_none=True, mode="json"),
        config=config,
        max_selections=len(fields_validated),  # autorise > 8 via la contrainte étendue
        log_args={
            "title": title[:200],
            "fields_count": len(fields_validated),
        },
    )


# ════════════════════════════════════════════════════════════════════════
#  9. show_summary_card — Récap d'extraction avec édition inline
# ════════════════════════════════════════════════════════════════════════


class SummaryCardItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(..., min_length=1, max_length=200)
    value: str | float | bool | None
    editable: bool = False


class ShowSummaryCardArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=200)
    items: list[SummaryCardItemInput] = Field(..., min_length=1, max_length=20)
    confirm_label: str = Field("Valider", min_length=1, max_length=50)
    correct_label: str = Field("Corriger", min_length=1, max_length=50)


@tool(args_schema=ShowSummaryCardArgs)
async def show_summary_card(
    title: str,
    items: list[dict],
    confirm_label: str = "Valider",
    correct_label: str = "Corriger",
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Affiche une carte récapitulative (extraction document) avec édition inline.

    Use when:
    - après extraction OCR/LLM d'un document : valider ou corriger les champs.
    - jusqu'à 20 items, un mix éditable/lecture-seule.
    Don't use when:
    - simple confirmation oui/non (utiliser `ask_yes_no`).
    - création d'entité from scratch (utiliser `show_form`).
    Exemple: show_summary_card(title="Voici l'extraction", items=[{label:"Capital", value:"5M FCFA", editable:true}, ...]).
    Anti: « Confirmes-tu ? » -> NE PAS appeler (utiliser ask_yes_no).
    """
    ctx = await _extract_context(config)
    if isinstance(ctx, str):
        return ctx
    db, user_id, conversation_id, module_name, account_id, assistant_message_id = ctx

    try:
        items_dicts = [
            i if isinstance(i, dict) else i.model_dump(exclude_none=True)
            for i in items
        ]
        items_validated = [
            SummaryCardItem(
                label=i["label"],
                value=i.get("value"),
                editable=i.get("editable", False),
            )
            for i in items_dicts
        ]
        validated = SummaryCardPayload(
            question_type="summary_card",
            title=title,
            items=items_validated,
            confirm_label=confirm_label,
            correct_label=correct_label,
        )
    except ValidationError as exc:
        return f"Erreur : paramètres invalides ({exc.errors()[0].get('msg', exc)})."

    return await _persist_widget_question(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        module_name=module_name,
        account_id=account_id,
        assistant_message_id=assistant_message_id,
        tool_name="show_summary_card",
        question_type="summary_card",
        prompt=title,
        payload=validated.model_dump(exclude_none=True),
        config=config,
        log_args={
            "title": title[:200],
            "items_count": len(items_validated),
        },
    )


# ════════════════════════════════════════════════════════════════════════
#  Liste des tools exposés (legacy F18 + 9 nouveaux F10)
# ════════════════════════════════════════════════════════════════════════


INTERACTIVE_TOOLS = [
    ask_interactive_question,  # F18 legacy QCU/QCM
    # F10 — 9 nouveaux widgets bottom sheet
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
