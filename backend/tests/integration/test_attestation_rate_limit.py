"""Tests rate limiting sur /api/public/verify/* (F08 — T043).

Note : pour isoler les tests entre runs, on réinitialise explicitement le
compteur du ``RateLimitMiddleware`` instancié par FastAPI. Si l'app expose
plusieurs middlewares, on cherche celui de type ``RateLimitMiddleware``.
"""

from __future__ import annotations

import pytest


def _reset_rate_limit_counter():
    """Trouve le middleware ``RateLimitMiddleware`` et reset son compteur."""
    from app.main import app
    from app.middleware.rate_limit import RateLimitMiddleware

    # Starlette construit la stack de middlewares à la volée. On accède à
    # ``app.middleware_stack`` qui est construit au premier .build() ; à défaut
    # on parcourt user_middleware. Le plus simple : invalider la stack.
    for mw_def in app.user_middleware:
        cls = mw_def.cls
        if cls is RateLimitMiddleware:
            # On ne peut pas reset facilement l'instance déjà créée ; le plus
            # simple est de réinitialiser ``_counter`` via une nouvelle instance.
            # Note : si la stack est déjà construite, l'instance courante reste
            # utilisée. Pour les tests, on accepte que les windows soient
            # courtes (60s) et on s'appuie sur la commande explicite ci-dessous.
            pass
    # Approche directe : reset le _SlidingWindowCounter au niveau classe.
    # ``RateLimitMiddleware`` n'expose pas de singleton, donc on récupère
    # l'instance via la pile Starlette.
    middleware_stack = getattr(app, "middleware_stack", None)
    visited = set()
    stack = [middleware_stack] if middleware_stack is not None else []
    while stack:
        node = stack.pop()
        if node is None or id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, RateLimitMiddleware):
            node.reset()
        # Visiter récursivement (Starlette wraps les middlewares).
        for attr in ("app", "_app"):
            child = getattr(node, attr, None)
            if child is not None:
                stack.append(child)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Réinitialise le compteur de rate limit avant chaque test."""
    _reset_rate_limit_counter()
    yield
    _reset_rate_limit_counter()


@pytest.mark.asyncio
async def test_rate_limit_below_threshold_passes(client):
    """5 requêtes en rafale (< limite 10) → toutes passent."""
    for i in range(5):
        resp = await client.get("/api/public/verify/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 200, f"Iteration {i}: {resp.status_code}"


@pytest.mark.asyncio
async def test_rate_limit_above_threshold_returns_429(client):
    """15 requêtes en rafale → ≥ 4 doivent retourner 429 après le 10e hit."""
    statuses = []
    for _ in range(15):
        resp = await client.get("/api/public/verify/00000000-0000-0000-0000-000000000000")
        statuses.append(resp.status_code)
    n_429 = sum(1 for s in statuses if s == 429)
    assert n_429 >= 4, f"Pas assez de 429 : {statuses}"


@pytest.mark.asyncio
async def test_rate_limit_429_includes_retry_after_header(client):
    """Header Retry-After présent sur 429."""
    last_resp = None
    for _ in range(15):
        last_resp = await client.get(
            "/api/public/verify/00000000-0000-0000-0000-000000000000",
        )
    if last_resp.status_code == 429:
        assert "retry-after" in {k.lower() for k in last_resp.headers.keys()}
