"""Tool LangChain ask_interactive_question (feature 018).

Permet au LLM de poser une question interactive sous forme de widget cliquable
(QCU, QCM, avec ou sans justification). La question est persistee en BDD et un
marker SSE est embarque dans le retour du tool, intercepte par stream_graph_events.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import update

from app.graph.tools.common import _tools_offered_from_config, get_db_and_user, log_tool_call
from app.models.interactive_question import (
    InteractiveQuestion,
    InteractiveQuestionState,
    InteractiveQuestionType,
)
from app.schemas.interactive_question import (
    InteractiveOption,
    InteractiveQuestionCreate,
)

logger = logging.getLogger(__name__)


class AskInteractiveQuestionArgs(BaseModel):
    """Args strict pour le tool ask_interactive_question.

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


def _serialize_for_sse(question: InteractiveQuestion) -> dict:
    """Serializer une question pour le payload SSE interactive_question."""
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


INTERACTIVE_TOOLS = [ask_interactive_question]
