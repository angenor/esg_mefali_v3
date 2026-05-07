"""Middleware FastAPI qui positionne ``source_of_change="admin"`` (F03).

Toutes les requêtes vers ``/api/admin/*`` ouvrent un scope admin via
:func:`app.core.audit_context.source_of_change_scope`. Toute mutation
effectuée par un endpoint admin sur un modèle ``Auditable`` est ainsi tracée
avec ``audit_log.source_of_change = 'admin'`` automatiquement.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.audit_context import source_of_change_scope


class AdminAuditContextMiddleware(BaseHTTPMiddleware):
    """Active la ContextVar ``source_of_change="admin"`` sur ``/api/admin/*``."""

    async def dispatch(
        self, request: Request, call_next  # type: ignore[no-untyped-def]
    ) -> Response:
        path = request.url.path
        if path.startswith("/api/admin/") or path == "/api/admin":
            with source_of_change_scope("admin"):
                return await call_next(request)
        return await call_next(request)
