"""F13 — Tests de la migration Alembic ``030_create_referential_scores`` (T007).

Vérifie :
1. Le fichier de migration existe.
2. Il déclare les bonnes ``revision`` et ``down_revision`` (=028_offers_and_enrich).
3. Il définit ``upgrade()`` et ``downgrade()``.
4. Le code crée la table ``referential_scores`` avec les colonnes attendues.
5. Le code définit l'index unique partiel + les indexes secondaires.
6. Le code seed les 5 référentiels MVP (idempotence ON CONFLICT).
7. Le code seed Mefali avec UUID stable.
8. Le code backfille les ``esg_assessments`` finalisés vers ``referential_scores``.
9. ``alembic downgrade -1`` réversible.
10. (PostgreSQL only) Round-trip up/down/up sans erreur.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _is_postgres() -> bool:
    db_url = os.environ.get("DATABASE_URL", "")
    return "postgresql" in db_url or "postgres" in db_url


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["alembic", *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_migration_030_file_exists() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    assert path.exists(), f"Migration manquante : {path}"


def test_migration_030_revision_id() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert 'revision: str = "030_create_referential_scores"' in content
    assert 'down_revision: Union[str, None] = "028_offers_and_enrich"' in content


def test_migration_030_has_upgrade_downgrade() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content


def test_migration_030_creates_referential_scores_table() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")

    expected_columns = [
        "account_id",
        "assessment_id",
        "referential_id",
        "referential_version",
        "superseded_by",
        "overall_score",
        "pillar_scores",
        "coverage_rate",
        "covered_criteria",
        "missing_criteria",
        "gap_to_threshold",
        "eligibility",
        "computed_at",
        "computed_by",
        "computed_request_id",
    ]
    for col in expected_columns:
        assert f'"{col}"' in content, f"Colonne manquante : {col}"


def test_migration_030_defines_partial_unique_index() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "idx_referential_scores_current" in content
    assert "WHERE superseded_by IS NULL" in content


def test_migration_030_defines_secondary_indexes() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "idx_referential_scores_assessment_computed_at" in content
    assert "idx_referential_scores_referential_computed_at" in content
    assert "idx_referential_scores_account_id" in content


def test_migration_030_creates_enum() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "referential_score_computed_by_enum" in content


def test_migration_030_seeds_5_mvp_referentials() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    for code in ("mefali", "gcf", "ifc_ps", "boad_ess", "gri_2021"):
        assert code in content, f"Référentiel MVP manquant : {code}"


def test_migration_030_seeds_mefali_uuid_stable() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    # UUID stable Mefali (cohérent avec MEFALI_REFERENTIAL_UUID dans constants.py)
    assert "0e5f1310-1310-1310-1310-13101310f013" in content


def test_migration_030_idempotent_seed() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "ON CONFLICT (code) DO NOTHING" in content


def test_migration_030_backfill_assessments() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "_backfill_assessments_to_mefali_scores" in content
    assert "INSERT INTO referential_scores" in content
    assert "FROM esg_assessments" in content or "esg_assessments" in content


def test_migration_030_rls_policy() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "FORCE ROW LEVEL SECURITY" in content
    assert "referential_scores_account_isolation" in content


def test_migration_030_check_constraint_coverage_rate() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "ck_referential_scores_coverage_rate_range" in content
    assert "coverage_rate >= 0 AND coverage_rate <= 1" in content


def test_migration_030_extends_reminder_type_enum() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "030_create_referential_scores.py"
    content = path.read_text(encoding="utf-8")
    assert "referential_version_evolved" in content
    assert "ALTER TYPE reminder_type_enum" in content


@pytest.mark.skipif(not _is_postgres(), reason="Round-trip uniquement testé sur PostgreSQL.")
def test_migration_030_roundtrip_pg() -> None:
    """Roundtrip up/down/up sur PostgreSQL doit être idempotent."""
    upgrade1 = _run_alembic("upgrade", "head")
    assert upgrade1.returncode == 0, upgrade1.stderr

    downgrade = _run_alembic("downgrade", "-1")
    assert downgrade.returncode == 0, downgrade.stderr

    upgrade2 = _run_alembic("upgrade", "head")
    assert upgrade2.returncode == 0, upgrade2.stderr
