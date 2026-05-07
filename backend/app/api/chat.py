"""Router chat : CRUD conversations, envoi de messages avec streaming SSE."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import async_session_factory, get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
    PaginatedResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────


async def get_user_conversation(
    conversation_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Conversation:
    """Récupérer une conversation appartenant à l'utilisateur, ou lever 404."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation introuvable",
        )
    return conversation


async def invoke_graph(content: str, conversation_id: str) -> str:
    """Invoquer le graphe LangGraph et retourner la réponse complète.

    Cette fonction est mockée dans les tests.
    """
    from app.main import compiled_graph

    if compiled_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service IA indisponible",
        )

    config = {"configurable": {"thread_id": conversation_id}}
    result = await compiled_graph.ainvoke(
        {"messages": [HumanMessage(content=content)]},
        config=config,
    )
    return result["messages"][-1].content


async def _error_sse(message: str) -> AsyncGenerator[str, None]:
    """Générer un événement SSE d'erreur."""
    yield f"data: {json.dumps({'type': 'error', 'content': message})}\n\n"


# Story 6.4 review (D1+P8) : plafond partage front/back pour stabiliser le
# comportement adaptatif (au-dela, le plancher 3s est deja atteint — compter
# plus loin n'ajoute rien et gonfle la payload / l'attaque DoS).
MAX_STATS_CAP = 5
# Review 6.4 P11 : cap longueur brute du Form field avant json.loads (CPU).
MAX_GUIDANCE_STATS_RAW_LEN = 500


def _parse_guidance_stats(raw: str | None) -> dict | None:
    """Parser le Form field guidance_stats (JSON) avec fallback None.

    Accepte uniquement un objet {refusal_count:int>=0, acceptance_count:int>=0}.
    Les valeurs sont clampees a MAX_STATS_CAP (defense en profondeur).
    Toute autre structure → None (pas de crash HTTP 500).
    """
    if not raw:
        return None
    if len(raw) > MAX_GUIDANCE_STATS_RAW_LEN:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    refusal = parsed.get("refusal_count")
    acceptance = parsed.get("acceptance_count")
    if not isinstance(refusal, int) or isinstance(refusal, bool) or refusal < 0:
        return None
    if not isinstance(acceptance, int) or isinstance(acceptance, bool) or acceptance < 0:
        return None
    return {
        "refusal_count": min(refusal, MAX_STATS_CAP),
        "acceptance_count": min(acceptance, MAX_STATS_CAP),
    }


# Story 10.2 : taille max du Form field active_entities (defense en profondeur).
MAX_ACTIVE_ENTITIES_RAW_LEN = 2000


