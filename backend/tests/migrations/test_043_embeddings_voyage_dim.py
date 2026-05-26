"""F25 — Tests de la migration Alembic ``043_embeddings_voyage_dim``.

Verifie :
1. Le fichier de migration existe.
2. Il declare les bonnes ``revision`` et ``down_revision``.
3. Il definit ``upgrade()`` et ``downgrade()``.
4. Les 3 tables vectorielles (message_chunks, document_chunks,
   financing_chunks) sont referencees.
5. Le pattern DROP idx → SET NULL → ALTER → CREATE idx est present.
6. (PostgreSQL only) Round-trip up/down/up sans erreur en < 30 s (SC-004).
7. (PostgreSQL only) Apres upgrade : dim 1024 sur les 3 colonnes.
8. (PostgreSQL only) Apres upgrade : 4 indexes HNSW + partial presents.
9. (PostgreSQL only) RLS sur message_chunks preservee (2 policies).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.embeddings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "043_embeddings_voyage_dim.py"
)


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


def test_migration_043_file_exists() -> None:
    assert MIGRATION_PATH.exists(), f"Migration manquante : {MIGRATION_PATH}"


def test_migration_043_revision_id() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "043_embeddings_voyage_dim"' in content
    assert 'down_revision: Union[str, None] = "042_extension_url_patterns"' in content


def test_migration_043_has_upgrade_downgrade() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content


def test_migration_043_targets_three_tables() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    for table in ("message_chunks", "document_chunks", "financing_chunks"):
        assert table in content, f"Table cible manquante : {table}"


def test_migration_043_uses_vector_1024() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "vector(1024)" in content
    assert "vector(1536)" in content  # downgrade


def test_migration_043_drops_then_creates_hnsw_indexes() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    # Pattern DROP IF EXISTS pour idempotence
    assert "DROP INDEX IF EXISTS ix_message_chunks_embedding_hnsw" in content
    assert "DROP INDEX IF EXISTS idx_message_chunks_pending_embedding" in content
    assert "DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw" in content
    assert "DROP INDEX IF EXISTS ix_financing_chunks_embedding_hnsw" in content
    # CREATE INDEX HNSW
    assert "CREATE INDEX ix_message_chunks_embedding_hnsw" in content
    assert "CREATE INDEX idx_message_chunks_pending_embedding" in content
    assert "CREATE INDEX ix_document_chunks_embedding_hnsw" in content
    assert "CREATE INDEX ix_financing_chunks_embedding_hnsw" in content


def test_migration_043_truncates_embeddings() -> None:
    """FR-009 : ``UPDATE ... SET embedding = NULL`` sur les 3 tables."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "UPDATE message_chunks SET embedding = NULL" in content
    assert "UPDATE document_chunks SET embedding = NULL" in content
    assert "UPDATE financing_chunks SET embedding = NULL" in content


def test_migration_043_uses_hnsw_cosine_ops() -> None:
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "USING hnsw (embedding vector_cosine_ops)" in content
    assert "WITH (m = 16, ef_construction = 64)" in content


def test_migration_043_skips_sqlite() -> None:
    """SQLite : la migration doit etre un no-op."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "is_postgres" in content
    assert "if not is_postgres" in content


def test_migration_043_idempotent_via_atttypmod() -> None:
    """L'ALTER doit etre protege par une lecture pg_attribute.atttypmod."""
    content = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "atttypmod" in content
    assert "_get_vector_dim" in content


@pytest.mark.skipif(not _is_postgres(), reason="Round-trip necessite PostgreSQL")
def test_alembic_upgrade_downgrade_upgrade_roundtrip_043() -> None:
    """``alembic upgrade head`` → ``downgrade -1`` → ``upgrade head`` < 30 s (SC-004)."""
    start = time.monotonic()

    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0, f"upgrade head failed:\n{res_up.stderr}"

    res_down = _run_alembic("downgrade", "-1")
    assert res_down.returncode == 0, f"downgrade -1 failed:\n{res_down.stderr}"

    res_up2 = _run_alembic("upgrade", "head")
    assert res_up2.returncode == 0, f"upgrade head (2nd) failed:\n{res_up2.stderr}"

    elapsed = time.monotonic() - start
    assert elapsed < 30, f"Round-trip a pris {elapsed:.1f}s (>30s, viole SC-004)"


@pytest.mark.skipif(not _is_postgres(), reason="Necessite PostgreSQL")
def test_migration_043_dimensions_after_upgrade(db_session) -> None:
    """Apres upgrade : les 3 colonnes ``embedding`` sont en dim 1024."""
    import sqlalchemy as sa

    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0

    for table in ("message_chunks", "document_chunks", "financing_chunks"):
        result = db_session.execute(
            sa.text(
                """
                SELECT a.atttypmod
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = :table
                  AND a.attname = 'embedding'
                  AND NOT a.attisdropped
                """
            ),
            {"table": table},
        ).scalar()
        assert result == 1024, f"{table}.embedding dim={result} (attendu 1024)"


@pytest.mark.skipif(not _is_postgres(), reason="Necessite PostgreSQL")
def test_migration_043_hnsw_indexes_present(db_session) -> None:
    """Apres upgrade : 4 indexes HNSW/partial presents."""
    import sqlalchemy as sa

    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0

    expected_indexes = {
        "ix_message_chunks_embedding_hnsw",
        "idx_message_chunks_pending_embedding",
        "ix_document_chunks_embedding_hnsw",
        "ix_financing_chunks_embedding_hnsw",
    }
    rows = db_session.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes WHERE indexname = ANY(:names)"
        ),
        {"names": list(expected_indexes)},
    ).fetchall()
    found = {row[0] for row in rows}
    missing = expected_indexes - found
    assert not missing, f"Indexes manquants apres upgrade : {missing}"


@pytest.mark.skipif(not _is_postgres(), reason="Necessite PostgreSQL")
def test_migration_043_preserves_message_chunks_rls(db_session) -> None:
    """RLS sur message_chunks preservee : 2 policies attendues."""
    import sqlalchemy as sa

    res_up = _run_alembic("upgrade", "head")
    assert res_up.returncode == 0

    rows = db_session.execute(
        sa.text(
            "SELECT polname FROM pg_policies "
            "WHERE tablename = 'message_chunks' ORDER BY polname"
        )
    ).fetchall()
    polnames = {row[0] for row in rows}
    assert "admin_full_access" in polnames
    assert "pme_access_own_account" in polnames
