"""F07 — Tests de la migration Alembic ``028_offers_and_enrich``.

Vérifie :
1. Le fichier de migration existe.
2. Il déclare les bonnes ``revision`` et ``down_revision``.
3. Il définit ``upgrade()`` et ``downgrade()``.
4. Le code crée la table ``offers`` avec les colonnes attendues.
5. Le code ajoute les colonnes attendues sur funds/intermediaries/fund_intermediaries/fund_applications.
6. Le code crée les indexes attendus.
7. Le code seed le singleton DIRECT.
8. Le code renomme l'enum fund_type.
9. (PostgreSQL only) Round-trip up/down/up sans erreur.
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


def test_migration_028_file_exists() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    assert path.exists(), f"Migration manquante : {path}"


def test_migration_028_revision_id() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    assert 'revision: str = "028_offers_and_enrich"' in content
    assert 'down_revision: Union[str, None] = "027_consents_and_deletion"' in content


def test_migration_028_has_upgrade_downgrade() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content


def test_migration_028_creates_offers_table() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    expected_cols = [
        "fund_id",
        "intermediary_id",
        "name",
        "accepted_languages",
        "target_sector",
        "effective_criteria",
        "effective_required_documents",
        "effective_fees",
        "effective_processing_time_days_min",
        "effective_processing_time_days_max",
        "effective_disbursement_time_days_min",
        "effective_disbursement_time_days_max",
        "is_active",
        "publication_status",
        "source_id",
        "version",
        "valid_from",
    ]
    for col in expected_cols:
        assert f'"{col}"' in content, f"Colonne manquante : {col}"


def test_migration_028_adds_funds_columns() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    for col in (
        "instruments", "theme", "submission_mode",
        "submission_calendar", "publication_status",
    ):
        assert f'"{col}"' in content, f"Colonne funds manquante : {col}"


def test_migration_028_adds_intermediaries_columns() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    for col in (
        "code", "required_documents", "fees_structured",
        "processing_time_days_min", "processing_time_days_max",
        "disbursement_time_days_min", "disbursement_time_days_max",
        "submission_portal_url", "success_rate",
        "total_funded_volume_amount", "total_funded_volume_currency",
        "publication_status",
    ):
        assert f'"{col}"' in content, f"Colonne intermediaries manquante : {col}"


def test_migration_028_adds_fund_intermediaries_columns() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    for col in (
        "accredited_from", "accredited_to",
        "max_amount_per_fund_amount", "max_amount_per_fund_currency",
        "accreditation_source_id",
    ):
        assert f'"{col}"' in content, f"Colonne fund_intermediaries manquante : {col}"


def test_migration_028_adds_fund_applications_offer_id() -> None:
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    assert '"offer_id"' in content
    assert "fund_applications" in content


def test_migration_028_renames_fund_type_enum() -> None:
    """Renommage enum fund_type (international → multilateral, etc.)."""
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    assert "fund_type_v2_enum" in content
    assert "multilateral" in content
    assert "carbon_marketplace" in content
    # Mapping migrations
    assert "'international' THEN 'multilateral'" in content
    assert "'carbon_market' THEN 'carbon_marketplace'" in content
    assert "'local_bank_green_line' THEN 'private'" in content


def test_migration_028_seeds_direct_singleton() -> None:
    """Le seed du singleton DIRECT est intégré dans la migration."""
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    assert "DIRECT_SINGLETON_CODE" in content
    assert "system://mefali/direct-singleton" in content
    assert "_ensure_direct_singleton" in content


def test_migration_028_declares_unique_constraint() -> None:
    """UNIQUE (fund_id, intermediary_id, version)."""
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    assert "uq_offers_fund_intermediary_version" in content


def test_migration_028_declares_check_constraints() -> None:
    """CHECK constraints sur offers."""
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    for c in (
        "offers_publication_status_chk",
        "offers_processing_time_consistency_chk",
        "offers_disbursement_time_consistency_chk",
        "offers_published_active_chk",
    ):
        assert c in content, f"CHECK manquant : {c}"


def test_migration_028_declares_indexes() -> None:
    """Indexes sur offers (dont publication_active partial)."""
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    for idx in (
        "idx_offers_publication_active",
        "idx_offers_fund_intermediary_valid_to",
        "idx_funds_theme_gin",
        "idx_intermediaries_country",
        "uq_intermediaries_code",
        "idx_fund_intermediaries_accredited_to",
    ):
        assert idx in content, f"Index manquant : {idx}"


def test_migration_028_backfill_logic() -> None:
    """Backfill : fund_applications.offer_id lié."""
    path = BACKEND_DIR / "alembic" / "versions" / "028_offers_and_enrich_fund_intermediary.py"
    content = path.read_text(encoding="utf-8")
    # 2 UPDATE pour le backfill (intermediary_id renseigné OU NULL→DIRECT)
    assert content.count("UPDATE fund_applications") >= 2


@pytest.mark.skipif(not _is_postgres(), reason="Round-trip nécessite PostgreSQL")
def test_alembic_upgrade_downgrade_upgrade_roundtrip_028() -> None:
    """``alembic upgrade head`` puis ``downgrade -1`` puis ``upgrade head`` OK."""
    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0, f"upgrade head failed:\n{res_up.stderr}"
    res_down = _run_alembic("downgrade", "-1")
    assert res_down.returncode == 0, f"downgrade -1 failed:\n{res_down.stderr}"
    res_up2 = _run_alembic("upgrade", "head")
    assert res_up2.returncode == 0, f"upgrade head (2nd) failed:\n{res_up2.stderr}"
