"""Tools LangChain pour le sourcage F01.

Trois actions :
- cite_source(source_id) : recuperer une source verifiee pour citation.
- search_source(query, publisher, limit=5) : chercher des sources verifiees.
- flag_unsourced(claim, reason) : journaliser une affirmation non sourcable.

Aucun de ces tools ne mute le catalogue (invariant ESG Mefali #7).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user
from app.models.source import Source, VerificationStatus
from app.models.unsourced_flag import UnsourcedFlag

logger = logging.getLogger(__name__)


def _serialize_source_for_llm(source: Source) -> dict:
    """Forme compacte renvoyee au LLM."""
    return {
        "id": str(source.id),
        "title": source.title,
        "publisher": source.publisher,
        "version": source.version,
        "url": source.url,
        "date_publi": source.date_publi.isoformat()
        if isinstance(source.date_publi, date)
        else str(source.date_publi),
        "page": source.page,
        "section": source.section,
    }


@tool
async def cite_source(
    source_id: str,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Cite une source verifiee du catalogue (F01) pour rattacher un chiffre/fait a une reference.

    Use when:
    - tu mentionnes un chiffre/seuil/facteur d'emission a rattacher a une source officielle.
    - apres `search_source`, lorsqu'un UUID a ete identifie.
    Don't use when:
    - source non `verified` (utiliser `search_source` ou `flag_unsourced`).
    - aucun chiffre dans la reponse (citation inutile).
    Exemple: pour citer ADEME Base Carbone v23 -> cite_source(source_id="b3a7c1f2-...").
    Anti: ne jamais inventer un UUID (toujours passer par `search_source`).

    Args:
        source_id: UUID de la source en statut `verified`.

    Returns:
        Texte structure decrivant la source pour citation, ou message d'erreur
        si la source n'existe pas ou n'est pas verifiee.
    """
    from sqlalchemy import select

    try:
        sid = uuid.UUID(source_id)
    except (ValueError, TypeError, AttributeError):
        return "Erreur : identifiant de source invalide (doit etre un UUID)."

    if config is None:
        return "Erreur : contexte d'execution manquant."

    try:
        db, _ = get_db_and_user(config)
    except ValueError as exc:
        return f"Erreur : {exc}"

    result = await db.execute(select(Source).where(Source.id == sid))
    source = result.scalar_one_or_none()
    if source is None:
        return f"Erreur : source {source_id} introuvable dans le catalogue."
    if source.verification_status != VerificationStatus.VERIFIED.value:
        return (
            f"Erreur : la source {source_id} n'est pas en statut 'verified' "
            f"(statut actuel : {source.verification_status}). "
            f"Utilise search_source pour trouver une alternative."
        )
    payload = _serialize_source_for_llm(source)
    return (
        f"Source citee : {payload['title']} ({payload['publisher']}, "
        f"version {payload['version']}, "
        f"publie {payload['date_publi']}). URL : {payload['url']}. "
        f"ID : {payload['id']}."
    )


@tool
async def search_source(
    query: str,
    publisher: str | None = None,
    limit: int = 5,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Recherche des sources verifiees du catalogue (F01) par mots-cles + publisher optionnel.

    Use when:
    - tu as besoin d'une source pour un chiffre mais tu n'as pas l'UUID.
    - exploration : "facteur emission electricite", "taxonomie UEMOA".
    Don't use when:
    - UUID connu (utiliser `cite_source` directement).
    - aucune source ne sera disponible (utiliser `flag_unsourced`).
    Exemple: search_source(query="electricite reseau", publisher="ADEME").
    Anti: requetes longues > 5 mots ; preferer 2-5 mots-cles.

    Args:
        query: Mots-cles de recherche (au moins 2 caracteres).
        publisher: Filtre optionnel par editeur (ADEME, IPCC, UEMOA, etc.).
        limit: Nombre max de resultats (1-5, capped a 5).

    Returns:
        Liste compacte des sources trouvees, ou message si aucune.
    """
    from app.modules.sources.service import SourceService

    if config is None:
        return "Erreur : contexte d'execution manquant."

    try:
        db, _ = get_db_and_user(config)
    except ValueError as exc:
        return f"Erreur : {exc}"

    if not query or len(query.strip()) < 2:
        return "Erreur : la requete doit contenir au moins 2 caracteres."

    service = SourceService(db)
    sources = await service.search(
        query.strip(), publisher=publisher, limit=min(5, max(1, limit)),
    )
    if not sources:
        return (
            "Aucune source verifiee ne correspond a cette recherche. "
            "Utilise flag_unsourced si tu ne peux pas trouver d'autre source."
        )
    lines = [f"{len(sources)} source(s) trouvee(s) :"]
    for src in sources:
        lines.append(
            f"- ID {src.id} : {src.title} ({src.publisher}, "
            f"v{src.version}, publie {src.date_publi})"
        )
    return "\n".join(lines)


@tool
async def flag_unsourced(
    claim: str,
    reason: str,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> str:
    """Signale explicitement une affirmation non sourcable (alternative a inventer une source).

    Use when:
    - tu dois mentionner un chiffre/fait sans source verifiee disponible.
    - apres `search_source` infructueux, tracer l'absence de source.
    Don't use when:
    - une source existe (essayer d'abord `search_source` puis `cite_source`).
    - tu connais l'UUID (utiliser `cite_source`).
    Exemple: flag_unsourced(claim="Secteur informel = 60% emploi", reason="aucune source UEMOA actuelle").
    Anti: utiliser pour eviter de chercher (devoir `search_source` d'abord).

    Args:
        claim: Texte de l'affirmation non sourcable (au moins 5 caracteres).
        reason: Motif explicite de l'absence de source.

    Returns:
        Confirmation que le signalement a ete journalise.
    """
    if not claim or len(claim.strip()) < 5:
        return "Erreur : l'affirmation doit contenir au moins 5 caracteres."
    if not reason or len(reason.strip()) < 3:
        return "Erreur : le motif doit contenir au moins 3 caracteres."

    if config is None:
        return "Erreur : contexte d'execution manquant."

    try:
        db, _ = get_db_and_user(config)
    except ValueError as exc:
        return f"Erreur : {exc}"

    configurable = config.get("configurable", {})
    conv_id = configurable.get("conversation_id")
    if isinstance(conv_id, str):
        try:
            conv_id = uuid.UUID(conv_id)
        except ValueError:
            conv_id = None

    flag = UnsourcedFlag(
        claim=claim.strip(),
        reason=reason.strip(),
        conversation_id=conv_id if isinstance(conv_id, uuid.UUID) else None,
    )
    db.add(flag)
    await db.flush()
    return (
        "Affirmation signalee comme non sourcable. "
        "Le systeme journalisera ce signalement pour revue admin."
    )


SOURCING_TOOLS: list = [cite_source, search_source, flag_unsourced]