def _parse_active_entities(raw: str | None) -> dict | None:
    """Parser le Form field active_entities (JSON) avec fallback None.

    Story 10.2 — cabled-only backend. Accepte un objet plat ; toute autre
    structure ou JSON invalide -> None (pas de 5xx).
    """
    if not raw:
        return None
    raw = raw.strip()[:MAX_ACTIVE_ENTITIES_RAW_LEN]
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def stream_graph_events(
    content: str,
    conversation_id: str,
    user_id: uuid.UUID,
    db: AsyncSession,
    user_profile: dict | None = None,
    context_memory: list[str] | None = None,
    document_analysis_summary: str | None = None,
    document_upload: dict | None = None,
    widget_response: dict | None = None,
    current_page: str | None = None,
    guidance_stats: dict | None = None,
    active_entities: dict | None = None,
    account_id: uuid.UUID | None = None,
    user_projects: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """Streamer les événements du graphe LangGraph via astream_events().

    Utilise le graphe compilé avec tool calling pour un flux complet :
    tokens, tool_call_start, tool_call_end, tool_call_error.

    Yields:
        dict avec type: token | tool_call_start | tool_call_end | tool_call_error
    """
    from app.main import compiled_graph

    if compiled_graph is None:
        yield {"type": "error", "content": "Service IA indisponible"}
        return

    # Construire l'état initial pour le graphe
    initial_state = {
        "messages": [HumanMessage(content=content)],
        "user_id": str(user_id),
        "user_profile": user_profile,
        "context_memory": context_memory or [],
        "profile_updates": None,
        "profiling_instructions": None,
        "document_upload": document_upload,
        "document_analysis_summary": document_analysis_summary,
        "has_document": document_upload is not None,
        "esg_assessment": None,
        "_route_esg": False,
        "carbon_data": None,
        "_route_carbon": False,
        "financing_data": None,
        "_route_financing": False,
        "application_data": None,
        "_route_application": False,
        "credit_data": None,
        "_route_credit": False,
        "action_plan_data": None,
        "_route_action_plan": False,
        "tool_call_count": 0,
        "current_page": current_page,
        "guidance_stats": guidance_stats,
        "active_entities": active_entities,
        # F06 — Projets actifs (statut ≠ cancelled/closed) injectés dans le state
        "user_projects": user_projects or [],
    }

    config = {
        "configurable": {
            "thread_id": conversation_id,
            "user_id": user_id,
            "db": db,
            "conversation_id": uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
            "widget_response": widget_response,
            # F12 — exposé au tool recall_history (filtre RLS multi-tenant)
            "account_id": account_id,
        },
    }

    # Emettre interactive_question_resolved au debut du tour si la reponse
    # provient d'un widget interactif (feature 018)
    if widget_response:
        from datetime import datetime, timezone
        yield {
            "type": "interactive_question_resolved",
            "id": widget_response.get("question_id"),
            "state": "answered",
            "response_values": widget_response.get("values"),
            "response_justification": widget_response.get("justification"),
            "answered_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        async for event in compiled_graph.astream_events(
            initial_state,
            config=config,
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                # Ignorer les tokens du routeur (classification interne)
                node_name = event.get("metadata", {}).get("langgraph_node", "")
                if node_name == "router":
                    continue
                # Token de texte streamé
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {"type": "token", "content": chunk.content}

            elif kind == "on_tool_start":
                # Début d'exécution d'un tool
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                run_id = event.get("run_id", "")
                yield {
                    "type": "tool_call_start",
                    "tool_name": tool_name,
                    "tool_args": tool_input if isinstance(tool_input, dict) else {},
                    "tool_call_id": run_id,
                }

            elif kind == "on_tool_end":
                # Fin d'exécution d'un tool
                tool_name = event.get("name", "unknown")
                output = event.get("data", {}).get("output", "")
                run_id = event.get("run_id", "")

                # Extraire le contenu reel du ToolMessage (sinon str() produit
                # une repr qui escape les quotes et casse le parse JSON du marker)
                if hasattr(output, "content"):
                    output_str = str(output.content) if output.content else ""
                else:
                    output_str = str(output) if output else ""

                result_summary = output_str[:200]
                yield {
                    "type": "tool_call_end",
                    "tool_name": tool_name,
                    "tool_call_id": run_id,
                    "success": True,
                    "result_summary": result_summary,
                }

                # Émettre les événements SSE profile_update/completion ou
                # interactive_question si le tool a retourné des métadonnées
                sse_marker = "<!--SSE:"
                if sse_marker in output_str:
                    try:
                        start = output_str.index(sse_marker) + len(sse_marker)
                        end = output_str.index("-->", start)
                        sse_data = json.loads(output_str[start:end])
                        if sse_data.get("__sse_profile__"):
                            for field_update in sse_data.get("changed_fields", []):
                                yield {"type": "profile_update", **field_update}
                            completion = sse_data.get("completion")
                            if completion:
                                yield {"type": "profile_completion", **completion}
                        elif sse_data.get("__sse_interactive_question__"):
                            # Émettre l'event interactive_question (feature 018)
                            event_payload = {
                                k: v for k, v in sse_data.items()
                                if k != "__sse_interactive_question__"
                            }
                            yield event_payload
                        elif sse_data.get("__sse_guided_tour__"):
                            # Émettre l'event guided_tour (feature 019)
                            event_payload = {
                                k: v for k, v in sse_data.items()
                                if k != "__sse_guided_tour__"
                            }
                            yield event_payload
                        elif sse_data.get("__sse_visualization_block__"):
                            # F11 — Émettre l'event visualization_block typé
                            event_payload = {
                                k: v for k, v in sse_data.items()
                                if k != "__sse_visualization_block__"
                            }
                            yield event_payload
                    except (ValueError, json.JSONDecodeError):
                        logger.debug("Impossible de parser les métadonnées SSE du tool")

            elif kind == "on_tool_error":
                # Erreur d'un tool
                tool_name = event.get("name", "unknown")
                error_data = event.get("data", {})
                run_id = event.get("run_id", "")
                yield {
                    "type": "tool_call_error",
                    "tool_name": tool_name,
                    "tool_call_id": run_id,
                    "error_message": str(error_data.get("error", "Erreur inconnue"))[:200],
                }

    except Exception as e:
        logger.exception("Erreur stream_graph_events")
        yield {"type": "error", "content": str(e)}


async def stream_llm_tokens(
    content: str,
    conversation_id: str,
    user_profile: dict | None = None,
    context_memory: list[str] | None = None,
    document_analysis_summary: str | None = None,
) -> AsyncGenerator[str, None]:
    """Streamer les tokens du LLM un par un (fallback sans tool calling).

    Utilise le LLM directement avec streaming pour un rendu progressif.
    Le prompt système est enrichi avec le profil, la mémoire contextuelle
    et le contexte document si disponible.
    """
    from app.graph.nodes import get_llm
    from app.prompts.system import build_system_prompt
    from langchain_core.messages import SystemMessage

    llm = get_llm()
    system_prompt = build_system_prompt(
        user_profile, context_memory,
        document_analysis_summary=document_analysis_summary,
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=content)]

    async for chunk in llm.astream(messages):
        if chunk.content:
            yield chunk.content


async def _load_profile_for_state(
    db: AsyncSession, user_id: uuid.UUID
) -> dict | None:
    """Charger le profil utilisateur pour le state du graphe.

    Utilise `get_or_create_profile` pour garantir qu'un profil existe et
    qu'il contient au minimum le `company_name` fourni à l'inscription
    (backfill depuis `User.company_name` si nécessaire).
    """
    from app.modules.company.service import get_or_create_profile

    profile = await get_or_create_profile(db, user_id)
    if profile is None:
        return None

    profile_dict: dict = {}
    for field in [
        "company_name", "sector", "sub_sector", "employee_count",
        "annual_revenue_xof", "city", "country", "year_founded",
        "has_waste_management", "has_energy_policy", "has_gender_policy",
        "has_training_program", "has_financial_transparency",
        "governance_structure", "environmental_practices",
        "social_practices", "notes",
    ]:
        value = getattr(profile, field)
        if value is not None:
            profile_dict[field] = value.value if hasattr(value, "value") else value

    return profile_dict if profile_dict else None


async def _load_full_context_for_state(
    db: AsyncSession, user_id: uuid.UUID,
) -> dict[str, list | dict | None]:
    """F06 — Charger profil + projets actifs pour le state LangGraph.

    Retourne un dict ``{"profile": ..., "projects": [...]}``.
    Les projets actifs sont ceux dont le statut n'est pas ``cancelled``/``closed``
    (statut in {draft, seeking_funding, funded, in_execution}). Le LLM peut
    ainsi être conscient des projets existants à chaque tour de conversation.
    """
    from app.models.user import User as _User
    from app.modules.projects.service import get_active_projects_for_user

    profile = await _load_profile_for_state(db, user_id)

    # Résoudre l'account_id du user pour charger ses projets.
    user_result = await db.execute(
        select(_User).where(_User.id == user_id)
    )
    user_obj = user_result.scalar_one_or_none()
    projects: list = []
    if user_obj is not None and user_obj.account_id is not None:
        try:
            projects = await get_active_projects_for_user(
                db, account_id=user_obj.account_id, limit=20,
            )
        except Exception:
            logger.exception("Erreur chargement projets actifs")
            projects = []

    return {"profile": profile, "projects": projects}


def format_relative_time(
    dt: "datetime", now: "datetime | None" = None
) -> str:
    """Formater un horodatage en français court (clarification Q4).

    - âge < 1 minute → « à l'instant »
    - âge < 60 minutes → « il y a N minutes »
    - âge < 24 heures → « il y a N heures »
    - âge < 48 heures → « hier »
    - âge ≤ 30 jours → « il y a N jours »
    - âge > 30 jours → « le DD/MM/YYYY »
    """
    from datetime import datetime, timezone

    if now is None:
        now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        minutes = seconds // 60
        suffix = "s" if minutes > 1 else ""
        return f"il y a {minutes} minute{suffix}"
    if seconds < 86400:
        hours = seconds // 3600
        suffix = "s" if hours > 1 else ""
        return f"il y a {hours} heure{suffix}"
    if seconds < 172800:
        return "hier"

    days = delta.days
    if days <= 30:
        return f"il y a {days} jours"
    return f"le {dt.strftime('%d/%m/%Y')}"


async def _load_context_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> list[str]:
    """Charger le contexte mémoire pour le LLM (F12).

    Compose :
    1. Les 3 derniers résumés de conversation (existant).
    2. Les 15 derniers messages bruts de la conversation courante (F12),
       formatés ``[<relative_time>, <role>] <content>``.

    Args:
        db: Session SQLAlchemy async.
        user_id: UUID de l'utilisateur courant.
        conversation_id: UUID de la conversation courante (optionnel).
            Si fourni, charge les 15 derniers messages de cette conversation.

    Returns:
        Liste de chaînes : résumés en tête, messages bruts en queue.
    """
    # 1. Résumés (mécanisme existant)
    result = await db.execute(
        select(Conversation.summary)
        .where(
            Conversation.user_id == user_id,
            Conversation.summary.isnot(None),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(3)
    )
    summaries = [row[0] for row in result.all() if row[0]]

    # 2. Derniers messages bruts (F12)
    raw_messages: list[str] = []
    if conversation_id is not None:
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(15)
        )
        rows = list(msg_result.scalars().all())
        # Inverser pour avoir l'ordre chronologique (du plus ancien au plus récent)
        rows.reverse()
        for msg in rows:
            role_label = "utilisateur" if msg.role == "user" else "assistant"
            try:
                rel_time = format_relative_time(msg.created_at)
            except Exception:
                rel_time = ""
            content = msg.content or ""
            # Borne défensive : ne pas dépasser 1500 chars par message en contexte
            if len(content) > 1500:
                content = content[:1497] + "..."
            line = f"[{rel_time}, {role_label}] {content}" if rel_time else f"[{role_label}] {content}"
            raw_messages.append(line)

    return [*summaries, *raw_messages]


async def _summarize_previous_conversation(
    db: AsyncSession, user_id: uuid.UUID
) -> None:
    """Générer le résumé de la dernière conversation si elle n'en a pas."""
    from app.chains.summarization import generate_summary

    # Récupérer la dernière conversation sans résumé
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.summary.is_(None),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    prev_conv = result.scalar_one_or_none()

    if prev_conv is None:
        return

    # Charger les messages de cette conversation
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == prev_conv.id)
        .order_by(Message.created_at.asc())
    )
    conv_messages = msg_result.scalars().all()

    if not conv_messages:
        return

    # Formater les messages pour le LLM
    messages_text = "\n".join(
        f"{'Utilisateur' if m.role == 'user' else 'Assistant'}: {m.content}"
        for m in conv_messages
    )

    summary = await generate_summary(messages_text)
    if summary:
        prev_conv.summary = summary
        await db.flush()


