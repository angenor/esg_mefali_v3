"""Tests contractuels du helper ``get_embeddings_client()`` (F25 T007).

Couvre les 3 cas du contrat (cf. ``contracts/voyage-embeddings-client.md`` §3) :
- Cas 1 : cle valide → instance ``VoyageAIEmbeddings`` avec ``model='voyage-3.5'``.
- Cas 2 : cle absente/vide → ``None`` + ``logger.warning`` emis.
- Cas 3 : package indisponible → ``None`` + ``logger.error`` emis.
"""

from __future__ import annotations

import logging
import os

import pytest
from pydantic import SecretStr


pytestmark = pytest.mark.embeddings


def test_returns_none_when_key_empty(monkeypatch, caplog):
    """Cas 2 : VOYAGE_API_KEY vide → None + warning."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr(""))

    from app.lib.embeddings import get_embeddings_client

    with caplog.at_level(logging.WARNING, logger="app.lib.embeddings"):
        client = get_embeddings_client()

    assert client is None
    assert any(
        "Aucune cle d'embedding configuree" in record.message
        for record in caplog.records
    ), f"Expected warning not found in {[r.message for r in caplog.records]}"


@pytest.mark.skipif(
    not os.environ.get("VOYAGE_API_KEY"),
    reason="VOYAGE_API_KEY absente — test nominal Voyage skipe en CI sans secret.",
)
def test_returns_voyage_client_when_key_present(monkeypatch):
    """Cas 1 : VOYAGE_API_KEY presente → instance _VoyageAIEmbeddingsClient."""
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "voyage_api_key", SecretStr(os.environ["VOYAGE_API_KEY"])
    )

    from app.lib.embeddings import _VoyageAIEmbeddingsClient, get_embeddings_client

    client = get_embeddings_client()
    assert isinstance(client, _VoyageAIEmbeddingsClient)
    assert client.model == "voyage-3.5"


def test_returns_none_when_package_missing(monkeypatch, caplog):
    """Cas 3 : import voyageai echoue → None + error."""
    import builtins

    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr("fake-key-for-test"))

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "voyageai":
            raise ImportError("simule absence du package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from app.lib.embeddings import get_embeddings_client

    with caplog.at_level(logging.ERROR, logger="app.lib.embeddings"):
        client = get_embeddings_client()

    assert client is None
    assert any(
        "voyageai indisponible" in record.message
        for record in caplog.records
    ), f"Expected error log not found in {[r.message for r in caplog.records]}"


def test_helper_does_no_network_call(monkeypatch):
    """Le helper ne doit faire AUCUN appel reseau lors de l'instantiation.

    Invariant de contrat (§7) : le helper ne fait aucun trafic ; seul
    aembed_query/aembed_documents declenche un appel reel.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "voyage_api_key", SecretStr("fake-key-no-network"))

    # Si un appel reseau etait declenche, il echouerait avec la cle factice.
    # On verifie juste que l'instantiation reussit ou retourne None
    # selon disponibilite du package.
    from app.lib.embeddings import get_embeddings_client

    client = get_embeddings_client()
    # Le client peut etre None (package absent) ou une instance — les deux
    # sont valides ; ce qui compte est qu'aucune exception reseau n'a fuit.
    assert client is None or hasattr(client, "aembed_query")
