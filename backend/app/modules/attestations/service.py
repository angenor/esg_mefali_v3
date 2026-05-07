"""Service métier Attestations (F08 — T031).

Orchestration de la génération atomique :

1. Charger les scores (CreditScore + EsgAssessment) depuis la base.
2. Calculer ``display_id`` (compteur ``ATT-YYYY-NNNNN`` scopé account+année).
3. Générer le QR code en mémoire.
4. Construire le PDF (1ère passe sans hash).
5. Calculer le SHA-256 du PDF.
6. Construire le payload canonique JSON.
7. Signer Ed25519.
8. Persister la ligne ``Attestation`` + audit log F03.
9. Écrire le PDF + QR sur disque.

API publique async :

- :func:`generate_attestation`
- :func:`revoke_attestation`
- :func:`verify_attestation`
- :func:`list_attestations_for_user`
- :func:`list_all_attestations_admin`
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import source_of_change_scope
from app.core.config import settings
from app.models.attestation import Attestation
from app.modules.attestations.pdf import build_attestation_pdf, write_pdf_to_disk
from app.modules.attestations.qr import generate_qr_code, generate_qr_code_bytes
from app.modules.attestations.schemas import (
    AuthenticVerification,
    ExpiredVerification,
    InvalidVerification,
    RevokedVerification,
)
from app.modules.attestations.signing import (
    build_canonical_payload,
    get_public_key_id,
    sign_payload,
    verify_signature,
)

logger = logging.getLogger(__name__)


UPLOADS_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "attestations"
)
PDF_DIR = UPLOADS_BASE / "pdfs"
QR_DIR = UPLOADS_BASE / "qr"


# ----------------------------------------------------------------------
# Exceptions métier
# ----------------------------------------------------------------------


class AttestationError(Exception):
    """Erreur générique du service Attestations."""


class CreditScoreMissingError(AttestationError):
    """Pas de CreditScore disponible pour générer une attestation."""


class EsgAssessmentMissingError(AttestationError):
    """Pas d'évaluation ESG finalisée disponible."""


class PdfGenerationError(AttestationError):
    """Échec de génération du PDF (WeasyPrint)."""


class AttestationNotFoundError(AttestationError):
    """Attestation introuvable (ou cross-tenant — RLS bloque la lecture)."""


class AttestationAlreadyRevokedError(AttestationError):
    """Tentative de révocation sur une attestation déjà révoquée."""


# ----------------------------------------------------------------------
# Helpers privés
# ----------------------------------------------------------------------


