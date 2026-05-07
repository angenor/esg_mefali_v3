"""F05 — Tests de la migration Alembic ``027_consents_and_deletion``.

Vérifie :
1. Le fichier de migration existe.
2. Il déclare les bonnes ``revision`` et ``down_revision``.
3. Il définit ``upgrade()`` et ``downgrade()``.
4. Le code crée la table ``consents`` avec les colonnes attendues.
5. Le code ajoute les colonnes attendues sur ``accounts``.
6. Le code crée les indexes attendus.
7. Le code crée les ENUMs ``consent_type_enum`` et ``legal_basis_enum``.
8. (PostgreSQL only) Round-trip up/down/up sans erreur.
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
        timeout=120,
    )


def test_migration_027_file_exists() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    assert path.exists(), f"Migration manquante : {path}"


def test_migration_027_revision_id() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    assert 'revision: str = "027_consents_and_deletion"' in content
    assert 'down_revision: Union[str, None] = "026_create_attestations"' in content


def test_migration_027_has_upgrade_downgrade() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content


def test_migration_027_creates_consents_table() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    expected_cols = [
        "account_id",
        "user_id",
        "consent_type",
        "granted",
        "granted_at",
        "revoked_at",
        "legal_basis",
        "version",
        "metadata",
    ]
    for col in expected_cols:
        assert f'"{col}"' in content, f"Colonne manquante : {col}"


def test_migration_027_adds_accounts_columns() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    for col in ("deletion_scheduled_at", "deleted_at", "purge_in_progress"):
        assert f'"{col}"' in content


def test_migration_027_declares_indexes() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    for idx in (
        "idx_consents_active",
        "uq_consents_one_active",
        "idx_accounts_deletion_scheduled",
        "idx_accounts_deleted",
    ):
        assert idx in content, f"Index manquant : {idx}"


def test_migration_027_declares_enums() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    assert "consent_type_enum" in content
    assert "legal_basis_enum" in content
    # Les 7 valeurs documentées
    for value in (
        "profile_analysis",
        "document_analysis_ai",
        "mobile_money_analysis",
        "photos_ia_analysis",
        "public_data_analysis",
        "credit_certificate_generation",
        "product_communications",
    ):
        assert value in content


def test_migration_027_check_constraint() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    assert "chk_consents_revoked_after_granted" in content


def test_migration_027_audit_log_anonymize_function() -> None:
    """La fonction PL/pgSQL ``audit_log_anonymize`` est définie pour la purge RGPD."""
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    assert "audit_log_anonymize" in content
    assert "DISABLE TRIGGER audit_log_no_update" in content


def test_migration_027_alters_audit_log_nullable() -> None:
    """``audit_log.user_id`` et ``account_id`` deviennent nullable pour anonymisation."""
    path = BACKEND_DIR / "alembic" / "versions" / "027_consents_and_account_deletion.py"
    content = path.read_text(encoding="utf-8")
    assert 'alter_column("audit_log", "user_id", nullable=True)' in content
    assert 'alter_column("audit_log", "account_id", nullable=True)' in content


@pytest.mark.skipif(not _is_postgres(), reason="Round-trip nécessite PostgreSQL")
def test_alembic_upgrade_downgrade_upgrade_roundtrip_f05() -> None:
    """``alembic upgrade head`` puis ``downgrade -1`` puis ``upgrade head`` OK."""
    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0, f"upgrade head failed:\n{res_up.stderr}"
    res_down = _run_alembic("downgrade", "-1")
    assert res_down.returncode == 0, f"downgrade -1 failed:\n{res_down.stderr}"
    res_up2 = _run_alembic("upgrade", "head")
    assert res_up2.returncode == 0, f"upgrade head (2nd) failed:\n{res_up2.stderr}"
