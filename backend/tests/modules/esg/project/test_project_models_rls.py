"""T010 — Test RLS ENABLE+FORCE sur les 2 tables F047 (PostgreSQL only)."""

from __future__ import annotations

import os

import pytest


_SKIP_REASON = (
    "RLS F047 requiert PostgreSQL réel (set ALEMBIC_TEST_REAL_PG=1)."
)


@pytest.mark.skipif(
    os.environ.get("ALEMBIC_TEST_REAL_PG") != "1",
    reason=_SKIP_REASON,
)
def test_rls_enabled_and_forced_on_pea():
    """Smoke : ENABLE+FORCE RLS activé sur project_esg_assessments."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    async def _run():
        e = create_async_engine(settings.database_url)
        async with e.connect() as c:
            r = await c.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname='project_esg_assessments'"
                )
            )
            row = r.first()
            assert row is not None, "table project_esg_assessments introuvable"
            assert row[0] is True, "RLS ENABLE attendu"
            assert row[1] is True, "RLS FORCE attendu"
        await e.dispose()

    asyncio.run(_run())


@pytest.mark.skipif(
    os.environ.get("ALEMBIC_TEST_REAL_PG") != "1",
    reason=_SKIP_REASON,
)
def test_rls_enabled_and_forced_on_pecr():
    """Smoke : ENABLE+FORCE RLS activé sur project_esg_criterion_responses."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    async def _run():
        e = create_async_engine(settings.database_url)
        async with e.connect() as c:
            r = await c.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname='project_esg_criterion_responses'"
                )
            )
            row = r.first()
            assert row is not None
            assert row[0] is True
            assert row[1] is True
        await e.dispose()

    asyncio.run(_run())
