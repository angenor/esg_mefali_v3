"""Schemas Pydantic pour le module Dossiers de Candidature."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.models.application import STATUS_LABELS


# --- Enumerations (paralleles aux modeles SQLAlchemy) ---


class TargetTypeEnum(str, Enum):
    fund_direct = "fund_direct"
    intermediary_bank = "intermediary_bank"
    intermediary_agency = "intermediary_agency"
    intermediary_developer = "intermediary_developer"


class ApplicationStatusEnum(str, Enum):
    draft = "draft"
    preparing_documents = "preparing_documents"
    in_progress = "in_progress"
    review = "review"
    ready_for_intermediary = "ready_for_intermediary"
    ready_for_fund = "ready_for_fund"
    submitted_to_intermediary = "submitted_to_intermediary"
    submitted_to_fund = "submitted_to_fund"
    under_review = "under_review"
    accepted = "accepted"
    rejected = "rejected"


class SectionStatusEnum(str, Enum):
    not_generated = "not_generated"
    generated = "generated"
    validated = "validated"


# --- Schemas de creation ---


class ApplicationCreate(BaseModel):
    """Creation d'un dossier de candidature.

    F048 (D5) — parité chat/UI : ``offer_id`` et ``project_id`` permettent au
    bouton « Candidater » (UI) et au tool chat de passer par le même service de
    création. Si ``offer_id`` est fourni, il est prioritaire : ``fund_id`` et
    ``intermediary_id`` sont dérivés de l'offre côté service. ``fund_id`` reste
    requis pour la compatibilité descendante (legacy direct fonds).
    """

    fund_id: uuid.UUID | None = None
    offer_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    intermediary_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _require_offer_or_fund(self) -> "ApplicationCreate":
        """Au moins une cible doit être fournie (offre prioritaire, sinon fonds)."""
        if self.offer_id is None and self.fund_id is None:
            raise ValueError(
                "Un identifiant d'offre (offer_id) ou de fonds (fund_id) est requis."
            )
        return self


# --- Schemas de mise a jour ---


class ApplicationStatusUpdate(BaseModel):
    """Mise a jour du statut d'un dossier."""

    status: ApplicationStatusEnum


class SectionGenerateRequest(BaseModel):
    """Demande de generation d'une section."""

    section_key: str = Field(min_length=1)


class SectionUpdateRequest(BaseModel):
    """Mise a jour manuelle d'une section."""

    content: str | None = None
    status: SectionStatusEnum | None = None


class AttachDocumentRequest(BaseModel):
    """049 — Rattachement (ou remplacement) du document d'un item de checklist.

    Un ``document_id`` mal formé ou absent → 422 (validation Pydantic), conforme
    au contrat ``attach-document.md`` (FR-001..FR-004, FR-007).
    """

    document_id: uuid.UUID


class ExportRequest(BaseModel):
    """Demande d'export."""

    format: str = Field(pattern="^(pdf|docx)$")


# --- Schemas de reponse ---


class SectionResponse(BaseModel):
    """Reponse section generee/modifiee."""

    section_key: str
    title: str
    content: str | None = None
    status: str
    updated_at: datetime | None = None


class FundInfo(BaseModel):
    """Info fonds dans un dossier."""

    id: uuid.UUID
    name: str
    organization: str

    model_config = {"from_attributes": True}


class IntermediaryInfo(BaseModel):
    """Info intermediaire dans un dossier."""

    id: uuid.UUID
    name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    physical_address: str | None = None

    model_config = {"from_attributes": True}


class MatchInfo(BaseModel):
    """Info match dans un dossier."""

    id: uuid.UUID
    compatibility_score: int

    model_config = {"from_attributes": True}


class SectionsProgress(BaseModel):
    """Progression des sections."""

    total: int
    generated: int
    validated: int


class DocumentRef(BaseModel):
    """049 — Référence légère vers un document rattaché à un item de checklist.

    Exposée dans la sérialisation enrichie de la checklist (sous-objet
    ``document``) pour afficher le nom du fichier (FR-004) et permettre
    l'aperçu (FR-005) sans recharger la liste documentaire complète.
    """

    id: uuid.UUID
    original_filename: str
    mime_type: str
    status: str

    model_config = {"from_attributes": True}


class ChecklistItem(BaseModel):
    """Element de checklist (forme de SORTIE enrichie — ``ChecklistItemOut``).

    049 — ``status`` est le statut EFFECTIF (revalidé à la sérialisation) et
    ``document`` est peuplé par chargement groupé des ``document_id`` non nuls.
    Un item dont le document est introuvable/supprimé est renvoyé
    ``status="missing"``, ``document=null`` (défense en profondeur, research D3).
    """

    key: str
    name: str
    status: str
    document_id: uuid.UUID | None = None
    required_by: str
    document: DocumentRef | None = None


class ChecklistProgress(BaseModel):
    """049 — Progression documentaire d'un dossier (FR-008, SC-004)."""

    provided: int
    total: int


class ApplicationSummary(BaseModel):
    """Resume d'un dossier pour les listes."""

    id: uuid.UUID
    fund_name: str
    intermediary_name: str | None = None
    target_type: TargetTypeEnum
    status: ApplicationStatusEnum
    status_label: str
    sections_progress: SectionsProgress
    checklist_progress: ChecklistProgress
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    """Detail complet d'un dossier."""

    id: uuid.UUID
    fund: FundInfo
    intermediary: IntermediaryInfo | None = None
    match: MatchInfo | None = None
    target_type: TargetTypeEnum
    status: ApplicationStatusEnum
    status_label: str
    sections: dict
    checklist: list[ChecklistItem]
    checklist_progress: ChecklistProgress
    intermediary_prep: dict | None = None
    simulation: dict | None = None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    """Liste paginee de dossiers."""

    items: list[ApplicationSummary]
    total: int


class ApplicationStatusResponse(BaseModel):
    """Reponse apres mise a jour du statut."""

    id: uuid.UUID
    status: ApplicationStatusEnum
    status_label: str
    updated_at: datetime


# --- Helpers ---


def get_status_label(status: str) -> str:
    """Retourner le libelle francais d'un statut."""
    return STATUS_LABELS.get(status, status)


def compute_sections_progress(sections: dict) -> SectionsProgress:
    """Calculer la progression des sections."""
    total = len(sections)
    generated = sum(
        1 for s in sections.values()
        if s.get("status") in ("generated", "validated")
    )
    validated = sum(
        1 for s in sections.values()
        if s.get("status") == "validated"
    )
    return SectionsProgress(total=total, generated=generated, validated=validated)


def compute_checklist_progress(items: list) -> ChecklistProgress:
    """049 — Calculer la progression documentaire (FR-008, SC-004).

    Compte les items au statut « provided ». Accepte aussi bien des items
    stockés (dict) que des items sérialisés (statut effectif) : un item est
    « provided » ssi son champ ``status`` vaut ``"provided"``.
    """
    total = len(items)
    provided = sum(
        1 for it in items
        if (it.get("status") if isinstance(it, dict) else getattr(it, "status", None))
        == "provided"
    )
    return ChecklistProgress(provided=provided, total=total)