# ─── Interactive questions (feature 018) ────────────────────────────


async def _expire_pending_questions(
    db: AsyncSession, conversation_id: uuid.UUID
) -> None:
    """Marquer toutes les questions pending d'une conversation comme expired.

    Conformement a la clarification Q4 : un nouveau message assistant ou un
    message utilisateur libre marque toute question pending comme expired.
    """
    from datetime import datetime, timezone

    from app.models.interactive_question import (
        InteractiveQuestion,
        InteractiveQuestionState,
    )

    await db.execute(
        update(InteractiveQuestion)
        .where(
            InteractiveQuestion.conversation_id == conversation_id,
            InteractiveQuestion.state == InteractiveQuestionState.PENDING.value,
        )
        .values(
            state=InteractiveQuestionState.EXPIRED.value,
            answered_at=datetime.now(timezone.utc),
        )
    )


async def _resolve_interactive_question(
    db: AsyncSession,
    *,
    question_uuid: uuid.UUID,
    conversation: Conversation,
    values_json: str | None,
    justification: str | None,
):
    """Resoudre une question interactive (passage en answered).

    Retourne (question, contenu_synthetise) ou leve HTTPException.
    """
    from datetime import datetime, timezone

    from app.models.interactive_question import (
        InteractiveQuestion,
        InteractiveQuestionState,
    )

    result = await db.execute(
        select(InteractiveQuestion).where(InteractiveQuestion.id == question_uuid)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="QUESTION_NOT_FOUND")

    if question.conversation_id != conversation.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    if question.state != InteractiveQuestionState.PENDING.value:
        raise HTTPException(status_code=409, detail="QUESTION_NOT_PENDING")

    # Parse values
    try:
        values = json.loads(values_json) if values_json else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="INVALID_VALUES") from exc

    if not isinstance(values, list) or not values:
        raise HTTPException(status_code=422, detail="VALUES_REQUIRED")

    if len(values) < question.min_selections or len(values) > question.max_selections:
        raise HTTPException(status_code=400, detail="INVALID_VALUES")

    valid_ids = {opt.get("id") for opt in (question.options or [])}
    if not all(v in valid_ids for v in values):
        raise HTTPException(status_code=400, detail="INVALID_VALUES")

    # Justification (defense en profondeur : tronquer a 400)
    just = justification
    if question.requires_justification:
        if not just or not just.strip():
            raise HTTPException(status_code=400, detail="JUSTIFICATION_REQUIRED")
    if just and len(just) > 400:
        raise HTTPException(status_code=400, detail="JUSTIFICATION_TOO_LONG")

    # Synthese textuelle
    label_by_id = {opt.get("id"): opt.get("label", "") for opt in (question.options or [])}
    chosen_labels = [label_by_id.get(v, v) for v in values]
    synthesized = ", ".join(chosen_labels)
    if just:
        synthesized = f"{synthesized}\n_{just}_"

    question.state = InteractiveQuestionState.ANSWERED.value
    question.response_values = list(values)
    question.response_justification = just
    question.answered_at = datetime.now(timezone.utc)

    await db.flush()
    return question, synthesized


