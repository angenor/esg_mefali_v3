"""F13 — Cron mensuel : détecte les évolutions de version des référentiels et
crée des reminders F11 pour les PMEs concernées.

Idempotent : 2 exécutions consécutives ne créent pas de doublons.

Usage::

    cd backend && source venv/bin/activate
    python -m scripts.check_referential_versions_evolution

L'orchestrateur externe (cron F19, post-MVP) appelle ce script. En MVP, on
peut déclencher manuellement quand un admin a fait évoluer un référentiel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select

from app.core.database import async_session_factory
from app.models.action_plan import Reminder, ReminderType
from app.models.referential import Referential
from app.models.referential_score import ReferentialScore

logger = logging.getLogger(__name__)


REMINDER_KIND_REFERENTIAL_VERSION_EVOLVED = "referential_version_evolved"


async def check_referential_versions_evolution(
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Parcourt les référentiels actifs et détecte les évolutions de version
    par rapport aux dernières versions connues dans ``referential_scores``.

    Pour chaque PME ayant un score sur un référentiel dont la version a
    évolué, crée une entrée ``reminders`` (F11) avec
    ``type=ReminderType.custom`` et un message JSON encodé contenant
    ``{kind: 'referential_version_evolved', metadata: {...}}``.

    Idempotent : une PME ne reçoit pas plusieurs reminders pour la même
    paire (référentiel, nouvelle version).

    Args:
        dry_run: si True, ne crée pas réellement les reminders.

    Returns:
        Dictionnaire de stats : ``{referentials_checked, reminders_created, skipped}``.
    """
    stats = {"referentials_checked": 0, "reminders_created": 0, "skipped": 0}

    async with async_session_factory() as db:
        # Charger les référentiels publiés
        referentials = (
            await db.execute(
                select(Referential).where(Referential.publication_status == "published")
            )
        ).scalars().all()
        stats["referentials_checked"] = len(referentials)

        for ref in referentials:
            # Pour chaque PME ayant un score sur ce référentiel avec une version
            # antérieure à la version courante du référentiel
            scores = (
                await db.execute(
                    select(ReferentialScore).where(
                        and_(
                            ReferentialScore.referential_id == ref.id,
                            ReferentialScore.superseded_by.is_(None),
                            ReferentialScore.referential_version != ref.version,
                        )
                    )
                )
            ).scalars().all()

            for score in scores:
                # Vérifier qu'on n'a pas déjà créé un reminder pour cette PME et
                # cette nouvelle version (idempotence)
                existing_reminders = (
                    await db.execute(
                        select(Reminder).where(
                            Reminder.account_id == score.account_id,
                            Reminder.type == ReminderType.custom,
                        )
                    )
                ).scalars().all()

                ref_marker = f'"referential_id": "{ref.id}"'
                version_marker = f'"new_version": "{ref.version}"'
                already = any(
                    ref_marker in (r.message or "") and version_marker in (r.message or "")
                    for r in existing_reminders
                )
                if already:
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    stats["reminders_created"] += 1
                    continue

                payload = {
                    "kind": REMINDER_KIND_REFERENTIAL_VERSION_EVOLVED,
                    "metadata": {
                        "referential_id": str(ref.id),
                        "referential_code": ref.code,
                        "old_version": score.referential_version,
                        "new_version": ref.version,
                        "delta_summary": (
                            f"Le référentiel {ref.label} a évolué de la version "
                            f"{score.referential_version} vers {ref.version}."
                        ),
                    },
                }
                # Charger le user via l'assessment (Reminder requiert user_id)
                from app.models.esg import ESGAssessment

                assessment = (
                    await db.execute(
                        select(ESGAssessment).where(
                            ESGAssessment.id == score.assessment_id
                        )
                    )
                ).scalar_one_or_none()
                if assessment is None:
                    continue
                rem = Reminder(
                    user_id=assessment.user_id,
                    account_id=score.account_id,
                    action_item_id=None,
                    type=ReminderType.custom,
                    message=json.dumps(payload, ensure_ascii=False),
                    scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    sent=False,
                )
                db.add(rem)
                stats["reminders_created"] += 1

        if not dry_run:
            await db.commit()

    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    dry_run = "--dry-run" in sys.argv
    stats = asyncio.run(check_referential_versions_evolution(dry_run=dry_run))
    logger.info("F13 cron stats : %s", stats)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
