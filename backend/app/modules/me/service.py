"""F05 — Services backend du module RGPD ``/api/me/*``.

Toutes les fonctions de mutation (grant_consent, revoke_consent,
schedule_deletion, cancel_deletion) journalisent un événement audit_log
explicite avec metadata (ip, user_agent, version) pour traçabilité RGPD
(invariant projet n°3 — audit log append-only).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import AuditAction, AuditSourceOfChange, UserRole
from app.core.security import verify_password as bcrypt_verify
from app.core.url_signer import sign_export_url
from app.models.account import Account
from app.models.application import FundApplication
from app.models.attestation import Attestation
from app.models.audit_log import AuditLog
from app.models.carbon import CarbonAssessment
from app.models.company import CompanyProfile
from app.models.consent import (
    CONSENT_TYPE_DEFAULT_GRANTED,
    CONSENT_TYPE_DEFAULT_LEGAL_BASIS,
    CONSENT_TYPE_DESCRIPTIONS,
    CONSENT_TYPE_LABELS,
    CONSENT_TYPE_VALUES,
    Consent,
)
from app.models.conversation import Conversation
from app.models.credit import CreditScore
from app.models.document import Document
from app.models.esg import ESGAssessment
from app.models.message import Message
from app.models.project import Project
from app.models.user import User
from app.modules.me.schemas import (
    CancelDeletionResponse,
    ConsentGrantResponse,
    ConsentItem,
    ConsentRevokeResponse,
    InventoryCounts,
    InventoryLastModified,
    InventoryResponse,
    ScheduleDeletionResponse,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Inventory
# ----------------------------------------------------------------------


_INVENTORY_TABLES = {
    "profile": (CompanyProfile, "account_id", "updated_at"),
    "projects": (Project, "account_id", "updated_at"),
    "applications": (FundApplication, "account_id", "updated_at"),
    "esg_assessments": (ESGAssessment, "account_id", "updated_at"),
    "carbon_assessments": (CarbonAssessment, "account_id", "updated_at"),
    "credit_scores": (CreditScore, "account_id", "updated_at"),
    "documents": (Document, "account_id", "updated_at"),
    "conversations": (Conversation, "account_id", "updated_at"),
    "messages": (Message, "account_id", "created_at"),
    "attestations": (Attestation, "account_id", "updated_at"),
    "consents": (Consent, "account_id", "updated_at"),
}


async def _count_and_last_modified(
    db: AsyncSession,
    model: type,
    account_id_attr: str,
    last_modified_attr: str,
    account_id: uuid.UUID,
) -> tuple[int, datetime | None]:
    account_id_col = getattr(model, account_id_attr)
    last_modified_col = getattr(model, last_modified_attr, None)
    count_q = select(func.count()).select_from(model).where(account_id_col == account_id)
    count = (await db.execute(count_q)).scalar() or 0
    last_modified: datetime | None = None
    if last_modified_col is not None:
        lm_q = select(func.max(last_modified_col)).where(account_id_col == account_id)
        last_modified = (await db.execute(lm_q)).scalar()
    return count, last_modified


async def get_inventory(
    db: AsyncSession, account_id: uuid.UUID
) -> InventoryResponse:
    """Construit l'inventaire des données de l'account.

    Lance les 11 SELECT COUNT(*) + 11 SELECT MAX(updated_at) en parallèle
    via ``asyncio.gather`` pour répondre p95 < 1 s.
    """
    counts: dict[str, int] = {}
    last_modified: dict[str, datetime | None] = {}
    # NB : asyncio.gather sur asyncpg requiert des sessions distinctes
    # (1 connexion = 1 statement). On séquence pour éviter de saturer le pool ;
    # le coût reste faible (≤ 11 SELECT COUNT(*)).
    for key, (model, fk_attr, lm_attr) in _INVENTORY_TABLES.items():
        try:
            count, lm = await _count_and_last_modified(
                db, model, fk_attr, lm_attr, account_id
            )
            counts[key] = count
            last_modified[key] = lm
        except Exception as exc:  # défensif — table absente / FK manquant
            logger.warning("Inventory: erreur sur %s: %s", key, exc)
            counts[key] = 0
            last_modified[key] = None

    return InventoryResponse(
        counts=InventoryCounts(**counts),
        last_modified=InventoryLastModified(**last_modified),
    )


# ----------------------------------------------------------------------
# Consents
# ----------------------------------------------------------------------


async def list_consents(
    db: AsyncSession, account_id: uuid.UUID
) -> list[ConsentItem]:
    """Retourne la liste des 7 consentements (avec valeurs par défaut si absents).

    Pour chaque type, on cherche le row le plus récent (créé en dernier).
    Si la dernière entrée est révoquée ou inexistante, on retourne ``granted=false``.
    """
    result = await db.execute(
        select(Consent)
        .where(Consent.account_id == account_id)
        .order_by(Consent.consent_type, Consent.created_at.desc())
    )
    rows = result.scalars().all()
    latest_per_type: dict[str, Consent] = {}
    for row in rows:
        if row.consent_type not in latest_per_type:
            latest_per_type[row.consent_type] = row

    items: list[ConsentItem] = []
    for ctype in CONSENT_TYPE_VALUES:
        latest = latest_per_type.get(ctype)
        if latest is not None and latest.revoked_at is None and latest.granted:
            items.append(
                ConsentItem(
                    type=ctype,  # type: ignore[arg-type]
                    granted=True,
                    granted_at=latest.granted_at,
                    revoked_at=None,
                    legal_basis=latest.legal_basis,  # type: ignore[arg-type]
                    version=latest.version,
                    label=CONSENT_TYPE_LABELS[ctype],
                    description=CONSENT_TYPE_DESCRIPTIONS[ctype],
                )
            )
        else:
            # Pas de consentement actif — retourne valeurs par défaut.
            default_granted = CONSENT_TYPE_DEFAULT_GRANTED[ctype]
            default_basis = CONSENT_TYPE_DEFAULT_LEGAL_BASIS[ctype]
            items.append(
                ConsentItem(
                    type=ctype,  # type: ignore[arg-type]
                    granted=False,
                    granted_at=None,
                    revoked_at=latest.revoked_at if latest else None,
                    legal_basis=default_basis,  # type: ignore[arg-type]
                    version=settings.privacy_policy_version,
                    label=CONSENT_TYPE_LABELS[ctype],
                    description=CONSENT_TYPE_DESCRIPTIONS[ctype],
                )
            )
            # Si le défaut est `True` mais que rien n'existe, on signale tout
            # de même `granted=False` à l'API : le service backend devra
            # créer les rows essentiels au moment de l'inscription (cf.
            # ``register`` modifié — section US4).
            if latest is None and default_granted:
                items[-1].granted = True
    return items


def _request_metadata(request: Request | None) -> dict[str, Any]:
    if request is None:
        return {}
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def _audit_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    new_value: dict[str, Any] | None = None,
    actor_metadata: dict[str, Any] | None = None,
) -> None:
    """Insère un événement audit_log custom (action non standard, ex. consent_*).

    Contourne le mixin ``Auditable`` parce que ``Consent`` n'est pas dans la
    whitelist (cf. ``app/core/auditable.py:AUDITABLE_MODELS``). On insère
    directement dans la table avec ``action='create'`` ou ``'update'`` mais en
    documentant l'intention RGPD via ``actor_metadata.action_kind``.
    """
    # Le schéma audit_log impose action ∈ {create,update,delete,view_admin}.
    # On encode l'action F05 (consent_granted, etc.) dans actor_metadata.
    pseudo_action = AuditAction.update if "revoke" in action or "cancel" in action else AuditAction.create
    metadata = dict(actor_metadata or {})
    metadata["action_kind"] = action
    log = AuditLog(
        user_id=user_id,
        account_id=account_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=pseudo_action,
        new_value=new_value,
        source_of_change=AuditSourceOfChange.manual,
        actor_metadata=metadata,
    )
    db.add(log)
    await db.flush()


async def grant_consent(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    consent_type: str,
    request: Request | None = None,
) -> ConsentGrantResponse:
    """Accorde un consentement (idempotent si déjà actif).

    Stratégie :
    - Si un consentement actif existe déjà pour (account_id, type) →
      retourne ses infos sans insertion (idempotent).
    - Sinon insère un nouveau row ``granted=true``, ``revoked_at=NULL``.
    """
    if consent_type not in CONSENT_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Type de consentement invalide",
                "valid_types": list(CONSENT_TYPE_VALUES),
            },
        )
    existing = await db.execute(
        select(Consent).where(
            Consent.account_id == account_id,
            Consent.consent_type == consent_type,
            Consent.revoked_at.is_(None),
            Consent.granted.is_(True),
        )
    )
    active = existing.scalar_one_or_none()
    if active is not None:
        return ConsentGrantResponse(
            type=consent_type,  # type: ignore[arg-type]
            granted=True,
            granted_at=active.granted_at,
            version=active.version,
        )

    metadata = _request_metadata(request)
    metadata["version"] = settings.privacy_policy_version
    legal_basis = CONSENT_TYPE_DEFAULT_LEGAL_BASIS[consent_type]
    consent = Consent(
        account_id=account_id,
        user_id=user_id,
        consent_type=consent_type,
        granted=True,
        legal_basis=legal_basis,
        version=settings.privacy_policy_version,
        metadata_=metadata,
    )
    db.add(consent)
    await db.flush()

    await _audit_event(
        db,
        user_id=user_id,
        account_id=account_id,
        entity_type="consent",
        entity_id=consent.id,
        action="consent_granted",
        new_value={
            "consent_type": consent_type,
            "version": consent.version,
        },
        actor_metadata=metadata,
    )
    return ConsentGrantResponse(
        type=consent_type,  # type: ignore[arg-type]
        granted=True,
        granted_at=consent.granted_at,
        version=consent.version,
    )


async def revoke_consent(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    consent_type: str,
    request: Request | None = None,
) -> ConsentRevokeResponse:
    """Révoque le consentement actif (idempotent si aucun actif)."""
    if consent_type not in CONSENT_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Type de consentement invalide",
                "valid_types": list(CONSENT_TYPE_VALUES),
            },
        )
    existing = await db.execute(
        select(Consent).where(
            Consent.account_id == account_id,
            Consent.consent_type == consent_type,
            Consent.revoked_at.is_(None),
            Consent.granted.is_(True),
        )
    )
    active = existing.scalar_one_or_none()
    now = datetime.now(tz=timezone.utc)
    if active is None:
        return ConsentRevokeResponse(
            type=consent_type,  # type: ignore[arg-type]
            granted=False,
            revoked_at=None,
        )
    active.revoked_at = now
    await db.flush()

    # F18 / SC-008 : marquer les données crédit alternatif dépendantes
    # comme ``unused=True`` + ``purge_after = now + 30j``. Best-effort :
    # une erreur de hook ne doit pas faire échouer la révocation.
    try:
        from app.modules.credit.alternative.revocation_hook import (
            mark_credit_data_unused_on_revoke,
        )

        await mark_credit_data_unused_on_revoke(
            db, account_id=account_id, consent_type=consent_type,
        )
    except Exception:  # pragma: no cover - défense en profondeur
        logger.exception(
            "credit_alternative_revocation_hook_failed",
            extra={"consent_type": consent_type, "account_id": str(account_id)},
        )

    metadata = _request_metadata(request)
    metadata["consent_type"] = consent_type
    metadata["previously_granted_at"] = active.granted_at.isoformat()
    await _audit_event(
        db,
        user_id=user_id,
        account_id=account_id,
        entity_type="consent",
        entity_id=active.id,
        action="consent_revoked",
        new_value={
            "consent_type": consent_type,
            "revoked_at": now.isoformat(),
        },
        actor_metadata=metadata,
    )
    return ConsentRevokeResponse(
        type=consent_type,  # type: ignore[arg-type]
        granted=False,
        revoked_at=now,
    )


async def create_essential_consents_on_register(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    privacy_policy_version: str,
    request: Request | None = None,
) -> None:
    """Crée les 3 consentements essentiels (granted=true) à l'inscription.

    Conformément à la spec : `profile_analysis`, `document_analysis_ai`,
    `credit_certificate_generation` ont base légale ``contract`` et sont
    considérés acceptés par défaut à la création du compte (ils sont
    nécessaires à la fourniture du service).
    """
    metadata = _request_metadata(request)
    metadata["version"] = privacy_policy_version
    metadata["bootstrap"] = "register"
    for ctype, default_granted in CONSENT_TYPE_DEFAULT_GRANTED.items():
        if not default_granted:
            continue
        legal_basis = CONSENT_TYPE_DEFAULT_LEGAL_BASIS[ctype]
        consent = Consent(
            account_id=account_id,
            user_id=user_id,
            consent_type=ctype,
            granted=True,
            legal_basis=legal_basis,
            version=privacy_policy_version,
            metadata_=metadata,
        )
        db.add(consent)
    await db.flush()


# ----------------------------------------------------------------------
# Account deletion
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyPasswordResult:
    verified: bool


async def verify_user_password(
    db: AsyncSession, *, user: User, password: str
) -> bool:
    """Vérifie le mot de passe utilisateur (renvoie True/False).

    Ne mute rien. Le caller décide de logger un audit_log si échec.
    """
    return bcrypt_verify(password, user.hashed_password)


async def schedule_account_deletion(
    db: AsyncSession,
    *,
    user: User,
    password: str,
    confirmation_text: str,
    request: Request | None = None,
) -> ScheduleDeletionResponse:
    """Programme la suppression du compte à J+30 (FR-011).

    Vérifications :
    - Mot de passe correct (sinon 401).
    - Texte de confirmation == "SUPPRIMER" (sinon 422).
    - Owner only (cf. router) — collaborator → 403.
    - Pas déjà programmée (sinon 409).
    """
    if confirmation_text != "SUPPRIMER":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le texte de confirmation doit être 'SUPPRIMER'",
        )
    if not bcrypt_verify(password, user.hashed_password):
        # Audit log d'échec
        if user.account_id is not None:
            await _audit_event(
                db,
                user_id=user.id,
                account_id=user.account_id,
                entity_type="user",
                entity_id=user.id,
                action="account_deletion_attempt_failed",
                new_value={"reason": "invalid_password"},
                actor_metadata=_request_metadata(request),
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect",
        )

    if user.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un administrateur ne peut pas programmer de suppression de compte",
        )

    account = (
        await db.execute(select(Account).where(Account.id == user.account_id))
    ).scalar_one()
    if account.deletion_scheduled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "Une suppression est déjà programmée",
                "deletion_scheduled_at": account.deletion_scheduled_at.isoformat(),
            },
        )

    grace_days = settings.account_deletion_grace_period_days
    scheduled_at = datetime.now(tz=timezone.utc) + timedelta(days=grace_days)
    account.deletion_scheduled_at = scheduled_at
    await db.flush()

    # Lien d'annulation signé
    cancel_token = sign_export_url(
        {"account_id": str(account.id), "action": "cancel_deletion"},
        salt="cancel-deletion",
    )
    cancel_url = (
        f"/api/me/account/cancel-deletion?token={cancel_token}"
    )

    metadata = _request_metadata(request)
    metadata["scheduled_at"] = scheduled_at.isoformat()
    await _audit_event(
        db,
        user_id=user.id,
        account_id=account.id,
        entity_type="account",
        entity_id=account.id,
        action="account_deletion_scheduled",
        new_value={"deletion_scheduled_at": scheduled_at.isoformat()},
        actor_metadata=metadata,
    )

    # Envoi email (stub si SMTP non configuré).
    from app.core.mailer import (
        format_deletion_scheduled_email,
        send_email,
    )

    subject, body = format_deletion_scheduled_email(
        account_name=account.name,
        deletion_date_iso=scheduled_at.strftime("%d/%m/%Y"),
        cancel_url=cancel_url,
    )
    await send_email(to=user.email, subject=subject, body_text=body)

    return ScheduleDeletionResponse(
        deletion_scheduled_at=scheduled_at,
        cancel_url=cancel_url,
        message=(
            f"Suppression programmée. Vous pouvez annuler jusqu'au "
            f"{scheduled_at.strftime('%d/%m/%Y')}."
        ),
    )


async def cancel_account_deletion(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID | None,
    request: Request | None = None,
) -> CancelDeletionResponse:
    """Annule une suppression programmée (FR-012).

    ``user_id`` peut être None lorsque l'annulation se fait via lien email
    signé (mode no-auth). Dans ce cas, on insère l'audit_log avec
    ``user_id`` du premier owner du compte (audit traceable).
    """
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compte introuvable",
        )
    if account.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Compte déjà supprimé, annulation impossible",
        )
    if account.deletion_scheduled_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune suppression programmée pour ce compte",
        )

    account.deletion_scheduled_at = None
    await db.flush()

    if user_id is None:
        # Mode email link : utiliser un user owner pour l'audit
        owner = (
            await db.execute(
                select(User)
                .where(User.account_id == account_id)
                .where(User.role == UserRole.PME.value)
                .limit(1)
            )
        ).scalar_one_or_none()
        user_id_for_log = owner.id if owner else uuid.uuid4()
    else:
        user_id_for_log = user_id

    now = datetime.now(tz=timezone.utc)
    await _audit_event(
        db,
        user_id=user_id_for_log,
        account_id=account_id,
        entity_type="account",
        entity_id=account_id,
        action="account_deletion_cancelled",
        new_value={"cancelled_at": now.isoformat()},
        actor_metadata=_request_metadata(request),
    )

    # Email de confirmation
    from app.core.mailer import (
        format_deletion_cancelled_email,
        send_email,
    )

    subject, body = format_deletion_cancelled_email(account.name)
    # Envoyer à tous les users du compte
    users_res = await db.execute(
        select(User).where(User.account_id == account_id)
    )
    for u in users_res.scalars():
        await send_email(to=u.email, subject=subject, body_text=body)

    return CancelDeletionResponse(
        cancelled_at=now,
        message="Suppression annulée. Votre compte reste actif.",
    )


__all__ = [
    "get_inventory",
    "list_consents",
    "grant_consent",
    "revoke_consent",
    "create_essential_consents_on_register",
    "verify_user_password",
    "schedule_account_deletion",
    "cancel_account_deletion",
]
