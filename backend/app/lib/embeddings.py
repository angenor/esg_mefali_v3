"""Helper centralise pour la construction du client d'embeddings F25.

Conformite : FR-001 (fournisseur unique), FR-006 (mode degrade), FR-007c
(timeout 10s + max_retries=1).

Cette fonction est l'unique point d'instantiation d'un client d'embeddings
dans le backend. Tous les call sites (memory/financing/documents) DOIVENT
l'utiliser plutot que d'importer directement le SDK voyageai.

Convention de mode degrade : un retour ``None`` signale au caller qu'il
doit basculer en mode degrade (skip de l'indexation, log deja emis ici).
Aucune exception n'est propagee pour les cas attendus (cle absente,
package manquant) — ce sont des etats routiniers en dev/CI.

Implementation : utilise directement le SDK ``voyageai`` officiel
(``voyageai.client_async.AsyncClient``) plutot que ``langchain-voyageai``
qui imposait une downgrade incompatible de ``langchain-core`` (cassait
``langchain-openai.ChatOpenAI`` utilise par OpenRouter — FR-014).
Le wrapper ``_VoyageAIEmbeddingsClient`` expose une API minimaliste
``aembed_query`` / ``aembed_documents`` compatible avec les call sites.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Defaults FR-007c (cf. contracts/voyage-embeddings-client.md §1)
_REQUEST_TIMEOUT_SECONDS: float = 10.0
_MAX_RETRIES: int = 1
_BATCH_SIZE: int = 72  # max recommande pour voyage-3.5


class _VoyageAIEmbeddingsClient:
    """Wrapper minimal autour de ``voyageai.AsyncClient``.

    Expose ``aembed_query`` et ``aembed_documents`` avec la meme signature
    que ``langchain_voyageai.VoyageAIEmbeddings`` pour rester compatible
    avec les call sites memory/financing/documents.

    Pourquoi pas ``langchain-voyageai`` directement ? Le package 0.1.3
    impose ``langchain-core <2.0,>=0.3``, ce qui downgrade le runtime
    et casse ``langchain-openai>=1.1`` (utilise par ChatOpenAI/OpenRouter
    pour le LLM principal — FR-014).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        batch_size: int = _BATCH_SIZE,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        import voyageai

        self.model = model
        self.batch_size = batch_size
        # Le client SYNC fonctionne sous Python 3.14 ; le client ASYNC du SDK
        # voyageai 0.2.3 retourne `APIConnectionError` (bug SDK aiohttp+Py314).
        # On wrappe donc le client SYNC avec `asyncio.to_thread` cote `aembed_*`.
        self._client = voyageai.Client(
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout,
        )

    async def aembed_query(self, text: str) -> list[float]:
        """Embedde une requete utilisateur (input_type='query')."""
        import asyncio

        result = await asyncio.to_thread(
            self._client.embed,
            [text],
            model=self.model,
            input_type="query",
        )
        return result.embeddings[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embedde des documents (input_type='document').

        Batche par ``self.batch_size`` pour respecter la limite Voyage.
        """
        import asyncio

        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            result = await asyncio.to_thread(
                self._client.embed,
                batch,
                model=self.model,
                input_type="document",
            )
            all_embeddings.extend(result.embeddings)
        return all_embeddings


def get_embeddings_client() -> Optional[_VoyageAIEmbeddingsClient]:
    """Retourne un client Voyage configure, ou None.

    Comportement :
    - ``VOYAGE_API_KEY`` non vide → instance ``_VoyageAIEmbeddingsClient``
      configuree (modele ``settings.voyage_model``, timeout 10s,
      max_retries=1, batch_size=72).
    - ``VOYAGE_API_KEY`` vide ou absent → retour ``None`` + ``logger.warning``.
    - Module ``voyageai`` indisponible → retour ``None`` + ``logger.error``.

    Returns:
        Une instance ``_VoyageAIEmbeddingsClient`` ou ``None``.
    """
    from app.core.config import settings

    api_key_value = settings.voyage_api_key.get_secret_value()
    if not api_key_value:
        logger.warning(
            "Aucune cle d'embedding configuree. "
            "Definir VOYAGE_API_KEY dans .env."
        )
        return None

    try:
        import voyageai  # noqa: F401  # validate import
    except ImportError:
        logger.error(
            "Module voyageai indisponible. "
            "Reinstaller backend/requirements.txt."
        )
        return None

    return _VoyageAIEmbeddingsClient(
        api_key=api_key_value,
        model=settings.voyage_model,
        batch_size=_BATCH_SIZE,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        max_retries=_MAX_RETRIES,
    )
