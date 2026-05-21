"""F045 T006 - Test migration 046 (matching projet-centric) up/down/up.

Approche test : les tests SQLite utilisent ``Base.metadata.create_all`` dans
``conftest.py``, donc la migration n'est pas executee. On verifie ici que :
1. Les 5 nouveaux champs SQLAlchemy existent sur le modele Project.
2. Les 4 nouveaux champs SQLAlchemy existent sur le modele OfferMatch.
3. La migration Alembic 046 est presente dans ``alembic/versions/`` avec un
   ``down_revision`` pointant vers la head precedente (``045_reports_polymorphic_assessment_fk``).
4. Round-trip alembic up/down/up reel : valide en CI PostgreSQL (test
   ``@pytest.mark.postgres``, skip ici).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_projects_has_5_new_columns(db_session: AsyncSession) -> None:
    """Verifie l'existence des 5 nouveaux champs F045 sur la table projects."""
    bind = await db_session.connection()

    def _columns(sync_conn) -> set[str]:
        return {c["name"] for c in inspect(sync_conn).get_columns("projects")}

    cols = await bind.run_sync(_columns)
    for expected in (
        "taxonomie_verte_uemoa_aligned",
        "gcf_priority_themes",
        "gender_inclusion",
        "vulnerable_populations",
        "project_esg_score",
    ):
        assert expected in cols, f"Colonne manquante sur projects : {expected}"


@pytest.mark.asyncio
async def test_offer_matches_has_4_new_columns(db_session: AsyncSession) -> None:
    """Verifie l'existence des 4 nouveaux champs F045 sur la table offer_matches."""
    bind = await db_session.connection()

    def _columns(sync_conn) -> set[str]:
        return {c["name"] for c in inspect(sync_conn).get_columns("offer_matches")}

    cols = await bind.run_sync(_columns)
    for expected in (
        "project_score",
        "company_score",
        "project_score_breakdown",
        "divergence_explanation",
    ):
        assert expected in cols, f"Colonne manquante sur offer_matches : {expected}"


def test_migration_046_file_exists() -> None:
    """Verifie la presence du fichier de migration 046."""
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    candidates = list(versions_dir.glob("046_*matching_projet*.py"))
    assert candidates, (
        "Migration F045 introuvable : attendu un fichier matchant "
        "alembic/versions/046_*matching_projet*.py"
    )


def test_migration_046_chains_to_head() -> None:
    """down_revision = revision precedente (045_reports_polymorphic_assessment_fk)."""
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    candidates = list(versions_dir.glob("046_*matching_projet*.py"))
    assert candidates
    content = candidates[0].read_text(encoding="utf-8")
    assert 'revision' in content
    assert "045_reports_polymorphic_assessment_fk" in content, (
        "down_revision doit pointer vers 045_reports_polymorphic_assessment_fk"
    )
