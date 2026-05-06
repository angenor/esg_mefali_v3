"""Helper de configuration de la Row-Level Security (F02).

À chaque requête authentifiée, l'application doit positionner les variables
de session PostgreSQL ``app.current_account_id``, ``app.current_role`` et
``app.current_user_id`` AVANT d'exécuter toute requête métier. Les policies
RLS PostgreSQL (cf. migration 019) filtrent ensuite les lignes accessibles
en fonction de ces variables.

En l'absence de ces variables (cas d'erreur applicative), les policies RLS
retournent 0 ligne (« fail-closed ») — aucune fuite ne peut survenir.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def set_rls_context(
    session: AsyncSession,
    account_id: uuid.UUID | None,
    role: str,
    user_id: uuid.UUID,
) -> None:
    """Positionne les variables de session PostgreSQL pour la RLS.

    - ``app.current_account_id`` : UUID du compte courant (vide si Admin).
    - ``app.current_role`` : ``'PME'`` ou ``'ADMIN'``.
    - ``app.current_user_id`` : UUID de l'utilisateur courant.

    Les SET LOCAL n'ont d'effet que pour la transaction courante (nettoyage
    automatique en fin de transaction, sécurisé pour pool de connexions).

    Sur SQLite (utilisé en tests unitaires), ces commandes sont silencieusement
    ignorées via un ``try/except`` car SQLite n'a pas de variables de session.
    """
    bind = session.bind
    dialect_name = (
        bind.dialect.name if bind is not None and bind.dialect is not None else ""
    )
    if dialect_name == "sqlite":
        # Aucun support RLS / GUC en SQLite : noop.
        return

    aid_str = str(account_id) if account_id is not None else ""
    role_str = role or ""
    uid_str = str(user_id) if user_id is not None else ""

    try:
        # PostgreSQL n'autorise pas l'usage de paramètres dans les SET, on
        # utilise set_config() qui prend des valeurs en paramètres bindés.
        await session.execute(
            text("SELECT set_config('app.current_account_id', :v, true)"),
            {"v": aid_str},
        )
        await session.execute(
            text("SELECT set_config('app.current_role', :v, true)"),
            {"v": role_str},
        )
        await session.execute(
            text("SELECT set_config('app.current_user_id', :v, true)"),
            {"v": uid_str},
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Impossible de positionner le contexte RLS : %s", exc)
        raise
