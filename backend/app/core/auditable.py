"""Mixin ``Auditable`` + listener global ``before_flush`` (F03).

Toute classe métier qui hérite du marqueur :class:`Auditable` voit ses
mutations capturées automatiquement par le listener
``capture_audit_log_before_flush`` enregistré au chargement du module.

Le listener parcourt :

- ``session.new`` : insertions → ``audit_log.action="create"``,
- ``session.dirty`` : mutations → 1 ``audit_log.action="update"`` par champ
  réellement modifié (via :class:`sqlalchemy.orm.AttributeState.history`),
- ``session.deleted`` : suppressions → ``audit_log.action="delete"``.

Anti-récursion : les insertions de ``AuditLog`` sont ignorées (sinon chaque
écriture du log déclencherait un nouveau log).

Atomicité : les lignes ``audit_log`` sont insérées dans la même session que
la mutation métier. Si la transaction métier rollback, les lignes ``audit_log``
rollback aussi (« on ne logue pas une mutation qui n'a jamais eu lieu »).

Sources / valeurs :

- ``user_id`` est lu depuis la GUC PostgreSQL ``app.current_user_id``
  positionnée par :func:`app.core.rls_session.set_rls_context`. Sur SQLite
  (tests unitaires), on tente d'extraire l'``user_id`` de l'objet métier (champ
  ``user_id`` ou ``actor_id``) ; à défaut on saute l'audit (cas test peu
  courant).
- ``account_id`` provient de l'attribut ``account_id`` de l'instance.
- ``source_of_change`` est lu depuis la ContextVar ``current_source_of_change``.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Session

from app.core.audit_context import get_current_source_of_change
from app.core.constants import AUDIT_VALUE_MAX_BYTES, AuditAction

logger = logging.getLogger(__name__)


class Auditable:
    """Marqueur pour les modèles métier dont les mutations doivent être tracées.

    N'introduit aucune colonne ni méthode : sert exclusivement d'introspection
    via ``isinstance(obj, Auditable)`` dans le listener ``before_flush`` et
    pour le test CI ``test_auditable_models_whitelist_complete``.
    """

    pass


def _get_audit_log_model():
    """Import différé du modèle ``AuditLog`` pour éviter la circular dep.

    ``app.models.company`` (et autres) importent ``Auditable`` ; on ne peut
    donc pas importer ``app.models.audit_log`` au top-level d'``auditable.py``
    sans déclencher une import partielle.
    """
    from app.models.audit_log import AuditLog  # noqa: PLC0415

    return AuditLog


# Whitelist publiée pour tests CI (FR-041 + SC-013).
#
# Note importante : la spec F03 mentionne ``ESGCriterionScore`` mais le projet
# actuel stocke les scores de critères ESG dans ``ESGAssessment.assessment_data``
# (JSON). Toute mutation de critère est donc tracée comme un ``update`` du
# champ ``assessment_data`` sur ``ESGAssessment``. Le nom ``ESGCriterionScore``
# reste documenté ici comme évolution post-MVP (table dédiée éventuelle).
AUDITABLE_MODELS: frozenset[str] = frozenset(
    {
        "CompanyProfile",
        "FundApplication",
        "ESGAssessment",
        "CarbonAssessment",
        "CreditScore",
        "ActionPlan",
        "ActionItem",
        # F06 — Entité Projet Vert
        "Project",
        # F08 — Attestation Vérifiable Ed25519
        "Attestation",
        # F14 — Matching Projet ↔ Offre
        "OfferMatch",
        "MatchAlertSubscription",
        # F18 — Crédit alternatif (Mobile Money + Photos IA + Données publiques)
        "MobileMoneyImport",
        "MobileMoneyTransaction",
        "CreditPhoto",
        "PublicDataSource",
    }
)

# Modèles explicitement exemptés (catalogue F01 + infrastructure + audit_log).
EXEMPT_MODELS: frozenset[str] = frozenset(
    {
        # Catalogue F01
        "Source",
        "Indicator",
        "Criterion",
        "Formula",
        "Threshold",
        "Referential",
        "ReferentialIndicator",
        "EmissionFactor",
        "RequiredDocument",
        "SimulationFactor",
        "UnsourcedFlag",
        # Catalogue financements (admin only)
        "Fund",
        "Intermediary",
        "FundIntermediary",
        "FundMatch",
        "FinancingChunk",
        # F07 — Catalogue offres (admin only). Le cron expiration journalise
        # explicitement via ``app/core/audit_context`` un événement ``import``.
        "Offer",
        # Documents : modélisé comme contenu utilisateur, pas comme entité
        # auditée champ-à-champ (l'utilisateur upload puis lit ; les mutations
        # de contenu Document sont rares — tracées via storage si besoin).
        "Document",
        "DocumentAnalysis",
        "DocumentChunk",
        # CarbonEmissionEntry : détail interne d'un CarbonAssessment, sans
        # account_id propre. Les mutations sont tracées via le snapshot JSONB
        # `assessment_data` de CarbonAssessment.
        "CarbonEmissionEntry",
        # Données de scoring crédit (CreditDataPoint est un detail interne du
        # CreditScore racine)
        "CreditDataPoint",
        # Plan d'action — Reminder/Badge sont auxiliaires, le plan racine
        # (ActionPlan) et ses items (ActionItem) suffisent.
        "Reminder",
        "Badge",
        # Infrastructure
        "User",
        "Account",
        "AccountInvitation",
        "RefreshToken",
        "Conversation",
        "Message",
        "InteractiveQuestion",
        "ToolCallLog",
        "Report",
        # Audit log lui-même : anti-récursion forte.
        "AuditLog",
        # F04 — Référentiel public global (pas d'account_id, lecture publique).
        # Les mutations sont admin-only (cron exchangerate-api.com) et tracées
        # via les logs structurés ERROR/INFO du module currency.
        "ExchangeRate",
        # F12 — Index de cache (chunks d'embedding) : pas une entité métier.
        # Les chunks sont insérés en arrière-plan via un hook après-insertion
        # de Message ; aucune mutation utilisateur directe. La traçabilité de
        # la donnée originale est sur Message (déjà en EXEMPT_MODELS comme
        # contenu conversationnel). Les logs structurés `message_embedded`
        # couvrent l'observabilité (FR-029, SC-007).
        "MessageChunk",
        # F06 — Table de jointure pure projet ↔ document. La traçabilité
        # passe par les mutations de Project (Auditable).
        "ProjectDocument",
        # F05 — Consentements RGPD. Hors mixin générique : les mutations
        # (grant/revoke) sont tracées explicitement par
        # ``app/modules/me/service.py`` avec metadata structurée
        # (``action_kind=consent_granted/revoked``, version, ip, user_agent)
        # via ``_audit_event``. L'introspection champ-à-champ générique du
        # mixin n'apporte pas de valeur ajoutée pour cette entité.
        "Consent",
        # F13 — ReferentialScore : artefact calculé (déterministe à partir de
        # ESGAssessment + Referential), pas une mutation métier au sens strict.
        # Les événements de recalcul (échec, partiel, fallback) sont
        # journalisés explicitement via ``app/core/audit_context`` avec
        # source_of_change='referential_score_recompute' (cf. plan.md F13).
        "ReferentialScore",
        # F23 — Skills (Playbooks Métier). Catalogue admin-only sans
        # account_id : les mutations CRUD sont tracées explicitement par
        # ``app/modules/skills/service.py`` via ``audit_log`` avec source
        # ``admin`` (middleware AdminAuditContextMiddleware). Le mixin
        # générique n'est pas appliqué car la table n'a pas de account_id.
        "Skill",
        # F18 — MobileMoneyAnalysis : artefact recalculé idempotent à partir
        # des MobileMoneyTransaction (déjà Auditable). Les mutations détaillées
        # sont déjà tracées sur les transactions. Le recalcul est journalisé
        # via les logs structurés ``mm_analysis_computed``.
        "MobileMoneyAnalysis",
        # F18 — Catalogue méthodologie scoring crédit (admin only, pas
        # d'account_id, lecture publique pour la page méthodologie).
        "CreditMethodologyFactor",
        # F20 — Bibliothèque Ressources : catalogue admin-only sans
        # account_id. Les mutations CRUD sont tracées via le middleware
        # ``AdminAuditContextMiddleware`` (source_of_change=admin).
        "Resource",
    }
)


# ----------------------------------------------------------------------
# Helpers : sérialisation JSON + troncature 10 KB
# ----------------------------------------------------------------------


def _json_default(obj: Any) -> Any:
    """Sérialise UUID / Decimal / datetime / date / Enum / sets en JSON.

    Fallback final : ``str(obj)``.
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        # Decimal sérialisé en string pour préserver la précision.
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=str)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