async def _load_credit_score(db: AsyncSession, user_id: uuid.UUID) -> Any | None:
    """Charge le dernier CreditScore de l'utilisateur (None si absent)."""
    from app.models.credit import CreditScore

    result = await db.execute(
        select(CreditScore)
        .where(CreditScore.user_id == user_id)
        .order_by(CreditScore.generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_latest_esg(db: AsyncSession, user_id: uuid.UUID) -> Any | None:
    """Charge la dernière ESGAssessment finalisée (status=completed)."""
    from app.models.esg import ESGAssessment, ESGStatusEnum

    result = await db.execute(
        select(ESGAssessment)
        .where(
            ESGAssessment.user_id == user_id,
            ESGAssessment.status == ESGStatusEnum.completed,
        )
        .order_by(ESGAssessment.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _compute_display_id(
    db: AsyncSession,
    account_id: uuid.UUID,
    year: int,
) -> str:
    """Calcule ``ATT-YYYY-NNNNN`` scopé année (compteur global cross-tenant).

    L'``account_id`` est conservé en paramètre pour traçabilité mais le
    compteur est GLOBAL au système : ``display_id`` est UNIQUE et exposé sur
    le PDF visible publiquement. Un compteur per-tenant introduirait des
    collisions inter-tenants.

    Tolérance courses : si 2 INSERTs concurrents calculent le même
    ``next_n``, la contrainte UNIQUE sur ``display_id`` rejettera la 2e
    insertion. Le service réessaie alors avec ``next_n+1`` (max 5 tentatives).
    """
    result = await db.execute(
        select(func.count(Attestation.id)).where(
            func.extract("year", Attestation.valid_from) == year,
        )
    )
    count = result.scalar() or 0
    next_n = count + 1
    return f"ATT-{year}-{next_n:05d}"


def _build_scores_dict(
    credit_score: Any | None,
    esg: Any | None,
    attestation_type: str,
) -> dict[str, int]:
    """Construit le dict `scores` à partir des modèles ORM chargés."""
    scores: dict[str, int] = {}
    if attestation_type in ("credit_score", "combined") and credit_score is not None:
        scores["combined"] = int(round(float(credit_score.combined_score)))
        scores["solvability"] = int(round(float(credit_score.solvability_score)))
        scores["green_impact"] = int(round(float(credit_score.green_impact_score)))
    if attestation_type in ("esg_assessment", "combined") and esg is not None:
        # ESGAssessment expose un champ ``score_global`` ou ``score`` selon
        # le modèle ; on tente plusieurs champs.
        for attr in ("score_global", "global_score", "score", "esg_global"):
            if hasattr(esg, attr):
                val = getattr(esg, attr)
                if val is not None:
                    scores["esg_global"] = int(round(float(val)))
                    break
    return scores


def _build_referentials_snapshot(
    credit_score: Any | None,
    esg: Any | None,
) -> list[dict[str, Any]]:
    """Snapshot des référentiels appliqués (placeholder simple — F01 enrichira)."""
    refs: list[dict[str, Any]] = [
        {
            "name": "ESG Mefali",
            "version": "1.0",
            "published_at": "2026-01-01",
        }
    ]
    if credit_score is not None and getattr(credit_score, "version", None):
        refs.append({
            "name": "Credit Vert Mefali",
            "version": str(credit_score.version),
            "published_at": (
                credit_score.generated_at.strftime("%Y-%m-%d")
                if getattr(credit_score, "generated_at", None)
                else None
            ),
        })
    return refs


def _build_payload_dict(
    *,
    attestation_type: str,
    scores: dict[str, int],
    referentials: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construit le payload JSONB (snapshot complet)."""
    payload = {
        "attestation_type": attestation_type,
        "scores": scores,
        "referentials": referentials,
    }
    if extra:
        payload.update(extra)
    return payload


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


async def generate_attestation(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    attestation_type: Literal["credit_score", "esg_assessment", "combined"],
    source_of_change: Literal["manual", "llm"] = "manual",
) -> Attestation:
    """Génère une nouvelle attestation pour l'utilisateur.

    :raises CreditScoreMissingError: si attestation_type requiert un CreditScore et qu'il n'existe pas.
    :raises EsgAssessmentMissingError: si attestation_type requiert une ESGAssessment et elle n'existe pas.
    :raises PdfGenerationError: si la génération PDF échoue.
    """
    credit_score = None
    esg = None

    if attestation_type in ("credit_score", "combined"):
        credit_score = await _load_credit_score(db, user_id)
        if credit_score is None:
            raise CreditScoreMissingError(
                "Aucun score de crédit calculé. Veuillez d'abord finaliser le scoring crédit."
            )

    if attestation_type in ("esg_assessment", "combined"):
        esg = await _load_latest_esg(db, user_id)
        if esg is None and attestation_type == "esg_assessment":
            raise EsgAssessmentMissingError(
                "Aucune évaluation ESG finalisée. Veuillez d'abord compléter votre évaluation ESG."
            )

    valid_from = datetime.now(tz=timezone.utc).replace(microsecond=0)
    valid_until = valid_from + timedelta(days=settings.attestation_validity_days)
    year = valid_from.year

    display_id = await _compute_display_id(db, account_id, year)
    scores = _build_scores_dict(credit_score, esg, attestation_type)
    referentials = _build_referentials_snapshot(credit_score, esg)
    payload_dict = _build_payload_dict(
        attestation_type=attestation_type,
        scores=scores,
        referentials=referentials,
    )

    # ID UUID v4 généré côté Python (cohérence si SQLite).
    attestation_id = uuid.uuid4()
    verification_url = (
        f"{settings.attestation_verification_base_url.rstrip('/')}/verify/{attestation_id}"
    )

    # 1. Génère le QR en mémoire.
    qr_bytes = generate_qr_code_bytes(verification_url)

    # 2. Génère le PDF + hash.
    try:
        pdf_bytes, pdf_hash = build_attestation_pdf(
            display_id=display_id,
            attestation_type=attestation_type,
            scores=scores,
            referentials=referentials,
            qr_png_bytes=qr_bytes,
            verification_url=verification_url,
            valid_from=valid_from,
            valid_until=valid_until,
            public_key_id=get_public_key_id(),
        )
    except Exception as exc:
        logger.exception("Échec de génération PDF attestation")
        raise PdfGenerationError(f"Génération PDF échouée : {exc}") from exc

    # 3. Construit le payload canonique + signe.
    canonical = build_canonical_payload(
        attestation_id=attestation_id,
        scores=scores,
        referential_snapshot=referentials,
        pdf_hash_sha256=pdf_hash,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    signature_b64 = sign_payload(canonical)

    # 4. Écrit les fichiers sur disque.
    pdf_path = PDF_DIR / f"{attestation_id}.pdf"
    qr_path = QR_DIR / f"{attestation_id}.png"
    write_pdf_to_disk(pdf_bytes, pdf_path)
    generate_qr_code(verification_url, qr_path)

    # 5. Persiste la ligne (Auditable F03 capture l'INSERT automatiquement).
    attestation = Attestation(
        id=attestation_id,
        account_id=account_id,
        user_id=user_id,
        attestation_type=attestation_type,
        payload=payload_dict,
        referential_snapshot=referentials,
        pdf_path=str(pdf_path),
        pdf_hash_sha256=pdf_hash,
        signature_ed25519=signature_b64,
        public_key_id=get_public_key_id(),
        qr_code_path=str(qr_path),
        valid_from=valid_from,
        valid_until=valid_until,
        verification_url=verification_url,
        display_id=display_id,
    )

    with source_of_change_scope(source_of_change):
        db.add(attestation)
        await db.flush()
        await db.commit()

    await db.refresh(attestation)
    logger.info(
        "Attestation générée : id=%s display=%s account=%s user=%s type=%s",
        attestation.id, display_id, account_id, user_id, attestation_type,
    )
    return attestation


async def revoke_attestation(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    attestation_id: uuid.UUID,
    reason: str,
    actor_role: Literal["pme", "admin"] = "pme",
) -> Attestation:
    """Révoque une attestation existante.

    :raises AttestationNotFoundError: si l'attestation n'existe pas (ou cross-tenant).
    :raises AttestationAlreadyRevokedError: si déjà révoquée.
    """
    query = select(Attestation).where(Attestation.id == attestation_id)
    if actor_role == "pme":
        # PME : restreindre au tenant courant.
        query = query.where(Attestation.account_id == account_id)
    result = await db.execute(query)
    attestation = result.scalar_one_or_none()

    if attestation is None:
        raise AttestationNotFoundError("Attestation introuvable")

    if attestation.revoked_at is not None:
        raise AttestationAlreadyRevokedError(
            "Cette attestation est déjà révoquée"
        )

    attestation.revoked_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    attestation.revoked_reason = reason
    attestation.revoked_by_user_id = user_id

    source = "manual"  # PME et admin = action manuelle (pas LLM, pas import).
    with source_of_change_scope(source):
        await db.commit()

    await db.refresh(attestation)
    logger.info(
        "Attestation révoquée : id=%s actor=%s reason=%s",
        attestation_id, actor_role, reason[:40],
    )
    return attestation


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Force un datetime en UTC aware (assume UTC si naïf — cas SQLite tests)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def verify_attestation(
    db: AsyncSession,
    attestation_id_str: str,
):
    """Vérifie le statut d'une attestation publique.

    Retourne un DTO Pydantic ``VerificationResult`` (discriminated union) :

    - ``InvalidVerification`` si UUID malformé ou inexistant ou signature corrompue.
    - ``RevokedVerification`` si révoquée.
    - ``ExpiredVerification`` si ``valid_until < now()``.
    - ``AuthenticVerification`` si signature valide et non révoquée et non expirée.

    Priorité statuts : ``revoked > expired > authentic``.
    """
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    msg_invalid_fr = (
        "Cet identifiant d'attestation n'existe pas ou la signature est invalide"
    )

    # 1. Parser l'UUID.
    try:
        aid = uuid.UUID(attestation_id_str)
    except (ValueError, TypeError, AttributeError):
        return InvalidVerification(verified_at=now, message=msg_invalid_fr)

    # 2. Charger l'attestation (no_filter — endpoint public).
    result = await db.execute(
        select(Attestation).where(Attestation.id == aid)
    )
    attestation = result.scalar_one_or_none()
    if attestation is None:
        return InvalidVerification(verified_at=now, message=msg_invalid_fr)

    # 3. Reconstruire le canonical payload + vérifier la signature.
    canonical = build_canonical_payload(
        attestation_id=attestation.id,
        scores=_extract_scores_from_payload(attestation.payload),
        referential_snapshot=attestation.referential_snapshot or [],
        pdf_hash_sha256=attestation.pdf_hash_sha256,
        valid_from=attestation.valid_from,
        valid_until=attestation.valid_until,
    )
    if not verify_signature(attestation.signature_ed25519, canonical):
        return InvalidVerification(verified_at=now, message=msg_invalid_fr)

    # 4. Normaliser les datetimes (SQLite peut retourner naïf).
    valid_from_aware = _ensure_aware(attestation.valid_from)
    valid_until_aware = _ensure_aware(attestation.valid_until)
    revoked_at_aware = _ensure_aware(attestation.revoked_at)
    issued_at_aware = _ensure_aware(attestation.created_at)

    # 5. Statut : priorité revoked > expired > authentic.
    base_kwargs = {
        "verified_at": now,
        "attestation_id": attestation.id,
        "display_id": attestation.display_id,
        "attestation_type": attestation.attestation_type,
        "valid_from": valid_from_aware,
        "valid_until": valid_until_aware,
        "issued_at": issued_at_aware,
        "scores": _extract_scores_from_payload(attestation.payload),
        "referentials": attestation.referential_snapshot or [],
        "pdf_hash_sha256": attestation.pdf_hash_sha256,
        "public_key_id": attestation.public_key_id,
    }

    if revoked_at_aware is not None:
        revoked_by_role = await _resolve_revoker_role(db, attestation.revoked_by_user_id)
        return RevokedVerification(
            **base_kwargs,
            message="Cette attestation a été révoquée",
            revoked_at=revoked_at_aware,
            revoked_reason=attestation.revoked_reason or "",
            revoked_by_role=revoked_by_role,
        )

    if valid_until_aware is not None and valid_until_aware < now:
        return ExpiredVerification(
            **base_kwargs,
            message="Cette attestation a expiré",
            expired_since=valid_until_aware,
        )

    return AuthenticVerification(
        **base_kwargs,
        message="Attestation authentique et signée",
    )


def _extract_scores_from_payload(payload: dict[str, Any] | None) -> dict[str, int]:
    """Extrait le dict ``scores`` du payload JSONB (sécurité sur structures historiques)."""
    if not payload:
        return {}
    raw = payload.get("scores") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


async def _resolve_revoker_role(
    db: AsyncSession,
    revoked_by_user_id: uuid.UUID | None,
) -> Literal["pme", "admin"]:
    """Détermine si le revocateur est PME ou admin (sans exposer son nom)."""
    if revoked_by_user_id is None:
        return "pme"
    from app.core.constants import UserRole
    from app.models.user import User

    result = await db.execute(
        select(User.role).where(User.id == revoked_by_user_id)
    )
    role_val = result.scalar_one_or_none()
    if role_val is None:
        return "pme"
    role_str = role_val.value if hasattr(role_val, "value") else str(role_val)
    return "admin" if role_str.upper() == UserRole.ADMIN.value.upper() else "pme"


async def list_attestations_for_user(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Attestation]:
    """Liste les attestations d'un account (PME — RLS limite déjà au tenant)."""
    result = await db.execute(
        select(Attestation)
        .where(Attestation.account_id == account_id)
        .order_by(Attestation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_all_attestations_admin(
    db: AsyncSession,
    *,
    status: str | None = None,
    account_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Attestation]:
    """Liste cross-tenant pour les admins."""
    query = select(Attestation)
    conditions = []
    if account_id is not None:
        conditions.append(Attestation.account_id == account_id)
    # Comparer en naïf-UTC pour compat SQLite (où les TIMESTAMPTZ sont stockés naïvement).
    now_naive = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    if status == "authentic":
        conditions.append(Attestation.revoked_at.is_(None))
        conditions.append(Attestation.valid_until > now_naive)
    elif status == "revoked":
        conditions.append(Attestation.revoked_at.isnot(None))
    elif status == "expired":
        conditions.append(Attestation.revoked_at.is_(None))
        conditions.append(Attestation.valid_until <= now_naive)
    if conditions:
        query = query.where(and_(*conditions))
    query = (
        query.order_by(Attestation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_attestation_for_user(
    db: AsyncSession,
    *,
    account_id: uuid.UUID,
    attestation_id: uuid.UUID,
) -> Optional[Attestation]:
    """Charge une attestation pour le tenant courant (None si inexistante/cross-tenant)."""
    result = await db.execute(
        select(Attestation).where(
            Attestation.id == attestation_id,
            Attestation.account_id == account_id,
        )
    )
    return result.scalar_one_or_none()
