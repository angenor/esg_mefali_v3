"""Bug fix login email casse — backfill ``users.email`` en minuscules + trim.

Revision ID: 043_normalize_users_email_lowercase
Revises: 042_extension_url_patterns
Create Date: 2026-05-09

Contexte
--------
Le login était sensible à la casse : ``Angenor99@gmail.com`` rejeté avec
« Identifiants invalides », ``angenor99@gmail.com`` accepté. Les schémas
Pydantic ``RegisterRequest`` / ``LoginRequest`` normalisent désormais
l'email en ``.strip().lower()``, mais les comptes existants peuvent encore
contenir des emails en casse mixte. Cette migration les normalise.

Garde-fou — détection de doublons
---------------------------------
Si la normalisation créerait des doublons (deux users dont les emails
diffèrent uniquement par la casse, ex. ``Foo@x.com`` et ``foo@x.com``),
la migration ABORT avec un message explicite. L'opérateur doit alors
résoudre manuellement (fusion / suppression) avant de relancer.

Réversibilité — limitée
-----------------------
``downgrade()`` est un no-op : la casse originale n'est pas conservée
(opération destructive volontaire pour stabiliser la BDD).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "043_normalize_users_email_lowercase"
down_revision: Union[str, None] = "042_extension_url_patterns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Normaliser ``users.email`` en lowercase + trim, après contrôle doublons."""
    bind = op.get_bind()

    # 1. Détecter les collisions potentielles avant modification.
    duplicates = bind.execute(
        sa.text(
            """
            SELECT LOWER(TRIM(email)) AS normalized_email, COUNT(*) AS n
            FROM users
            GROUP BY LOWER(TRIM(email))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if duplicates:
        details = ", ".join(
            f"{row.normalized_email} ({row.n} comptes)" for row in duplicates
        )
        raise RuntimeError(
            "Migration 043 ABORT : la normalisation des emails créerait des "
            "doublons sur la contrainte UNIQUE de users.email. "
            f"Collisions détectées : {details}. "
            "Résolvez manuellement (fusion / suppression du compte en double) "
            "puis relancez la migration."
        )

    # 2. Backfill : LOWER + TRIM uniquement si l'email change vraiment, pour
    #    éviter de bumper updated_at sur la totalité des lignes.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET email = LOWER(TRIM(email))
            WHERE email <> LOWER(TRIM(email))
            """
        )
    )


def downgrade() -> None:
    """No-op : la casse originale n'est pas restaurable (perte de l'info)."""
    pass