def _truncate_value(
    value: Any, max_bytes: int = AUDIT_VALUE_MAX_BYTES
) -> Any:
    """Tronque ``value`` si sa sérialisation JSON dépasse ``max_bytes``.

    Renvoie soit ``value`` inchangée, soit un dict ::

        {
          "_truncated": true,
          "_truncated_size": <bytes original>,
          "_preview": "<premiers 8 KiB de la valeur sérialisée>"
        }

    ``None`` est renvoyé tel quel.
    """
    if value is None:
        return None
    try:
        # Sérialisation compacte (sans espaces) pour mesurer fidèlement
        # l'occupation et préserver le quota 10 KB.
        serialized = json.dumps(
            value,
            default=_json_default,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:  # pragma: no cover — défensif
        logger.warning("Sérialisation JSON impossible pour audit_log: %s", exc)
        return {
            "_truncated": True,
            "_truncated_size": 0,
            "_preview": str(value)[: 8 * 1024],
        }
    size = len(serialized.encode("utf-8"))
    if size <= max_bytes:
        return value
    preview = serialized[: 8 * 1024]
    return {
        "_truncated": True,
        "_truncated_size": size,
        "_preview": preview,
    }


def _to_json_safe(value: Any) -> Any:
    """Convertit ``value`` en structure JSON-serializable.

    Utilisé après :func:`_truncate_value` pour garantir qu'au moment de
    l'INSERT SQL, JSONB reçoit une structure native (dict/list/str/int/etc.).
    """
    if value is None:
        return None
    # Round-trip via json.dumps + json.loads garantit que UUID/Decimal/Enum
    # deviennent des types natifs.
    return json.loads(
        json.dumps(value, default=_json_default, ensure_ascii=False)
    )


# ----------------------------------------------------------------------
# Helpers : extraction des informations de la session
# ----------------------------------------------------------------------


def _get_actor_id_from_session(session: Session) -> uuid.UUID | None:
    """Lit ``app.current_user_id`` (GUC PG) si disponible, None sinon.

    Sur SQLite (tests unitaires), retourne None — l'appelant peut alors
    déduire l'``user_id`` depuis l'objet métier.
    """
    try:
        bind = session.bind
        dialect_name = (
            bind.dialect.name if bind is not None and bind.dialect is not None else ""
        )
        if dialect_name != "postgresql":
            return None
        result = session.execute(
            text("SELECT current_setting('app.current_user_id', true)")
        ).scalar_one_or_none()
        if not result:
            return None
        return uuid.UUID(result)
    except Exception:  # pragma: no cover — défensif
        return None


def _resolve_actor_id(obj: Any, session_actor_id: uuid.UUID | None) -> uuid.UUID | None:
    """Détermine l'``user_id`` à inscrire dans ``audit_log``.

    Préférence : valeur de session (RLS PG). Fallback : champ ``user_id``,
    ``created_by_user_id``, ou ``actor_id`` de l'objet métier.
    """
    if session_actor_id is not None:
        return session_actor_id
    for attr in ("user_id", "created_by_user_id", "actor_id"):
        candidate = getattr(obj, attr, None)
        if isinstance(candidate, uuid.UUID):
            return candidate
        if isinstance(candidate, str):
            try:
                return uuid.UUID(candidate)
            except ValueError:
                continue
    return None


def _resolve_account_id(obj: Any) -> uuid.UUID | None:
    """Récupère l'``account_id`` de l'instance auditable, ou None."""
    candidate = getattr(obj, "account_id", None)
    if isinstance(candidate, uuid.UUID):
        return candidate
    if isinstance(candidate, str):
        try:
            return uuid.UUID(candidate)
        except ValueError:
            return None
    return None


def _entity_type_name(obj: Any) -> str:
    """Nom de table de l'instance (ex. ``"company_profiles"``).

    Préférence : ``__tablename__`` (forme déjà indexée). Fallback : nom de
    classe lower-snake.
    """
    table = getattr(obj, "__tablename__", None)
    if isinstance(table, str) and table:
        return table
    return obj.__class__.__name__


def _entity_id(obj: Any) -> uuid.UUID | None:
    """UUID de l'instance (champ ``id``).

    Si le `id` n'est pas encore matérialisé (cas typique pour ``session.new``
    avant que SQLAlchemy n'évalue les defaults Python), on l'évalue nous-même
    via le `column_default.arg()` du mapper, et on l'assigne en retour à
    l'instance pour cohérence.
    """
    candidate = getattr(obj, "id", None)
    if isinstance(candidate, uuid.UUID):
        return candidate
    if isinstance(candidate, str):
        try:
            return uuid.UUID(candidate)
        except ValueError:
            return None
    # id non matérialisé : tenter de l'évaluer via le default mapper
    try:
        mapper = inspect(obj.__class__)
        id_attr = mapper.column_attrs.get("id")
        if id_attr is None:
            return None
        col = id_attr.columns[0]
        if col.default is not None and col.default.is_callable:
            new_id = col.default.arg(None)
            if isinstance(new_id, uuid.UUID):
                # Assigner en retour à l'instance pour qu'INSERT utilise
                # la même valeur que celle inscrite dans audit_log.
                obj.id = new_id
                return new_id
    except Exception:  # pragma: no cover — défensif
        return None
    return None


def _column_attribute_keys(obj: Any) -> list[str]:
    """Liste des attributs colonne (exclut les relations)."""
    mapper = inspect(obj.__class__)
    return [col_attr.key for col_attr in mapper.column_attrs]


def _snapshot_columns(obj: Any) -> dict[str, Any]:
    """Snapshot ``{field: valeur}`` des colonnes (pour create/delete)."""
    snap: dict[str, Any] = {}
    for key in _column_attribute_keys(obj):
        snap[key] = getattr(obj, key, None)
    return snap


# ----------------------------------------------------------------------
# Helpers : construction des lignes audit_log
# ----------------------------------------------------------------------


def _common_row(
    obj: Any,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
    action: AuditAction,
) -> dict[str, Any]:
    """Champs communs à toutes les lignes audit_log."""
    return {
        "id": uuid.uuid4(),
        "user_id": actor_id,
        "account_id": account_id,
        "entity_type": _entity_type_name(obj),
        "entity_id": _entity_id(obj),
        "action": action.value,
        "source_of_change": source,
    }


def _make_create_row(
    obj: Any,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
) -> dict[str, Any]:
    snap = _snapshot_columns(obj)
    new_value = _to_json_safe(_truncate_value(snap))
    row = _common_row(obj, actor_id, account_id, source, AuditAction.create)
    row.update(
        {
            "field": None,
            "old_value": None,
            "new_value": new_value,
            "actor_metadata": None,
        }
    )
    return row


def _make_delete_row(
    obj: Any,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
) -> dict[str, Any]:
    snap = _snapshot_columns(obj)
    old_value = _to_json_safe(_truncate_value(snap))
    row = _common_row(obj, actor_id, account_id, source, AuditAction.delete)
    row.update(
        {
            "field": None,
            "old_value": old_value,
            "new_value": None,
            "actor_metadata": None,
        }
    )
    return row


def _make_update_rows(
    obj: Any,
    actor_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
) -> list[dict[str, Any]]:
    """Retourne 1 ligne audit_log par champ effectivement modifié."""
    rows: list[dict[str, Any]] = []
    state = inspect(obj)
    for key in _column_attribute_keys(obj):
        attr_state = state.attrs[key]
        history = attr_state.history
        if not history.has_changes():
            continue
        # ``history.deleted`` peut être [PASSIVE_NO_RESULT] si le champ n'a
        # jamais été chargé. ``history.added`` contient la nouvelle valeur.
        old_raw = history.deleted[0] if history.deleted else None
        new_raw = history.added[0] if history.added else None
        old_value = _to_json_safe(_truncate_value(old_raw))
        new_value = _to_json_safe(_truncate_value(new_raw))
        row = _common_row(obj, actor_id, account_id, source, AuditAction.update)
        row.update(
            {
                "field": key,
                "old_value": old_value,
                "new_value": new_value,
                "actor_metadata": None,
            }
        )
        rows.append(row)
    return rows


# ----------------------------------------------------------------------
# Listener global before_flush
# ----------------------------------------------------------------------


@event.listens_for(Session, "before_flush")
def capture_audit_log_before_flush(
    session: Session, flush_context: Any, instances: Any
) -> None:
    """Capture les mutations sur les instances ``Auditable`` et insère les
    lignes ``audit_log`` correspondantes dans la même session.
    """
    # Import différé pour éviter une dépendance circulaire à l'import-time
    # (app.models.company importe Auditable depuis ce module).
    AuditLog = _get_audit_log_model()

    # Récupération du contexte (lu depuis Python ContextVars + GUC PG)
    source = get_current_source_of_change()
    session_actor_id = _get_actor_id_from_session(session)

    rows: list[dict[str, Any]] = []

    # 1. Insertions
    for obj in list(session.new):
        if isinstance(obj, AuditLog):
            continue  # anti-récursion
        if not isinstance(obj, Auditable):
            continue
        actor_id = _resolve_actor_id(obj, session_actor_id)
        account_id = _resolve_account_id(obj)
        if actor_id is None or account_id is None:
            # Sans acteur ou sans account_id, on ne peut pas tracer (FK NOT NULL).
            # Cas typique : tests legacy avant F02. On loggue en debug et on saute.
            logger.debug(
                "Audit ignoré (create) : actor_id=%s, account_id=%s, model=%s",
                actor_id,
                account_id,
                obj.__class__.__name__,
            )
            continue
        rows.append(_make_create_row(obj, actor_id, account_id, source))

    # 2. Mutations
    for obj in list(session.dirty):
        if isinstance(obj, AuditLog):
            continue
        if not isinstance(obj, Auditable):
            continue
        # `dirty` peut contenir des objets sans modification réelle (peuvent
        # être attachés via `merge`); on filtre en aval via has_changes()
        actor_id = _resolve_actor_id(obj, session_actor_id)
        account_id = _resolve_account_id(obj)
        if actor_id is None or account_id is None:
            logger.debug(
                "Audit ignoré (update) : actor_id=%s, account_id=%s, model=%s",
                actor_id,
                account_id,
                obj.__class__.__name__,
            )
            continue
        rows.extend(_make_update_rows(obj, actor_id, account_id, source))

    # 3. Suppressions
    for obj in list(session.deleted):
        if isinstance(obj, AuditLog):
            continue
        if not isinstance(obj, Auditable):
            continue
        actor_id = _resolve_actor_id(obj, session_actor_id)
        account_id = _resolve_account_id(obj)
        if actor_id is None or account_id is None:
            logger.debug(
                "Audit ignoré (delete) : actor_id=%s, account_id=%s, model=%s",
                actor_id,
                account_id,
                obj.__class__.__name__,
            )
            continue
        rows.append(_make_delete_row(obj, actor_id, account_id, source))

    if not rows:
        return

    # Insertion en bulk via session.execute(insert(AuditLog), rows).
    from sqlalchemy import insert

    session.execute(insert(AuditLog), rows)
