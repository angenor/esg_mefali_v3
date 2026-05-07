"""F05 — Export RGPD (Art. 15 + Art. 20).

Construit un fichier ZIP exhaustif contenant toutes les données stockées
pour l'``account_id`` courant. Mode synchrone si la taille estimée est
≤ 100 MB ; sinon délégué à ``BackgroundTasks`` FastAPI (post-MVP).
"""

from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction, AuditSourceOfChange
from app.core.url_signer import sign_export_url
from app.models.account import Account
from app.models.application import FundApplication
from app.models.attestation import Attestation
from app.models.audit_log import AuditLog
from app.models.carbon import CarbonAssessment
from app.models.company import CompanyProfile
from app.models.consent import Consent
from app.models.conversation import Conversation
from app.models.credit import CreditScore
from app.models.document import Document
from app.models.esg import ESGAssessment
from app.models.message import Message
from app.models.project import Project
from app.models.user import User

logger = logging.getLogger(__name__)


# Seuil au-delà duquel on bascule en async (envoi par email).
SYNC_EXPORT_THRESHOLD_BYTES: int = 100 * 1024 * 1024  # 100 MB


_EXPORT_TABLES: dict[str, type] = {
    "users": User,
    "profile": CompanyProfile,
    "projects": Project,
    "applications": FundApplication,
    "esg_assessments": ESGAssessment,
    "carbon_assessments": CarbonAssessment,
    "credit_scores": CreditScore,
    "documents": Document,
    "conversations": Conversation,
    "messages": Message,
    "attestations": Attestation,
    "consents": Consent,
}


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Sérialise un row SQLAlchemy en dict JSON-safe."""
    out: dict[str, Any] = {}
    mapper = inspect(row.__class__)
    for col in mapper.column_attrs:
        v = getattr(row, col.key)
        if isinstance(v, uuid.UUID):
            out[col.key] = str(v)
        elif isinstance(v, datetime):
            out[col.key] = v.isoformat()
        elif isinstance(v, bytes):
            out[col.key] = v.decode("utf-8", errors="replace")
        elif hasattr(v, "value"):  # Enum
            out[col.key] = v.value
        else:
            out[col.key] = v
    return out


async def _fetch_table_rows(
    db: AsyncSession,
    model: type,
    account_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Récupère toutes les rows d'une table filtrées par account_id."""
    if not hasattr(model, "account_id"):
        return []
    result = await db.execute(
        select(model).where(model.account_id == account_id)
    )
    rows = result.scalars().all()
    return [_row_to_dict(r) for r in rows]


async def estimate_export_size(
    db: AsyncSession, account_id: uuid.UUID
) -> int:
    """Estime grossièrement la taille du ZIP final (en bytes).

    Heuristique simple : 2 KB par row métier. Documents physiques restent
    hors ZIP (URLs signées 24h), donc l'estimation de la taille du ZIP est
    essentiellement celle de ``data.json``.
    """
    base = 0
    for model in _EXPORT_TABLES.values():
        base += await _table_count(db, model, account_id)
    return base * 2048


async def _table_count(
    db: AsyncSession, model: type, account_id: uuid.UUID
) -> int:
    if not hasattr(model, "account_id"):
        return 0
    from sqlalchemy import func

    result = await db.execute(
        select(func.count())
        .select_from(model)
        .where(model.account_id == account_id)
    )
    return result.scalar() or 0


async def build_export_zip(
    db: AsyncSession, account_id: uuid.UUID, user_id: uuid.UUID
) -> bytes:
    """Construit le fichier ZIP en mémoire et retourne ses bytes."""
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()

    data: dict[str, Any] = {
        "account": _row_to_dict(account) if account else None,
        "_meta": {
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "exported_by_user_id": str(user_id),
            "schema_version": "1.0",
        },
    }
    for key, model in _EXPORT_TABLES.items():
        rows = await _fetch_table_rows(db, model, account_id)
        data[key] = rows

    # audit_log personnel (account_id == account_id, lecture seule)
    audit_q = await db.execute(
        select(AuditLog).where(AuditLog.account_id == account_id)
    )
    data["audit_log_personnel"] = [_row_to_dict(r) for r in audit_q.scalars().all()]

    # Manifeste documents : URLs signées 24h.
    documents_manifest: list[dict[str, Any]] = []
    docs = (
        await db.execute(select(Document).where(Document.account_id == account_id))
    ).scalars().all()
    expires_at = datetime.now(tz=timezone.utc).timestamp() + 86400
    for doc in docs:
        signed_url_token = sign_export_url(
            {"document_id": str(doc.id), "account_id": str(account_id)},
            salt="document-download",
        )
        documents_manifest.append(
            {
                "id": str(doc.id),
                "filename": getattr(doc, "filename", None),
                "mimetype": getattr(doc, "mime_type", None) or getattr(doc, "mimetype", None),
                "size_bytes": getattr(doc, "file_size", None) or getattr(doc, "size_bytes", None),
                "uploaded_at": (
                    doc.created_at.isoformat() if getattr(doc, "created_at", None) else None
                ),
                "signed_url_24h": f"/api/me/data/export/document?token={signed_url_token}",
                "expires_at": datetime.fromtimestamp(
                    expires_at, tz=timezone.utc
                ).isoformat(),
            }
        )

    # Construction ZIP
    buf = io.BytesIO()
    readme = (
        "# Export RGPD ESG Mefali\n\n"
        f"Date d'export : {data['_meta']['exported_at']}\n"
        f"Account ID : {account_id}\n\n"
        "## Structure\n\n"
        "- `data.json` : toutes vos données stockées sous forme JSON exhaustif.\n"
        "  - `account` : métadonnées du compte.\n"
        "  - `users`, `profile`, `projects`, `applications`, `esg_assessments`,\n"
        "    `carbon_assessments`, `credit_scores`, `documents`, `conversations`,\n"
        "    `messages`, `attestations`, `consents`, `audit_log_personnel`.\n"
        "  - `_meta` : informations sur l'export.\n"
        "- `documents/manifest.json` : liste des fichiers documents avec liens\n"
        "  signés temporaires (24h) pour téléchargement.\n\n"
        "## Vos droits RGPD\n\n"
        "- Article 15 : droit d'accès → cet export.\n"
        "- Article 17 : droit à l'effacement → /mes-donnees → Supprimer mon compte.\n"
        "- Article 20 : droit à la portabilité → cet export en JSON structuré.\n\n"
        "Pour toute question : privacy@esg-mefali.com\n"
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", readme)
        zf.writestr(
            "data.json",
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
        )
        zf.writestr(
            "documents/manifest.json",
            json.dumps(documents_manifest, ensure_ascii=False, indent=2),
        )

    return buf.getvalue()


async def log_export_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    size_bytes: int,
    mode: str,
    actor_metadata: dict[str, Any] | None = None,
) -> None:
    """Insère un événement audit_log ``data_exported`` (FR-024)."""
    log = AuditLog(
        user_id=user_id,
        account_id=account_id,
        entity_type="account",
        entity_id=account_id,
        action=AuditAction.create,
        new_value={
            "format": "json",
            "size_bytes": size_bytes,
            "mode": mode,
        },
        source_of_change=AuditSourceOfChange.manual,
        actor_metadata={
            "action_kind": "data_exported",
            **(actor_metadata or {}),
        },
    )
    db.add(log)
    await db.flush()


__all__ = [
    "SYNC_EXPORT_THRESHOLD_BYTES",
    "estimate_export_size",
    "build_export_zip",
    "log_export_event",
]
