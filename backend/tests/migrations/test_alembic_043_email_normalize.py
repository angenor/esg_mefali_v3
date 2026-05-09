"""Tests pour la migration 043 — normalisation users.email en lowercase.

Vérifie :
1. Le fichier de migration existe.
2. revision / down_revision corrects.
3. upgrade()/downgrade() définis.
4. Le code détecte les doublons (LOWER + TRIM ... HAVING COUNT > 1).
5. Le code applique l'UPDATE conditionnel.
"""

from __future__ import annotations

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
MIGRATION_PATH = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "043_normalize_users_email_lowercase.py"
)


def test_migration_043_file_exists() -> None:
    assert MIGRATION_PATH.exists(), f"Migration manquante : {MIGRATION_PATH}"


def test_migration_043_revision_id() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "043_normalize_users_email_lowercase"' in content
    assert 'down_revision: Union[str, None] = "042_extension_url_patterns"' in content


def test_migration_043_has_upgrade_downgrade() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content


def test_migration_043_detects_duplicates_before_update() -> None:
    """La migration doit faire un SELECT ... HAVING COUNT > 1 avant l'UPDATE."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "GROUP BY LOWER(TRIM(email))" in content
    assert "HAVING COUNT(*) > 1" in content


def test_migration_043_aborts_on_duplicates() -> None:
    """La migration doit RAISE explicitement si des doublons existent."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "RuntimeError" in content
    assert "ABORT" in content


def test_migration_043_uses_conditional_update() -> None:
    """L'UPDATE doit être conditionnel (ne pas bumper updated_at inutilement)."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "UPDATE users" in content
    assert "LOWER(TRIM(email))" in content
    # Filtre WHERE pour ne toucher que les lignes qui changent réellement.
    assert "WHERE email <> LOWER(TRIM(email))" in content


def test_migration_043_downgrade_is_noop() -> None:
    """downgrade() est un no-op (la casse originale n'est pas restaurable)."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    # Le pass est volontaire — opération destructive.
    assert "def downgrade()" in content
    assert "pass" in content
