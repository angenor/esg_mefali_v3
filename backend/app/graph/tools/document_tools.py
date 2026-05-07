"""Tools LangChain pour le noeud analyse de documents.

Trois tools exposes au LLM :
- analyze_uploaded_document : lancer l'analyse d'un document
- get_document_analysis : consulter les resultats d'analyse
- list_user_documents : lister les documents de l'utilisateur
"""

import logging
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.graph.tools.common import get_db_and_user

logger = logging.getLogger(__name__)


@tool
async def analyze_uploaded_document(
    document_id: str,
    config: RunnableConfig,
) -> str:
    """Analyse un document uploade (PDF/DOCX/XLSX) avec OCR/extraction et resume IA.

    Use when:
    - un document vient d'etre uploade (`status='pending'` ou `'uploaded'`).
    - re-analyse explicitement demandee (changement de modele).
    Don't use when:
    - document deja analyse (utiliser `get_document_analysis`).
    - simple liste demandee (utiliser `list_user_documents`).
    Exemple: "Analyse mon bilan financier" + document_id -> analyze_uploaded_document(document_id=...).
    Anti: "Que disait mon document ?" -> NE PAS appeler (utiliser `get_document_analysis`).

    Args:
        document_id: Identifiant UUID du document a analyser.
    """
    from app.modules.documents.service import analyze_document, get_document

    try:
        db, _user_id = get_db_and_user(config)

        document = await get_document(db=db, document_id=uuid.UUID(document_id))
        if document is None:
            return f"Document introuvable (id={document_id})."

        analysis = await analyze_document(db=db, document=document)

        findings = analysis.key_findings if hasattr(analysis, "key_findings") and analysis.key_findings else []
        findings_text = "\n".join(f"  - {f}" for f in findings[:5]) if findings else "  Aucun point cle identifie."

        return (
            f"Analyse du document '{document.filename}' terminee.\n"
            f"- Type : {analysis.document_type}\n"
            f"- Resume : {analysis.summary[:300] if analysis.summary else 'N/A'}\n"
            f"- Points cles :\n{findings_text}\n"
            f"- Confiance : {getattr(analysis, 'confidence_score', 'N/A')}"
        )
    except Exception as e:
        logger.exception("Erreur lors de l'analyse du document %s", document_id)
        return f"Erreur lors de l'analyse du document : {e}"


@tool
async def get_document_analysis(
    document_id: str,
    config: RunnableConfig,
) -> str:
    """Consulte les resultats d'analyse d'un document deja analyse (resume + points cles).

    Use when:
    - "que dit mon document", "resume du PDF", apres analyse achevee.
    - decision basee sur le contenu (matching financement, plan).
    Don't use when:
    - document non analyse (utiliser `analyze_uploaded_document`).
    - liste de documents (utiliser `list_user_documents`).
    Exemple: "Resume mon business plan" -> get_document_analysis(document_id=...).
    Anti: "Documents disponibles ?" -> NE PAS appeler (utiliser `list_user_documents`).

    Args:
        document_id: Identifiant UUID du document.
    """
    from app.modules.documents.service import get_document

    try:
        db, _user_id = get_db_and_user(config)

        document = await get_document(db=db, document_id=uuid.UUID(document_id))
        if document is None:
            return f"Document introuvable (id={document_id})."

        analysis = document.analysis if hasattr(document, "analysis") else None
        if analysis is None:
            return (
                f"Le document '{document.filename}' n'a pas encore ete analyse. "
                f"Utilisez le tool analyze_uploaded_document pour lancer l'analyse."
            )

        findings = analysis.key_findings if hasattr(analysis, "key_findings") and analysis.key_findings else []
        findings_text = "\n".join(f"  - {f}" for f in findings[:5]) if findings else "  Aucun point cle identifie."

        return (
            f"Resultats d'analyse de '{document.filename}' :\n"
            f"- Type : {analysis.document_type}\n"
            f"- Resume : {analysis.summary[:300] if analysis.summary else 'N/A'}\n"
            f"- Points cles :\n{findings_text}\n"
            f"- Confiance : {getattr(analysis, 'confidence_score', 'N/A')}"
        )
    except Exception as e:
        logger.exception("Erreur lors de la consultation de l'analyse du document %s", document_id)
        return f"Erreur lors de la consultation de l'analyse : {e}"


@tool
async def list_user_documents(
    config: RunnableConfig,
    document_type: str | None = None,
) -> str:
    """Liste les documents uploades par l'utilisateur (avec filtre type optionnel).

    Use when:
    - "mes documents", "qu'est-ce que j'ai uploade".
    - decider quel document analyser ensuite (filtre par type).
    Don't use when:
    - analyse demandee (utiliser `analyze_uploaded_document`).
    - resultats d'un document precis (utiliser `get_document_analysis`).
    Exemple: "Liste mes documents PDF" -> list_user_documents(document_type='pdf').
    Anti: "Analyse mon dernier document" -> NE PAS appeler (utiliser `analyze_uploaded_document`).

    Args:
        document_type: Filtrer par type de document (optionnel).
    """
    from app.modules.documents.service import list_documents

    try:
        db, user_id = get_db_and_user(config)

        documents, total = await list_documents(
            db=db,
            user_id=user_id,
            document_type=document_type,
        )

        if not documents:
            return "Aucun document trouve pour cet utilisateur."

        lines: list[str] = [f"{total} document(s) trouve(s) :"]
        for doc in documents[:10]:
            status = doc.status if hasattr(doc, "status") else "N/A"
            lines.append(
                f"  - {doc.filename} (type: {doc.document_type or 'N/A'}, "
                f"statut: {status}, id: {doc.id})"
            )

        if total > 10:
            lines.append(f"  ... et {total - 10} autres documents.")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("Erreur lors de la liste des documents")
        return f"Erreur lors de la liste des documents : {e}"


DOCUMENT_TOOLS = [analyze_uploaded_document, get_document_analysis, list_user_documents]
