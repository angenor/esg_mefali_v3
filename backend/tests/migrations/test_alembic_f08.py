"""Tests Alembic round-trip migration F08 (T009).

Vérifie :
1. La migration ``026_create_attestations`` existe et applique up/down/up sans erreur.
2. La table ``attestations`` est créée avec les colonnes attendues.
3. Les indexes attendus sont présents (sur PostgreSQL).
4. Les CHECK constraints regex sont présents (sur PostgreSQL uniquement).
5. Les policies RLS sont présentes (sur PostgreSQL).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _is_postgres() -> bool:
    """Détecte si l'on cible PostgreSQL via DATABASE_URL."""
    db_url = os.environ.get("DATABASE_URL", "")
    return "postgresql" in db_url or "postgres" in db_url


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    """Helper pour exécuter une commande alembic."""
    return subprocess.run(
        ["alembic", *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_migration_026_file_exists():
    """Le fichier de migration F08 existe."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    assert path.exists(), f"Migration manquante : {path}"


def test_migration_026_revision_id():
    """Le fichier déclare la bonne revision ID et down_revision."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    content = path.read_text(encoding="utf-8")
    assert 'revision: str = "026_create_attestations"' in content
    assert 'down_revision: Union[str, None] = "025_create_projects"' in content


def test_migration_026_has_upgrade_downgrade():
    """Les fonctions upgrade et downgrade sont définies."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    content = path.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content


def test_migration_026_creates_attestations_table():
    """Le code de la migration crée la table ``attestations`` avec ses colonnes."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    content = path.read_text(encoding="utf-8")
    # Toutes les colonnes attendues.
    expected_cols = [
        "account_id",
        "user_id",
        "attestation_type",
        "payload",
        "referential_snapshot",
        "pdf_path",
        "pdf_hash_sha256",
        "signature_ed25519",
        "public_key_id",
        "qr_code_path",
        "valid_from",
        "valid_until",
        "revoked_at",
        "revoked_reason",
        "revoked_by_user_id",
        "verification_url",
        "display_id",
    ]
    for col in expected_cols:
        assert f'"{col}"' in content, f"Colonne manquante dans migration : {col}"


def test_migration_026_declares_indexes():
    """La migration crée les indexes attendus."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    content = path.read_text(encoding="utf-8")
    assert "idx_attestations_account_valid_until" in content
    assert "idx_attestations_user_id" in content
    assert "idx_attestations_revoked_at" in content
    assert "idx_attestations_account_valid_from" in content


def test_migration_026_declares_rls_policies():
    """La migration crée les policies RLS PostgreSQL."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    content = path.read_text(encoding="utf-8")
    assert "pme_access_own_account" in content
    assert "admin_full_access" in content
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "FORCE ROW LEVEL SECURITY" in content


def test_migration_026_declares_check_constraints():
    """La migration déclare les CHECK constraints regex (PostgreSQL only) + portables."""
    path = BACKEND_DIR / "alembic" / "versions" / "026_create_attestations.py"
    content = path.read_text(encoding="utf-8")
    # Portables
    assert "attestation_type_chk" in content
    assert "valid_until_after_from_chk" in content
    assert "revoked_consistency_chk" in content
    # Regex (PG only)
    assert "pdf_hash_sha256_format_chk" in content
    assert "display_id_format_chk" in content
    assert "public_key_id_format_chk" in content


@pytest.mark.skipif(not _is_postgres(), reason="Round-trip nécessite PostgreSQL")
def test_alembic_upgrade_downgrade_upgrade_roundtrip():
    """``alembic upgrade head`` puis ``downgrade -1`` puis ``upgrade head`` OK."""
    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0, f"upgrade head failed:\n{res_up.stderr}"

    res_down = _run_alembic("downgrade", "-1")
    assert res_down.returncode == 0, f"downgrade -1 failed:\n{res_down.stderr}"

    res_up2 = _run_alembic("upgrade", "head")
    assert res_up2.returncode == 0, f"upgrade head (2nd) failed:\n{res_up2.stderr}"
