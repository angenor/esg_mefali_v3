"""F11 — Validator pour intercepter les ValidationError Pydantic des tools typed.

Politique :
- 1er passage (retry_count=0) : message d'erreur structuré renvoyé au LLM avec
  retry demandé.
- 2e passage (retry_count=1) : fallback texte (pas de nouveau retry).

Ce validator est complémentaire de ``source_required.py`` : il ne se déclenche
que pour les ValidationError Pydantic des tools de visualisation typed
(show_kpi_card, show_match_card, show_map, show_comparison_table).

Voir contracts/visualization-tools.md §"Politique d'erreurs LLM".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import ValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PayloadInvalidResult:
    """Résultat de la gestion d'un payload invalide."""

    requires_retry: bool
    fallback_text: str | None = None
    llm_error_message: str | None = None


# Texte de fallback affiché à l'utilisateur si le 2e essai échoue.
_FALLBACK_TEXT = (
    "[je n'ai pas pu rendre cette visualisation correctement, "
    "voici la réponse en texte]"
)


def build_llm_error_message(
    *,
    tool_name: str,
    schema_name: str,
    error: ValidationError,
) -> str:
    """Construire un message d'erreur structuré à renvoyer au LLM.

    Le message doit guider le LLM vers (a) une nouvelle tentative avec un
    payload conforme au schéma, (b) ou un fallback texte si l'information
    n'est pas disponible. Limite la taille du message pour éviter l'inflation
    du contexte (max 5 erreurs énumérées).
    """
    error_lines: list[str] = []
    for err in error.errors()[:5]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalide")
        error_lines.append(f"- champ `{loc}` : {msg}")
    bullet_list = "\n".join(error_lines) if error_lines else "- payload invalide"

    return (
        f"L'appel au tool `{tool_name}` a échoué : le payload ne respecte "
        f"pas le schéma `{schema_name}`.\n\n"
        f"Erreurs détectées :\n{bullet_list}\n\n"
        f"Retente avec un payload conforme au schéma `{schema_name}`, "
        f"ou réponds en texte simple si l'information n'est pas disponible."
    )


def handle_payload_invalid(
    *,
    tool_name: str,
    schema_name: str,
    error: ValidationError,
    retry_count: int,
) -> PayloadInvalidResult:
    """Décider de l'action à prendre face à un payload invalide.

    Args:
        tool_name: nom du tool LangChain (ex: "show_kpi_card").
        schema_name: nom du schéma Pydantic (ex: "KPICardArgs").
        error: l'exception ValidationError levée.
        retry_count: 0 = premier passage, ≥ 1 = retry déjà tenté.

    Returns:
        PayloadInvalidResult immuable indiquant : retry à demander OU
        fallback texte à utiliser.
    """
    if retry_count == 0:
        message = build_llm_error_message(
            tool_name=tool_name,
            schema_name=schema_name,
            error=error,
        )
        logger.info(
            "Payload invalide pour tool=%s, schéma=%s, retry demandé",
            tool_name,
            schema_name,
        )
        return PayloadInvalidResult(
            requires_retry=True,
            fallback_text=None,
            llm_error_message=message,
        )

    # 2e tentative : fallback texte, pas de nouveau retry.
    logger.warning(
        "Payload invalide pour tool=%s après retry — fallback texte",
        tool_name,
    )
    return PayloadInvalidResult(
        requires_retry=False,
        fallback_text=_FALLBACK_TEXT,
        llm_error_message=None,
    )


__all__ = [
    "PayloadInvalidResult",
    "build_llm_error_message",
    "handle_payload_invalid",
]
