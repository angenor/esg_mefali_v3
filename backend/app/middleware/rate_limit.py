"""Rate limiting middleware FastAPI (F08 — T047).

Applique un rate limiting par IP source sur les routes ``/api/public/verify/*``
pour empêcher l'énumération des attestations.

Implémentation : cache LRU local en mémoire (pas de Redis pour le MVP).
Limite : 10 req/IP/min (FR-015). Header ``Retry-After: 60`` au-delà.
"""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from threading import Lock
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


# Configuration par défaut (paramétrable via constructeur).
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_LIMIT = 10
DEFAULT_LRU_CAPACITY = 10_000  # Nombre max d'IPs trackées simultanément.

# Routes ciblées (regex). Peut être étendu post-MVP.
PUBLIC_VERIFY_PATTERN = re.compile(r"^/api/public/verify/[^/]+/?$")


class _SlidingWindowCounter:
    """Compteur sliding window par IP (purge naturelle via LRU)."""

    def __init__(
        self,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        capacity: int = DEFAULT_LRU_CAPACITY,
    ) -> None:
        self._window = window_seconds
        self._capacity = capacity
        self._lock = Lock()
        # OrderedDict[ip → list[timestamps]]
        self._hits: OrderedDict[str, list[float]] = OrderedDict()

    def _purge_expired(self, ip: str, now: float) -> list[float]:
        """Supprime les timestamps hors fenêtre, retourne la liste restante."""
        cutoff = now - self._window
        timestamps = self._hits.get(ip, [])
        kept = [t for t in timestamps if t > cutoff]
        return kept

    def hit(self, ip: str) -> int:
        """Enregistre un hit ; retourne le compte courant dans la fenêtre."""
        now = time.monotonic()
        with self._lock:
            kept = self._purge_expired(ip, now)
            kept.append(now)
            self._hits[ip] = kept
            # LRU : si capacité dépassée, retire les plus anciens.
            self._hits.move_to_end(ip)
            while len(self._hits) > self._capacity:
                self._hits.popitem(last=False)
            return len(kept)

    def reset(self) -> None:
        """Réinitialise complètement le cache (utilisé par les tests)."""
        with self._lock:
            self._hits.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware FastAPI rate-limit pour les routes publiques de vérification.

    Limite : ``limit`` requêtes par fenêtre ``window_seconds`` par IP source.
    """

    def __init__(
        self,
        app,
        *,
        limit: int = DEFAULT_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        path_patterns: Iterable[re.Pattern[str]] | None = None,
    ) -> None:
        super().__init__(app)
        self._limit = limit
        self._window = window_seconds
        self._patterns = list(path_patterns) if path_patterns else [PUBLIC_VERIFY_PATTERN]
        self._counter = _SlidingWindowCounter(window_seconds=window_seconds)

    def _matches(self, path: str) -> bool:
        return any(p.match(path) for p in self._patterns)

    @staticmethod
    def _client_ip(request: Request) -> str:
        # ``X-Forwarded-For`` peut être présent derrière un reverse proxy.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._matches(request.url.path):
            return await call_next(request)

        ip = self._client_ip(request)
        count = self._counter.hit(ip)
        if count > self._limit:
            logger.warning(
                "rate_limit_exceeded path=%s ip=%s count=%d limit=%d",
                request.url.path, ip, count, self._limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "retry_after": self._window,
                    "message": "Trop de requêtes. Veuillez patienter avant de réessayer.",
                },
                headers={"Retry-After": str(self._window)},
            )
        if count > 5:
            # Log WARN en cas d'énumération suspecte.
            logger.info(
                "rate_limit_close path=%s ip=%s count=%d",
                request.url.path, ip, count,
            )
        return await call_next(request)

    def reset(self) -> None:
        """Réinitialise le compteur (utilisé entre tests)."""
        self._counter.reset()
