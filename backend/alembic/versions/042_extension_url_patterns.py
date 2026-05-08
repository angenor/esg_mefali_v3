"""F24 — Extension Chrome MV3 : url_patterns + scope refresh tokens + audit_source extension.

Revision ID: 042_extension_url_patterns
Revises: 041_templates_and_application_refactor
Create Date: 2026-05-08

Migration F24 minimale :
- Ajoute la colonne ``url_patterns JSONB`` (default ``[]``) sur ``funds``.
- Ajoute la colonne ``url_patterns JSONB`` (default ``[]``) sur ``intermediaries``.
- Ajoute la colonne ``scope VARCHAR(20)`` (default ``'web'``) sur ``refresh_tokens``
  + CHECK constraint applicative ``scope IN ('web','extension')``.
- Ajoute la valeur ``'extension'`` à l'ENUM PostgreSQL ``audit_source``
  (skip SQLite, varchar libre).
- Seed UPSERT ~5 url_patterns prioritaires (best-effort, idempotent).

Round-trip up/down/up validé.

NOTE : ``ALTER TYPE ... ADD VALUE`` est non réversible en PostgreSQL —
la valeur ``'extension'`` reste dans l'enum après rollback (sans impact car
non utilisée si l'application n'est plus déployée).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "042_extension_url_patterns"
down_revision: Union[str, None] = "041_templates_and_application_refactor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_FUND_URL_PATTERNS: dict[str, list[dict]] = {
    "BOAD": [
        {"pattern": r"^https://(www\.)?boad\.org/.*", "scope": "homepage"},
        {"pattern": r"^https://sunref\.boad\.org/.*", "scope": "submission_portal"},
    ],
    "GCF": [
        {"pattern": r"^https://(www\.)?greenclimate\.fund/.*", "scope": "homepage"},
    ],
    "AFD": [
        {"pattern": r"^https://(www\.)?afd\.fr/.*", "scope": "homepage"},
    ],
    "PNUD_AFRICA": [
        {"pattern": r"^https://(www\.)?undp\.org/africa.*", "scope": "homepage"},
    ],
}

SEED_INTERMEDIARY_URL_PATTERNS: dict[str, list[dict]] = {
    "ECOBANK_SUNREF": [
        {"pattern": r"^https://ecobank\.com/.*sunref.*", "scope": "submission_portal"},
    ],
}


def _json_type(is_postgres: bool):
    """Retourne JSONB sur PG, JSON sur SQLite."""
    return postgresql.JSONB() if is_postgres else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. ALTER TYPE audit_source ADD VALUE 'extension' (PG only).
    if is_postgres:
        op.execute(
            "DO $$ BEGIN "
            "ALTER TYPE audit_source ADD VALUE IF NOT EXISTS 'extension'; "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    # 2. funds.url_patterns
    op.add_column(
        "funds",
        sa.Column(
            "url_patterns",
            _json_type(is_postgres),
            nullable=False,
            server_default=sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'"),
        ),
    )

    # 3. intermediaries.url_patterns
    op.add_column(
        "intermediaries",
        sa.Column(
            "url_patterns",
            _json_type(is_postgres),
            nullable=False,
            server_default=sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'"),
        ),
    )

    # 4. refresh_tokens.scope (default 'web' + CHECK).
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "scope",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'web'"),
        ),
    )
    # Backfill explicite (idempotent) pour les anciens tokens.
    op.execute("UPDATE refresh_tokens SET scope = 'web' WHERE scope IS NULL")
    op.create_check_constraint(
        "refresh_tokens_scope_chk",
        "refresh_tokens",
        "scope IN ('web', 'extension')",
    )

    # 5. Seed url_patterns (best-effort, idempotent).
    # On essaie de matcher par organization/name pour les fonds, et par code
    # ou name pour les intermédiaires. Les UPDATE ne touchent que si la
    # colonne url_patterns est encore vide (`[]`) → idempotent.
    import json as _json

    is_empty_clause = (
        "url_patterns::text = '[]'" if is_postgres else "url_patterns = '[]'"
    )
    # En PG, on caste le paramètre sur place avec CAST(:patterns AS jsonb).
    set_value_expr = (
        "CAST(:patterns AS jsonb)" if is_postgres else ":patterns"
    )

    for fund_key, patterns in SEED_FUND_URL_PATTERNS.items():
        # Match large : nom OU organization contient la clé (case-insensitive).
        like_pattern = f"%{fund_key.replace('_', ' ')}%"
        op.execute(
            sa.text(
                f"UPDATE funds SET url_patterns = {set_value_expr} "
                "WHERE (UPPER(organization) LIKE UPPER(:like_pattern) "
                "      OR UPPER(name) LIKE UPPER(:like_pattern)) "
                f"  AND (url_patterns IS NULL OR {is_empty_clause})"
            ).bindparams(
                patterns=_json.dumps(patterns),
                like_pattern=like_pattern,
            )
        )

    for code_key, patterns in SEED_INTERMEDIARY_URL_PATTERNS.items():
        like_pattern = f"%{code_key.replace('_', '%')}%"
        op.execute(
            sa.text(
                f"UPDATE intermediaries SET url_patterns = {set_value_expr} "
                "WHERE (UPPER(code) LIKE UPPER(:like_pattern) "
                "      OR UPPER(name) LIKE UPPER(:like_pattern)) "
                f"  AND (url_patterns IS NULL OR {is_empty_clause})"
            ).bindparams(
                patterns=_json.dumps(patterns),
                like_pattern=like_pattern,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Drop CHECK + colonne scope
    op.drop_constraint(
        "refresh_tokens_scope_chk", "refresh_tokens", type_="check"
    )
    op.drop_column("refresh_tokens", "scope")

    # Drop url_patterns
    op.drop_column("intermediaries", "url_patterns")
    op.drop_column("funds", "url_patterns")

    # NOTE : ne pas DROP la valeur 'extension' de l'ENUM audit_source
    # (PostgreSQL ne le supporte pas nativement, et la valeur reste sans
    # impact car elle n'est plus utilisée après rollback applicatif).
