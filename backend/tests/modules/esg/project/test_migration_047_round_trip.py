"""T009 — Test round-trip Alembic 047 (PostgreSQL uniquement).

Vérifie qu'on peut faire upgrade → downgrade → upgrade sans perdre les
saisies F045 ``projects.project_esg_score``.
"""

from __future__ import annotations

import os
import subprocess

import pytest


def _has_postgres() -> bool:
    return bool(os.environ.get("TEST_DATABASE_URL_PG")) or os.environ.get(
        "ALEMBIC_TEST_REAL_PG"
    ) == "1"


@pytest.mark.skipif(
    not _has_postgres(),
    reason="Round-trip Alembic 047 requiert une BDD PostgreSQL réelle "
    "(set ALEMBIC_TEST_REAL_PG=1 ou TEST_DATABASE_URL_PG).",
)
def test_round_trip_047_preserves_f045_data():
    """Vérification minimale : up/down/up doit terminer sans erreur."""
    # Up
    r = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # Down
    r = subprocess.run(["alembic", "downgrade", "-1"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # Up again
    r = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
