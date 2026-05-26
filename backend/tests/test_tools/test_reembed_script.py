"""F25 — Tests contractuels du script ``app.scripts.reembed_all``.

Couvre les 4 cas du contrat (cf. data-model.md §5.5) :
1. ``--dry-run`` ne fait pas de UPDATE et retourne 0.
2. ``--table financing`` ne touche que ``financing_chunks``.
3. ``--limit 5`` traite <= 5 lignes meme si plus disponibles.
4. Sans ``VOYAGE_API_KEY`` → exit code 1 + message stderr.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr


pytestmark = pytest.mark.embeddings


def _run_script(args: list[str]) -> int:
    """Helper : exécute le module ``app.scripts.reembed_all`` avec args."""
    from app.scripts import reembed_all

    saved_argv = sys.argv
    try:
        sys.argv = ["reembed_all", *args]
        return reembed_all.run_cli()
    finally:
        sys.argv = saved_argv


def test_reembed_script_module_exists() -> None:
    """Le module reembed_all doit etre importable."""
    from app.scripts import reembed_all  # noqa: F401

    assert hasattr(reembed_all, "run_cli")


def test_reembed_script_argparse_supports_options() -> None:
    """Le parser CLI doit accepter les 4 options documentees."""
    from app.scripts.reembed_all import _build_parser

    parser = _build_parser()
    # parse argv valide : aucune erreur SystemExit
    ns = parser.parse_args(["--table", "messages", "--limit", "10",
                             "--batch-size", "20", "--dry-run"])
    assert ns.table == "messages"
    assert ns.limit == 10
    assert ns.batch_size == 20
    assert ns.dry_run is True


def test_reembed_script_table_choices() -> None:
    """L'option ``--table`` doit n'accepter que 4 valeurs."""
    from app.scripts.reembed_all import _build_parser

    parser = _build_parser()
    for valid in ("messages", "documents", "financing", "all"):
        ns = parser.parse_args(["--table", valid])
        assert ns.table == valid

    # Valeur invalide : argparse leve SystemExit
    with pytest.raises(SystemExit):
        parser.parse_args(["--table", "invalid"])


def test_reembed_script_default_table_all() -> None:
    """Sans ``--table``, valeur par defaut = ``all``."""
    from app.scripts.reembed_all import _build_parser

    parser = _build_parser()
    ns = parser.parse_args([])
    assert ns.table == "all"
    assert ns.batch_size == 72  # default voyage-3.5
    assert ns.dry_run is False
    assert ns.limit is None


@pytest.mark.asyncio
async def test_reembed_script_exits_1_without_voyage_key(monkeypatch, capsys) -> None:
    """Sans VOYAGE_API_KEY → exit code 1 + message stderr."""
    from app.scripts import reembed_all
    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr(""))

    # Mock get_embeddings_client pour retourner None (cle absente).
    monkeypatch.setattr(
        "app.lib.embeddings.get_embeddings_client",
        lambda: None,
    )

    rc = await reembed_all.main(
        table="all", limit=None, batch_size=72, dry_run=False
    )
    assert rc == 1
    captured = capsys.readouterr()
    err_or_out = (captured.err + captured.out).lower()
    assert (
        "aucune cle d'embedding configuree" in err_or_out
        or "voyage_api_key" in err_or_out
        or "voyage api key" in err_or_out
    ), f"Stderr/stdout n'a pas le message attendu : {captured.err!r} / {captured.out!r}"


@pytest.mark.asyncio
async def test_reembed_script_dry_run_does_no_update(
    monkeypatch, fake_embeddings, db_session
) -> None:
    """``--dry-run`` ne fait pas de UPDATE en BDD et retourne 0."""
    from app.scripts import reembed_all
    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr("fake-key"))

    # Mock le selecteur de lignes pour simuler 3 candidats sur message_chunks
    fake_rows = [(f"id-{i}", f"chunk text {i}") for i in range(3)]
    fake_select = AsyncMock(return_value=fake_rows)
    fake_update = AsyncMock()

    with patch.object(reembed_all, "_select_pending", fake_select), \
         patch.object(reembed_all, "_persist_batch", fake_update):
        rc = await reembed_all.main(
            table="messages", limit=None, batch_size=72, dry_run=True
        )

    assert rc == 0
    # En dry-run, _persist_batch ne doit JAMAIS etre appele
    fake_update.assert_not_called()


@pytest.mark.asyncio
async def test_reembed_script_table_financing_only(
    monkeypatch, fake_embeddings
) -> None:
    """``--table financing`` ne lit que ``financing_chunks``."""
    from app.scripts import reembed_all
    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr("fake-key"))

    fake_select = AsyncMock(return_value=[])
    fake_persist = AsyncMock()

    with patch.object(reembed_all, "_select_pending", fake_select), \
         patch.object(reembed_all, "_persist_batch", fake_persist):
        rc = await reembed_all.main(
            table="financing", limit=None, batch_size=72, dry_run=False
        )

    assert rc == 0
    # _select_pending appele uniquement avec table_name="financing_chunks"
    called_tables = [
        call.args[1] if len(call.args) > 1 else call.kwargs.get("table_name")
        for call in fake_select.await_args_list
    ]
    assert "financing_chunks" in called_tables
    assert "message_chunks" not in called_tables
    assert "document_chunks" not in called_tables


@pytest.mark.asyncio
async def test_reembed_script_limit_caps_rows(
    monkeypatch, fake_embeddings
) -> None:
    """``--limit 5`` cape le SELECT a 5 lignes."""
    from app.scripts import reembed_all
    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr("fake-key"))

    fake_select = AsyncMock(return_value=[])
    fake_persist = AsyncMock()

    with patch.object(reembed_all, "_select_pending", fake_select), \
         patch.object(reembed_all, "_persist_batch", fake_persist):
        await reembed_all.main(
            table="messages", limit=5, batch_size=72, dry_run=True
        )

    # Verifier que limit=5 a bien ete propage au SELECT
    called_with_limits = [
        call.kwargs.get("limit") for call in fake_select.await_args_list
    ]
    assert any(lim == 5 for lim in called_with_limits), (
        f"Limit 5 non propage : {called_with_limits}"
    )
