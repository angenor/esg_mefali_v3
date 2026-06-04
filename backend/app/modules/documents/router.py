"""Router FastAPI pour le module documents (upload, analyse, CRUD)."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.documents.schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    ReanalyzeResponse,
)
from app.modules.documents.service import (
    delete_document,
    get_document,
    list_documents,
    upload_document,
)

router = APIRouter()

MAX_FILES_PER_UPLOAD = 5


# ─── Helpers ──────────────────────────────────────────────────────────


def _check_document_ownership(document, user: User) -> None:
    """Vérifier que l'utilisateur est propriétaire du document."""
    if document.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé",
        )


def _document_to_response(document) -> DocumentResponse:
    """Convertir un Document ORM en DocumentResponse."""
    return DocumentResponse(
        id=document.id,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size=document.file_size,
        status=document.status,
        document_type=document.document_type,
        has_analysis=document.analysis is not None
        if hasattr(document, "analysis") and document.analysis is not None
        else False,
        created_at=document.created_at,
    )


# ─── POST /upload ────────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    files: list[UploadFile] = File(...),
    conversation_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Uploader un ou plusieurs fichiers (max 5)."""
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_FILES_PER_UPLOAD} fichiers par upload",
        )

    uploaded_docs: list[DocumentResponse] = []

    for file in files:
        content = await file.read()
        try:
            doc = await upload_document(
                db=db,
                user_id=current_user.id,
                filename=file.filename or "document",
                content=content,
                content_type=file.content_type or "application/octet-stream",
                file_size=len(content),
                conversation_id=conversation_id,
                # F02 — tenant requis (documents.account_id NOT NULL en PostgreSQL).
                account_id=current_user.account_id,
            )
            uploaded_docs.append(
                DocumentResponse(
                    id=doc.id,
                    original_filename=doc.original_filename,
                    mime_type=doc.mime_type,
                    file_size=doc.file_size,
                    status=doc.status,
                    document_type=doc.document_type,
                    has_analysis=False,
                    created_at=doc.created_at,
                )
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    return DocumentUploadResponse(documents=uploaded_docs)


# ─── GET / ───────────────────────────────────────────────────────────


@router.get("/", response_model=DocumentListResponse)
async def list_user_documents(
    document_type: str | None = Query(None),
    document_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """Lister les documents de l'utilisateur avec filtres et pagination."""
    documents, total = await list_documents(
        db=db,
        user_id=current_user.id,
        document_type=document_type,
        status=document_status,
        page=page,
        limit=limit,
    )

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                original_filename=doc.original_filename,
                mime_type=doc.mime_type,
                file_size=doc.file_size,
                status=doc.status,
                document_type=doc.document_type,
                has_analysis=False,
                created_at=doc.created_at,
            )
            for doc in documents
        ],
        total=total,
        page=page,
        limit=limit,
    )


# ─── GET /{id} ───────────────────────────────────────────────────────


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Récupérer le détail d'un document avec son analyse."""
    document = await get_document(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé",
        )

    _check_document_ownership(document, current_user)

    from app.modules.documents.schemas import DocumentAnalysisResponse

    analysis_response = None
    if document.analysis is not None:
        analysis_response = DocumentAnalysisResponse.model_validate(document.analysis)

    return DocumentDetailResponse(
        id=document.id,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size=document.file_size,
        status=document.status,
        document_type=document.document_type,
        created_at=document.created_at,
        analysis=analysis_response,
    )


# ─── DELETE /{id} ────────────────────────────────────────────────────


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Supprimer un document (fichier physique + BDD)."""
    document = await get_document(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé",
        )

    _check_document_ownership(document, current_user)
    await delete_document(db, document)


# ─── POST /{id}/reanalyze ───────────────────────────────────────────


@router.post("/{document_id}/reanalyze", response_model=ReanalyzeResponse)
async def reanalyze_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReanalyzeResponse:
    """Relancer l'analyse d'un document."""
    document = await get_document(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé",
        )

    _check_document_ownership(document, current_user)

    from app.models.document import DocumentStatus

    document.status = DocumentStatus.processing
    await db.flush()

    return ReanalyzeResponse(
        id=document.id,
        status=document.status,
        message="Analyse relancée avec succès",
    )


# ─── GET /{id}/preview ─────────────────────────────────────────────


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Servir le fichier pour prévisualisation (images et PDFs)."""
    document = await get_document(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé",
        )

    _check_document_ownership(document, current_user)

    from app.modules.documents.service import UPLOADS_DIR

    file_path = Path(UPLOADS_DIR.parent / document.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier introuvable sur le serveur",
        )

    return FileResponse(
        path=str(file_path),
        media_type=document.mime_type,
        filename=document.original_filename,
    )
