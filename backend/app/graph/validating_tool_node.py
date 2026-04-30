"""Story 10.4 — `ValidatingToolNode` : boucle de correction Pydantic bornee a 1 retry + fallback texte FR.

Composition autour de `langgraph.prebuilt.ToolNode` (NE PAS subclasser).

Flux :
1. Recuperer les `tool_calls` du dernier `AIMessage`.
2. Pour chaque tool_call : valider `args` contre `tool.args_schema` (Pydantic v2).
3. Si valide -> executer le tool (via `tool.ainvoke(args, config)`) et journaliser
   `validation_status="valid"` (ou `"valid_after_retry"` si compteur > 0).
4. Si `ValidationError` au 1er essai (`pydantic_retries[id] == 0`) -> ToolMessage avec
   format AC3 FR et incrementer le compteur. Pas de log final ici (le retry suivra).
5. Si `ValidationError` au 2eme essai (`pydantic_retries[id] >= max=1`) -> ToolMessage
   fallback FR, log `validation_status="failed_after_retry"`, flag `validation_failed=True`,
   force `tool_call_count = MAX_TOOL_CALLS_PER_TURN` pour terminer la boucle (cf. AC4 + §6 spec).

Verrous :
- `with_retry` (`tools/common.py`) gere une couche disjointe (exceptions runtime). NE PAS y toucher.
- Schemas Pydantic verrouilles (story 10.1) : on consomme, on ne modifie pas.
- Aucun appel LLM dans ce noeud — purement deterministe.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode  # composition (pas heritage)
from pydantic import BaseModel, ValidationError

from app.graph.tools.common import get_db_and_user, log_tool_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes & messages
# ---------------------------------------------------------------------------


# Message FR fallback (CLAUDE.md = accents obligatoires).
PYDANTIC_FALLBACK_MESSAGE = (
    "Je n'arrive pas à formaliser cette action correctement. "
    "Pourrais-tu reformuler ta demande ou préciser les informations manquantes ? "
    "(Erreur technique : payload invalide après 1 tentative de correction.)"
)

# Limite par ligne de l'erreur structuree envoyee au LLM (AC3 spec §8).
_MAX_LINE_LEN = 200

# Mapping types Pydantic v2 -> messages humanises FR (AC3 spec §8).
_TYPE_HINT_FR: dict[str, str] = {
    "string_type": "doit être un string",
    "int_type": "doit être un integer",
    "float_type": "doit être un float",
    "bool_type": "doit être un boolean",
    "list_type": "doit être une liste",
    "dict_type": "doit être un dict",
}


# ---------------------------------------------------------------------------
# Helper format_pydantic_errors_for_llm (AC3)
# ---------------------------------------------------------------------------


def _format_loc(loc: tuple | list) -> str:
    """Joindre `loc` (tuple Pydantic) en notation pointee."""
    return ".".join(str(part) for part in loc)


def _humanize_error(err: dict) -> str:
    """Convertir un item de `exc.errors()` en message FR humanise."""
    err_type = err.get("type", "")
    raw_msg = err.get("msg", "")

    if err_type == "missing":
        return "champ requis manquant"

    if err_type == "enum":
        ctx = err.get("ctx") or {}
        expected = ctx.get("expected") or raw_msg
        input_value = err.get("input")
        return f"doit être un enum parmi [{expected}], tu as envoyé {input_value!r}"

    if err_type in _TYPE_HINT_FR:
        return _TYPE_HINT_FR[err_type]

    # Fallback : message Pydantic brut (deja relativement clair).
    return raw_msg or "valeur invalide"


def format_pydantic_errors_for_llm(tool_name: str, errors: list[dict]) -> str:
    """Formater une liste d'erreurs Pydantic v2 en message FR structure pour le LLM.

    Format (AC3) :
        Le tool {tool_name} a rejeté ton appel. Erreurs :
        - field "{loc}": {message_humanise}
        ...
        Réessaie avec un payload corrigé.

    Chaque ligne d'erreur tronquee a 200 caracteres avec suffixe `...`.
    """
    lines: list[str] = [f"Le tool {tool_name} a rejeté ton appel. Erreurs :"]
    for err in errors:
        loc = _format_loc(err.get("loc") or ())
        humanized = _humanize_error(err)
        line = f'- field "{loc}": {humanized}'
        if len(line) > _MAX_LINE_LEN:
            line = line[: _MAX_LINE_LEN - 3] + "..."
        lines.append(line)
    lines.append("Réessaie avec un payload corrigé.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ValidatingToolNode (AC1, AC7)
# ---------------------------------------------------------------------------


class ValidatingToolNode:
    """Wrapper compose autour de `langgraph.prebuilt.ToolNode` ajoutant
    une boucle de validation Pydantic bornee a 1 retry + fallback FR.

    Args:
        tools: Liste des tools LangChain (memes objets que ceux passes a `bind_tools`).
        node_name: Nom du noeud parent (pour journalisation `tool_call_logs.node_name`).
        max_pydantic_retries: Nombre max de retries Pydantic par tool_call_id.
            Hard-code a 1 par contrat epic. Argument reserve aux tests.
    """

    def __init__(
        self,
        tools: list,
        *,
        node_name: str,
        max_pydantic_retries: int = 1,
    ) -> None:
        # Composition : instance ToolNode conservee pour conformite contractuelle (AC1 §1)
        # et delegation potentielle future. L'execution effective passe par tool.ainvoke
        # direct afin de pouvoir tester unitairement sans Runtime LangGraph complet.
        self._inner = ToolNode(tools)
        self._tools_by_name: dict[str, Any] = {t.name: t for t in tools}
        # Avertir si un tool n'a pas d'args_schema — verrou story 10.1 garantit qu'ils
        # en ont tous un, mais si un futur tool casse l'invariant, la validation Pydantic
        # est silencieusement bypassee. Trace de log plutot que crash.
        for _t in tools:
            if getattr(_t, "args_schema", None) is None:
                logger.warning(
                    "Tool %s sans args_schema — validation Pydantic ignoree (story 10.4)",
                    getattr(_t, "name", "?"),
                )
        self._node_name = node_name
        self._max_pydantic_retries = max_pydantic_retries
        # Exposes pour la retro-compat des tests qui inspectent
        # un ToolNode (cf. test_guided_tour_toolnode_registration).
        self.tools_by_name = self._tools_by_name
        self.tools = list(tools)

    async def __call__(self, state, config=None):
        # NB : les annotations sont volontairement absentes pour la signature
        # publique appelee par LangGraph — `from __future__ import annotations`
        # convertit `RunnableConfig | None` en string et le runtime LangGraph
        # emet alors un UserWarning sur la frappe (cf. _runnable.py:311).
        from app.graph.graph import MAX_TOOL_CALLS_PER_TURN

        messages = state.get("messages") or []
        if not messages:
            return {"messages": []}

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}

        # Etat retries (par tool_call_id). Retro-compat : None autorise.
        retries: dict[str, int] = dict(state.get("pydantic_retries") or {})
        validation_failed = bool(state.get("validation_failed"))
        forced_tool_call_count: int | None = None

        out_messages: list[ToolMessage] = []

        for call in last.tool_calls:
            tool_call_id = call.get("id") or _stable_fallback_id(
                call.get("name"), call.get("args")
            )
            tool_name = call.get("name") or ""
            args = call.get("args") or {}

            tool_obj = self._tools_by_name.get(tool_name)
            if tool_obj is None:
                # Tool inconnu — repondre au tool_call_id (contrat LangGraph) + audit + comptage.
                error_msg = f"Erreur : tool '{tool_name}' indisponible."
                out_messages.append(
                    ToolMessage(content=error_msg, tool_call_id=tool_call_id)
                )
                retries[tool_call_id] = retries.get(tool_call_id, 0) + 1
                await self._safe_log(
                    config=config,
                    tool_name=tool_name,
                    tool_args=args,
                    tool_result=None,
                    duration_ms=None,
                    status="error",
                    retry_count=retries[tool_call_id] - 1,
                    validation_status="unknown_tool",
                    pydantic_errors=None,
                    error_message=error_msg,
                )
                continue

            current_retry = retries.get(tool_call_id, 0)

            # 1. Tentative de validation Pydantic (si schema disponible)
            args_schema = getattr(tool_obj, "args_schema", None)
            validation_error: ValidationError | None = None
            if args_schema is not None:
                try:
                    args_schema.model_validate(args)
                except ValidationError as exc:
                    validation_error = exc

            if validation_error is None:
                # 2. Payload valide -> executer le tool
                msg, log_status = await self._execute_tool(
                    tool_obj=tool_obj,
                    tool_call_id=tool_call_id,
                    args=args,
                    config=config,
                )
                out_messages.append(msg)
                await self._safe_log(
                    config=config,
                    tool_name=tool_name,
                    tool_args=args,
                    tool_result={"content": str(msg.content)},
                    duration_ms=None,
                    status=log_status,
                    retry_count=current_retry,
                    validation_status=("valid" if current_retry == 0 else "valid_after_retry"),
                    pydantic_errors=None,
                )
                continue

            # 3. ValidationError -> 1er ou 2eme essai ?
            # Le formatage LLM consomme les erreurs RAW (pour afficher la valeur fautive
            # dans le diagnostic enum), tandis que la persistance DB filtre `input` (spec §9).
            raw_errors = validation_error.errors()
            filtered_errors = _filter_pydantic_errors(raw_errors)

            if current_retry < self._max_pydantic_retries:
                # 1er echec : message structure FR au LLM, log d'audit, incrementation du compteur.
                structured = format_pydantic_errors_for_llm(tool_name, raw_errors)
                out_messages.append(
                    ToolMessage(content=structured, tool_call_id=tool_call_id)
                )
                retries[tool_call_id] = current_retry + 1
                # Log d'audit du 1er echec (AC7 : "apres chaque tentative").
                await self._safe_log(
                    config=config,
                    tool_name=tool_name,
                    tool_args=args,
                    tool_result=None,
                    duration_ms=None,
                    status="error",
                    retry_count=current_retry,
                    validation_status="invalid_first_attempt",
                    pydantic_errors=filtered_errors,
                    error_message=structured,
                )
            else:
                # 2eme echec consecutif : fallback FR + flag terminaison.
                out_messages.append(
                    ToolMessage(
                        content=PYDANTIC_FALLBACK_MESSAGE,
                        tool_call_id=tool_call_id,
                    )
                )
                validation_failed = True
                forced_tool_call_count = MAX_TOOL_CALLS_PER_TURN
                await self._safe_log(
                    config=config,
                    tool_name=tool_name,
                    # Persister les args rejetes (debug) — `pydantic_errors.input` est filtre
                    # cote DB, mais le payload complet va dans `tool_args` pour audit.
                    tool_args=args,
                    tool_result=None,
                    duration_ms=None,
                    status="error",
                    retry_count=current_retry,
                    validation_status="failed_after_retry",
                    pydantic_errors=filtered_errors,
                    error_message=PYDANTIC_FALLBACK_MESSAGE,
                )

        # Construction du delta state retourne au reducer LangGraph.
        update: dict[str, Any] = {
            "messages": out_messages,
            "pydantic_retries": retries,
        }
        if validation_failed:
            update["validation_failed"] = True
        if forced_tool_call_count is not None:
            update["tool_call_count"] = forced_tool_call_count
        return update

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    async def _execute_tool(
        self,
        *,
        tool_obj: Any,
        tool_call_id: str,
        args: dict,
        config: RunnableConfig | None,
    ) -> tuple[ToolMessage, str]:
        """Executer le tool valide et retourner (ToolMessage, status_log).

        Serialisation des resultats non-string en JSON (alignement avec le ToolNode standard) ;
        les `BaseModel` Pydantic sont serialises via `model_dump`.
        """
        try:
            cfg = config or {"configurable": {}}
            result = await tool_obj.ainvoke(args, config=cfg)
            content = _serialize_tool_result(result)
            return (
                ToolMessage(content=content, tool_call_id=tool_call_id),
                "success",
            )
        except Exception as exc:  # noqa: BLE001 — la couche `with_retry` formatte deja les exc runtime
            logger.warning(
                "Tool %s a leve une exception runtime apres validation Pydantic OK : %s",
                getattr(tool_obj, "name", "?"),
                exc,
                exc_info=True,
            )
            return (
                ToolMessage(content=f"Erreur : {exc}", tool_call_id=tool_call_id),
                "error",
            )

    async def _safe_log(
        self,
        *,
        config: RunnableConfig | None,
        tool_name: str,
        tool_args: dict,
        tool_result: dict | None,
        duration_ms: int | None,
        status: str,
        retry_count: int,
        validation_status: str,
        pydantic_errors: list[dict] | None,
        error_message: str | None = None,
    ) -> None:
        """Journaliser le tool call avec defense en profondeur (AC7).

        Toute exception du log est avalee — la boucle ne doit pas casser
        sur une erreur de journalisation (pattern `with_retry` lignes 145-146).
        """
        if not config:
            return
        try:
            db, user_id = get_db_and_user(config)
        except Exception:  # config sans db/user -> log silencieux
            logger.debug("Pas de db/user_id dans config, log_tool_call skip", exc_info=True)
            return

        configurable = (config or {}).get("configurable", {}) or {}
        tools_offered = configurable.get("tools_offered")
        if not (isinstance(tools_offered, list) and all(isinstance(v, str) for v in tools_offered)):
            tools_offered = None

        try:
            await log_tool_call(
                db,
                user_id=user_id,
                conversation_id=configurable.get("conversation_id"),
                node_name=self._node_name,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                duration_ms=duration_ms,
                status=status,
                error_message=error_message,
                retry_count=retry_count,
                tools_offered=tools_offered,
                validation_status=validation_status,
                pydantic_errors=pydantic_errors,
            )
        except Exception:
            logger.debug(
                "Erreur lors de la journalisation tool_call_logs (story 10.4)",
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Helpers prives
# ---------------------------------------------------------------------------


def _stable_fallback_id(tool_name: str | None, args: dict | None) -> str:
    """ID de repli stable pour tool_call (Python `hash()` est randomise par PYTHONHASHSEED).

    Utilise SHA-1 tronque sur (name, args JSON-serialized). Suffisant pour servir
    de cle dans le compteur de retries — pas un identifiant cryptographique.
    """
    raw = json.dumps([tool_name or "", args or {}], sort_keys=True, default=str)
    return f"hash:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _serialize_tool_result(result: Any) -> str:
    """Serialiser un resultat de tool en string (alignement avec ToolNode standard).

    - str -> tel quel
    - BaseModel Pydantic -> model_dump_json
    - dict / list -> json.dumps(default=str)
    - autre -> str(...)
    """
    if isinstance(result, str):
        return result
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(result)
    return str(result)


def _filter_pydantic_errors(errors: list[dict]) -> list[dict]:
    """Filtrer `exc.errors()` pour ne conserver que `loc`, `msg`, `type`.

    Le champ `input` peut contenir des secrets (cf. spec §9). On l'elimine
    avant journalisation et avant envoi au LLM.
    """
    out: list[dict] = []
    for err in errors:
        out.append(
            {
                "loc": list(err.get("loc") or []),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return out
