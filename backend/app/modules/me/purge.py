"""F05 — Purge effective d'un compte programmé pour suppression (Art. 17 RGPD).

Le job cron ``scripts/purge_scheduled_deletions.py`` invoque
:func:`purge_account_data` pour chaque account dont
``deletion_scheduled_at < now()`` et ``deleted_at IS NULL``.

Étapes (idempotentes — le flag ``purge_in_progress`` permet de reprendre
après interruption) :

1. Verrouiller le compte (``purge_in_progress=true``).
2. Révoquer une éventuelle attestation crédit active
   (``status='revoked', revoked_reason='account_deleted'``).
3. Lister les fichiers à supprimer (paths sous ``/uploads/{account_id}/``).
4. Supprimer en cascade les rows métier (cascade FK depuis ``accounts``).
5. Anonymiser ``audit_log`` via UPDATE en place (clarification spec Q3) :
   ``user_id=NULL, account_id=NULL, payload filtré``.
6. Révoquer les refresh tokens.
7. Supprimer les fichiers physiques sous ``/uploads/{account_id}/``.
8. Marquer ``deleted_at=now()``, ``purge_in_progress=false``.
9. Envoyer email de confirmation finale.
10. Insérer audit_log ``account_purged`` (anonymisé immédiatement).
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction, AuditSourceOfChange
from app.models.account import Account
from app.models.application import FundApplication
from app.models.attestation import Attestation
from app.models.audit_log import AuditLog
from app.models.carbon import CarbonAssessment, CarbonEmissionEntry
from app.models.company import CompanyProfile
from app.models.consent import Consent
from app.models.conversation import Conversation
from app.models.credit import CreditDataPoint, CreditScore
from app.models.document import Document, DocumentAnalysis, DocumentChunk
from app.models.esg import ESGAssessment
from app.models.message import Message
from app.models.project import Project
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)


# Liste des champs PII whitelistés à retirer des payloads audit_log lors de
# l'anonymisation. Toute clé matchant exactement OU se terminant par un suffixe
# whitelisté (_email, _phone, _name, etc.) est supprimée.
PII_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "phone",
        "mobile_number",
        "name",
        "first_name",
        "last_name",
        "full_name",
        "address",
        "street",
        "city",
        "country",
        "ip",
        "ip_address",
        "user_agent",
        "bank_account",
        "bank_iban",
        "mobile_money_number",
        "signature",
        "signed_by",
        "gps_lat",
        "gps_lng",
    }
)

PII_SUFFIXES: tuple[str, ...] = (
    "_email",
    "_phone",
    "_name",
    "_address",
    "_ip",
    "_user_agent",
)


def anonymize_payload(payload: Any) -> Any:
    """Retire récursivement les clés PII whitelistées du payload.

    Conserve les autres champs intacts (entity_type, action, etc.).
    """
    if payload is None:
        return None
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if key in PII_FIELDS:
                continue
            if any(key.endswith(suf) for suf in PII_SUFFIXES):
                continue
            out[key] = anonymize_payload(value)
        return out
    if isinstance(payload, list):
        return [anonymize_payload(item) for item in payload]
    return payload


@dataclass
class PurgeResult:
    account_id: uuid.UUID
    deleted_at: datetime
    rows_deleted: dict[str, int] = field(default_factory=dict)
    audit_log_anonymized: int = 0
    files_removed: int = 0
    email_sent: bool = False


def _delete_uploads_directory(account_id: uuid.UUID) -> int:
    """Supprime le répertoire ``/uploads/{account_id}/`` et retourne le nombre de fichiers."""
    base_dirs = [
        Path("uploads") / str(account_id),
        Path("/uploads") / str(account_id),
    ]
    removed = 0
    for base in base_dirs:
        if base.exists() and base.is_dir():
            for root, _, files in os.walk(base):
                removed += len(files)
            shutil.rmtree(base, ignore_errors=True)
    return removed


async def _revoke_active_attestations(
    db: AsyncSession, account_id: uuid.UUID
) -> None:
    """Avant la cascade, révoquer les attestations actives (FR-025)."""
    now = datetime.now(tz=timezone.utc)
    await db.execute(
        update(Attestation)
        .where(Attestation.account_id == account_id)
        .where(Attestation.revoked_at.is_(None))
        .values(
            revoked_at=now,
            revoked_reason="account_deleted",
        )
    )


async def _fetch_document_paths(
    db: AsyncSession, account_id: uuid.UUID
) -> list[str]:
    """Récupère les paths physiques des documents avant cascade."""
    result = await db.execute(
        select(Document.storage_path).where(Document.account_id == account_id)
    )
    return [p for p in result.scalars().all() if p]


async def _delete_cascade(
    db: AsyncSession, account_id: uuid.UUID
) -> dict[str, int]:
    """Suppression manuelle table par table (les FK existantes ne sont pas
    toutes ON DELETE CASCADE).

    Retourne un compteur par table pour traçabilité.
    """
    counts: dict[str, int] = {}

    # 1. Children of metric tables (ordre dépendances)
    res = await db.execute(
        delete(CarbonEmissionEntry).where(
            CarbonEmissionEntry.assessment_id.in_(
                select(CarbonAssessment.id).where(
                    CarbonAssessment.account_id == account_id
                )
            )
        )
    )
    counts["carbon_emission_entries"] = res.rowcount or 0

    res = await db.execute(
        delete(CreditDataPoint).where(
            CreditDataPoint.credit_score_id.in_(
                select(CreditScore.id).where(
                    CreditScore.account_id == account_id
                )
            )
        )
    )
    counts["credit_data_points"] = res.rowcount or 0

    res = await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id.in_(
                select(Document.id).where(Document.account_id == account_id)
            )
        )
    )
    counts["document_chunks"] = res.rowcount or 0

    res = await db.execute(
        delete(DocumentAnalysis).where(
            DocumentAnalysis.document_id.in_(
                select(Document.id).where(Document.account_id == account_id)
            )
        )
    )
    counts["document_analyses"] = res.rowcount or 0

    # 2. Tables principales par account_id
    for model in [
        Consent,
        Attestation,
        FundApplication,
        ESGAssessment,
        CarbonAssessment,
        CreditScore,
        Document,
        Message,
        Conversation,
        Project,
        CompanyProfile,
    ]:
        if not hasattr(model, "account_id"):
            continue
        res = await db.execute(
            delete(model).where(model.account_id == account_id)
        )
        counts[model.__tablename__] = res.rowcount or 0

    # 3. Refresh tokens (par user_id liés au compte)
    res = await db.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id.in_(
                select(User.id).where(User.account_id == account_id)
            )
        )
    )
    counts["refresh_tokens"] = res.rowcount or 0

    # 4. Users du compte (FK ON DELETE RESTRICT vers accounts) — supprimer ici.
    res = await db.execute(
        delete(User).where(User.account_id == account_id)
    )
    counts["users"] = res.rowcount or 0

    return counts


async def _anonymize_audit_log(
    db: AsyncSession, account_id: uuid.UUID
) -> int:
    """Anonymise les rows audit_log liées au compte (UPDATE en place)."""
    bind = db.get_bind() if hasattr(db, "get_bind") else None
    is_postgres = (
        bind is not None
        and getattr(bind, "dialect", None) is not None
        and bind.dialect.name == "postgresql"
    )
    if is_postgres:
        # Sur PostgreSQL : utilise la fonction PL/pgSQL audit_log_anonymize
        # qui désactive temporairement le trigger no_update.
        result = await db.execute(
            text("SELECT audit_log_anonymize(:acc_id, :pii_fields)"),
            {
                "acc_id": str(account_id),
                "pii_fields": list(PII_FIELDS),
            },
        )
        return int(result.scalar() or 0)
    # Sur SQLite (tests) : pas de trigger, UPDATE direct.
    rows = (
        await db.execute(
            select(AuditLog).where(AuditLog.account_id == account_id)
        )
    ).scalars().all()
    count = 0
    for row in rows:
        # Note: attention au listener Auditable global (before_flush) qui
        # ignore AuditLog (anti-récursion). On peut donc UPDATE directement.
        row.user_id = None
        row.account_id = None
        if isinstance(row.new_value, dict):
            row.new_value = anonymize_payload(row.new_value)
        if isinstance(row.old_value, dict):
            row.old_value = anonymize_payload(row.old_value)
        if isinstance(row.actor_metadata, dict):
            row.actor_metadata = anonymize_payload(row.actor_metadata)
        count += 1
    await db.flush()
    return count


async def purge_account_data(
    db: AsyncSession, account_id: uuid.UUID
) -> PurgeResult:
    """Purge effective des données d'un compte (idempotent).

    Args:
        db: session async.
        account_id: UUID du compte à purger.

    Returns:
        PurgeResult avec les compteurs et la date de purge.

    Raises:
        ValueError: si le compte n'existe pas ou si ``deleted_at`` est déjà
            positionné (idempotent — on retourne sans erreur dans ce cas).
    """
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise ValueError(f"Compte introuvable : {account_id}")
    if account.deleted_at is not None:
        # Déjà purgé → idempotent
        return PurgeResult(
            account_id=account_id,
            deleted_at=account.deleted_at,
            email_sent=False,
        )

    # Capture infos avant purge pour l'email final
    primary_user = (
        await db.execute(
            select(User).where(User.account_id == account_id).limit(1)
        )
    ).scalar_one_or_none()
    former_email = primary_user.email if primary_user else None
    account_name = account.name

    # 1. Lock idempotent
    account.purge_in_progress = True
    await db.flush()

    # 2. Révocation attestations
    await _revoke_active_attestations(db, account_id)

    # 3. Récupérer paths fichiers
    document_paths = await _fetch_document_paths(db, account_id)

    # 4. Cascade
    rows_deleted = await _delete_cascade(db, account_id)

    # 5. Anonymisation audit_log
    audit_anonymized = await _anonymize_audit_log(db, account_id)

    # 6. Suppression fichiers physiques
    files_removed = 0
    for path in document_paths:
        try:
            Path(path).unlink(missing_ok=True)
            files_removed += 1
        except Exception:  # défensif
            pass
    files_removed += _delete_uploads_directory(account_id)

    # 7. Marquer deleted_at
    now = datetime.now(tz=timezone.utc)
    account.deleted_at = now
    account.purge_in_progress = False
    account.is_active = False
    await db.flush()

    # 8. Email final (best-effort)
    email_sent = False
    if former_email:
        from app.core.mailer import (
            format_deletion_completed_email,
            send_email,
        )

        subject, body = format_deletion_completed_email(account_name)
        email_sent = await send_email(
            to=former_email, subject=subject, body_text=body
        )

    # 9. Audit log final (anonymisé immédiatement après insertion).
    # Étant donné que l'audit_log accepte désormais user_id NULL et
    # account_id NULL (migration 027), on insère directement avec NULL.
    final_log = AuditLog(
        user_id=None,
        account_id=None,
        entity_type="account",
        entity_id=account_id,
        action=AuditAction.delete,
        source_of_change=AuditSourceOfChange.manual,
        actor_metadata={"action_kind": "account_purged", "purged_at": now.isoformat()},
    )
    db.add(final_log)
    await db.flush()

    return PurgeResult(
        account_id=account_id,
        deleted_at=now,
        rows_deleted=rows_deleted,
        audit_log_anonymized=audit_anonymized,
        files_removed=files_removed,
        email_sent=email_sent,
    )


__all__ = [
    "PII_FIELDS",
    "anonymize_payload",
    "purge_account_data",
    "PurgeResult",
]