# ─── CRUD Conversations ──────────────────────────────────────────────


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    data: ConversationCreate = ConversationCreate(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Créer une nouvelle conversation.

    Génère le résumé du thread précédent (s'il n'en a pas déjà un).
    """
    # Générer le résumé du thread précédent si nécessaire
    await _summarize_previous_conversation(db, current_user.id)

    conversation = Conversation(
        user_id=current_user.id,
        title=data.title,
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return conversation


@router.get(
    "/conversations",
    response_model=PaginatedResponse[ConversationResponse],
)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lister les conversations de l'utilisateur connecté."""
    count_result = await db.execute(
        select(func.count()).select_from(Conversation).where(
            Conversation.user_id == current_user.id
        )
    )
    total = count_result.scalar_one()

    offset = (page - 1) * limit
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Modifier le titre d'une conversation."""
    conversation = await get_user_conversation(conversation_id, current_user, db)
    conversation.title = data.title
    await db.flush()
    await db.refresh(conversation)
    return conversation


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Supprimer une conversation et ses messages."""
    conversation = await get_user_conversation(conversation_id, current_user, db)
    await db.delete(conversation)


# ─── Messages ────────────────────────────────────────────────────────


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageResponse],
)
async def get_messages(
    conversation_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Récupérer les messages d'une conversation."""
    await get_user_conversation(conversation_id, current_user, db)

    count_result = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        )
    )
    total = count_result.scalar_one()

    offset = (page - 1) * limit
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post(
    "/conversations/{conversation_id}/messages",
)
async def send_message(
    conversation_id: uuid.UUID,
    content: str = Form(None),
    file: UploadFile | None = File(None),
    interactive_question_id: str | None = Form(None),
    interactive_question_values: str | None = Form(None),
    interactive_question_justification: str | None = Form(None),
    current_page: str | None = Form(None),
    guidance_stats: str | None = Form(None),
    active_entities: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Envoyer un message et recevoir la réponse en streaming SSE.

    Accepte un message texte (content) et/ou un fichier (file) en multipart.
    Si un fichier est joint, il est uploadé et analysé avant la réponse IA.
    Si `interactive_question_id` est fourni, la reponse provient d'un widget
    interactif (feature 018).
    """
    # Sanitisation de current_page : longueur max et caracteres autorises
    if current_page is not None:
        current_page = current_page.strip()[:200] or None

    # Parsing du Form field guidance_stats (FR17 — modulation adaptative)
    parsed_guidance_stats = _parse_guidance_stats(guidance_stats)

    # Parsing du Form field active_entities (story 10.2 — cabled-only backend)
    parsed_active_entities = _parse_active_entities(active_entities)

    conversation = await get_user_conversation(conversation_id, current_user, db)

    # Gérer le contenu : multipart (Form) ou JSON fallback
    message_content = content or ""

    # Resolution d'une question interactive (feature 018) — avant validation contenu
    widget_response_payload: dict | None = None
    if interactive_question_id:
        try:
            iq_uuid = uuid.UUID(interactive_question_id)
        except ValueError:
            return StreamingResponse(
                _error_sse("interactive_question_id invalide"),
                media_type="text/event-stream",
            )

        try:
            iq, synthesized = await _resolve_interactive_question(
                db,
                question_uuid=iq_uuid,
                conversation=conversation,
                values_json=interactive_question_values,
                justification=interactive_question_justification,
            )
        except HTTPException as exc:
            return StreamingResponse(
                _error_sse(str(exc.detail)),
                media_type="text/event-stream",
                status_code=exc.status_code,
            )

        # Le contenu utilisateur est synthetise a partir des choix
        if not message_content:
            message_content = synthesized

        widget_response_payload = {
            "question_id": str(iq.id),
            "values": iq.response_values,
            "justification": iq.response_justification,
            "module": iq.module,
        }

    # Si pas de contenu et pas de fichier, tenter de lire le body JSON
    if not message_content and file is None:
        return StreamingResponse(
            _error_sse("Veuillez fournir un message ou un fichier"),
            media_type="text/event-stream",
        )

    # Si un fichier est joint, l'uploader
    uploaded_doc = None
    if file is not None:
        from app.modules.documents.service import upload_document

        file_content = await file.read()
        try:
            uploaded_doc = await upload_document(
                db=db,
                user_id=current_user.id,
                filename=file.filename or "document",
                content=file_content,
                content_type=file.content_type or "application/octet-stream",
                file_size=len(file_content),
                conversation_id=conversation.id,
            )
        except ValueError as e:
            return StreamingResponse(
                _error_sse(str(e)),
                media_type="text/event-stream",
            )

    # Si pas de contenu texte mais un fichier, générer un message par défaut
    if not message_content and uploaded_doc:
        message_content = f"Analyse ce document : {uploaded_doc.original_filename}"

    # Sauvegarder le message utilisateur
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=message_content,
    )
    db.add(user_message)
    await db.flush()

    # Lier le message utilisateur a la question interactive (feature 018)
    if widget_response_payload and interactive_question_id:
        try:
            from app.models.interactive_question import InteractiveQuestion
            await db.execute(
                update(InteractiveQuestion)
                .where(
                    InteractiveQuestion.id == uuid.UUID(interactive_question_id),
                )
                .values(response_message_id=user_message.id)
            )
        except Exception:  # pragma: no cover
            logger.debug("Lien response_message_id echoue", exc_info=True)
    elif not widget_response_payload:
        # Clarification Q4 : un message texte standard EXPIRE toute question pending
        await _expire_pending_questions(db, conversation.id)

    # Capturer les IDs avant de quitter le scope de la session FastAPI
    conv_id = conversation.id
    conv_title = conversation.title
    user_content = message_content
    user_id = current_user.id

    # Préparer les infos document pour le state
    doc_upload_info = None
    if uploaded_doc:
        doc_upload_info = {
            "document_id": str(uploaded_doc.id),
            "filename": uploaded_doc.original_filename,
            "user_id": str(user_id),
        }

    # F06 — Charger le profil + projets actifs et la mémoire contextuelle pour le prompt
    full_context = await _load_full_context_for_state(db, user_id)
    user_profile = full_context.get("profile")
    user_projects_state = full_context.get("projects") or []
    context_memory = await _load_context_memory(db, user_id, conversation_id=conv_id)

    async def generate_sse() -> AsyncGenerator[str, None]:
        """Générer les événements SSE via le graphe LangGraph avec tool calling."""
        async with async_session_factory() as sse_db:
            try:
                # Émettre les événements SSE de progression document
                doc_analysis_summary = None
                if doc_upload_info:
                    yield f"data: {json.dumps({'type': 'document_upload', 'document_id': doc_upload_info['document_id'], 'filename': doc_upload_info['filename'], 'status': 'uploaded'})}\n\n"
                    yield f"data: {json.dumps({'type': 'document_status', 'document_id': doc_upload_info['document_id'], 'status': 'extracting'})}\n\n"

                    from app.modules.documents.service import analyze_document, get_document as get_doc
                    doc = await get_doc(sse_db, uuid.UUID(doc_upload_info["document_id"]))

                    if doc:
                        yield f"data: {json.dumps({'type': 'document_status', 'document_id': doc_upload_info['document_id'], 'status': 'analyzing'})}\n\n"

                        try:
                            analysis = await analyze_document(sse_db, doc)
                            doc_analysis_summary = (
                                f"Document : {doc_upload_info['filename']}\n"
                                f"Type : {doc.document_type.value if doc.document_type else 'inconnu'}\n"
                            )
                            if analysis.summary:
                                doc_analysis_summary += f"Résumé : {analysis.summary}\n"
                            if analysis.key_findings:
                                findings = analysis.key_findings
                                if isinstance(findings, list):
                                    doc_analysis_summary += "Points clés :\n" + "\n".join(f"- {f}" for f in findings[:5])

                            yield f"data: {json.dumps({'type': 'document_analysis', 'document_id': doc_upload_info['document_id'], 'summary': analysis.summary or '', 'document_type': doc.document_type.value if doc.document_type else 'autre'})}\n\n"
                        except Exception:
                            logger.exception("Erreur analyse document dans chat")
                            doc_analysis_summary = f"Document reçu : {doc_upload_info['filename']}. Erreur lors de l'analyse."
                            yield f"data: {json.dumps({'type': 'document_status', 'document_id': doc_upload_info['document_id'], 'status': 'error'})}\n\n"

                # Streamer via le graphe LangGraph avec tool calling
                full_response = ""
                guided_tour_emitted = False
                async for event in stream_graph_events(
                    content=user_content,
                    conversation_id=str(conv_id),
                    user_id=user_id,
                    db=sse_db,
                    user_profile=user_profile,
                    context_memory=context_memory,
                    document_analysis_summary=doc_analysis_summary,
                    document_upload=doc_upload_info,
                    widget_response=widget_response_payload,
                    current_page=current_page,
                    guidance_stats=parsed_guidance_stats,
                    active_entities=parsed_active_entities,
                    account_id=current_user.account_id,
                    user_projects=user_projects_state,
                ):
                    event_type = event.get("type")

                    if event_type == "token":
                        full_response += event["content"]
                        yield f"data: {json.dumps(event)}\n\n"

                    elif event_type in (
                        "tool_call_start", "tool_call_end", "tool_call_error",
                        "interactive_question", "interactive_question_resolved",
                        "guided_tour",
                        "profile_update", "profile_completion",
                        # F11 — visualisations typées (KPICard, MatchCard, Map, ComparisonTable)
                        "visualization_block",
                    ):
                        if event_type == "guided_tour":
                            guided_tour_emitted = True
                        yield f"data: {json.dumps(event)}\n\n"

                    elif event_type == "error":
                        yield f"data: {json.dumps(event)}\n\n"

                # BUG-3 (post-fix guided_tour 2026-04-15) : ne pas persister un
                # message assistant vide quand un guided_tour a ete emis.
                # Le prompt GUIDED_TOUR_INSTRUCTION interdit au LLM d'ajouter
                # du texte apres l'appel `trigger_guided_tour` — la reponse
                # est donc intentionnellement vide. Persister cette bulle vide
                # en base produit un artefact visible dans l'UI (historique).
                if not full_response.strip() and guided_tour_emitted:
                    yield f"data: {json.dumps({'type': 'done', 'message_id': None, 'skipped_empty': True})}\n\n"
                else:
                    # Sauvegarder la réponse complète
                    assistant_message = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=full_response,
                    )
                    sse_db.add(assistant_message)
                    await sse_db.flush()
                    await sse_db.refresh(assistant_message)

                    # Lier la question interactive pending creee dans ce tour au
                    # message assistant qui vient d'etre persiste (feature 018).
                    try:
                        from app.models.interactive_question import (
                            InteractiveQuestion as IQ,
                            InteractiveQuestionState as IQState,
                        )
                        await sse_db.execute(
                            update(IQ)
                            .where(
                                IQ.conversation_id == conv_id,
                                IQ.state == IQState.PENDING.value,
                                IQ.assistant_message_id.is_(None),
                            )
                            .values(assistant_message_id=assistant_message.id)
                        )
                    except Exception:  # pragma: no cover
                        logger.debug("Liaison assistant_message_id echouee", exc_info=True)

                    yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_message.id)})}\n\n"

                # Notification rapport : si une evaluation ESG vient d'etre completee
                try:
                    from app.models.esg import ESGAssessment, ESGStatusEnum
                    latest_assessment_result = await sse_db.execute(
                        select(ESGAssessment)
                        .where(
                            ESGAssessment.user_id == user_id,
                            ESGAssessment.status == ESGStatusEnum.completed,
                        )
                        .order_by(ESGAssessment.updated_at.desc())
                        .limit(1)
                    )
                    latest_completed = latest_assessment_result.scalar_one_or_none()
                    if latest_completed:
                        from app.models.report import Report
                        existing_report = await sse_db.execute(
                            select(Report).where(
                                Report.assessment_id == latest_completed.id,
                                Report.user_id == user_id,
                            ).limit(1)
                        )
                        if existing_report.scalar_one_or_none() is None:
                            yield f"data: {json.dumps({'type': 'report_suggestion', 'assessment_id': str(latest_completed.id), 'message': 'Votre evaluation ESG est terminee ! Vous pouvez generer un rapport PDF detaille.'})}\n\n"
                except Exception:
                    logger.debug("Notification rapport : aucune evaluation completee ou erreur")

                await sse_db.commit()

                # Générer un titre automatique en arrière-plan
                if conv_title == "Nouvelle conversation":
                    import asyncio

                    async def _generate_title_bg() -> None:
                        try:
                            from app.graph.nodes import generate_title

                            title = await generate_title(user_content, full_response)
                            async with async_session_factory() as title_db:
                                result = await title_db.execute(
                                    select(Conversation).where(Conversation.id == conv_id)
                                )
                                conv = result.scalar_one_or_none()
                                if conv:
                                    conv.title = title
                                    await title_db.commit()
                        except Exception:
                            pass

                    asyncio.create_task(_generate_title_bg())

            except Exception as e:
                logger.exception("Erreur SSE generate")
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ─── JSON fallback pour l'ancien format ────────────────────────────


@router.post(
    "/conversations/{conversation_id}/messages/json",
)
async def send_message_json(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Envoyer un message en JSON (sans fichier) — compatibilité."""
    return await send_message(
        conversation_id=conversation_id,
        content=data.content,
        file=None,
        interactive_question_id=None,
        interactive_question_values=None,
        interactive_question_justification=None,
        current_page=None,
        guidance_stats=None,
        current_user=current_user,
        db=db,
    )


# ─── Interactive questions endpoints (feature 018) ──────────────────


@router.post("/interactive-questions/{question_id}/abandon")
async def abandon_interactive_question(
    question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Marquer une question interactive comme abandonnee (« Repondre autrement »).

    Permet a l'utilisateur de contourner un widget et reprendre l'input texte.
    """
    from datetime import datetime, timezone

    from app.models.interactive_question import (
        InteractiveQuestion,
        InteractiveQuestionState,
    )

    result = await db.execute(
        select(InteractiveQuestion).where(InteractiveQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="QUESTION_NOT_FOUND")

    # Verifier ownership via la conversation
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == question.conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    if question.state != InteractiveQuestionState.PENDING.value:
        raise HTTPException(status_code=409, detail="QUESTION_NOT_PENDING")

    now = datetime.now(timezone.utc)
    question.state = InteractiveQuestionState.ABANDONED.value
    question.answered_at = now
    await db.flush()

    return {
        "success": True,
        "data": {
            "id": str(question.id),
            "state": question.state,
            "answered_at": now.isoformat(),
        },
    }


@router.get(
    "/conversations/{conversation_id}/interactive-questions",
)
async def list_interactive_questions(
    conversation_id: uuid.UUID,
    state: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lister les questions interactives d'une conversation pour l'hydratation."""
    from app.models.interactive_question import (
        InteractiveQuestion,
        InteractiveQuestionState,
    )
    from app.schemas.interactive_question import InteractiveQuestionResponse

    # Verification ownership
    await get_user_conversation(conversation_id, current_user, db)

    stmt = select(InteractiveQuestion).where(
        InteractiveQuestion.conversation_id == conversation_id,
    )
    if state != "all":
        if state not in {s.value for s in InteractiveQuestionState}:
            raise HTTPException(status_code=422, detail="INVALID_STATE")
        stmt = stmt.where(InteractiveQuestion.state == state)

    stmt = stmt.order_by(InteractiveQuestion.created_at.asc()).limit(limit)
    result = await db.execute(stmt)
    questions = result.scalars().all()

    items = [
        InteractiveQuestionResponse.model_validate(q).model_dump(mode="json")
        for q in questions
    ]
    return {
        "success": True,
        "data": items,
        "meta": {"total": len(items), "limit": limit},
    }
