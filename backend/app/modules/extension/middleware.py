"""Middleware FastAPI ``ExtensionAuditContextMiddleware`` (F24).

Active la ContextVar ``source_of_change="extension"`` sur les requêtes
``/api/extension/*`` afin que toute mutation déclenchée depuis l'extension
soit auditée comme tel (cf. F03 audit log).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.audit_context import source_of_change_scope


class ExtensionAuditContextMiddleware(BaseHTTPMiddleware):
    """Active ``source_of_change='extension'`` sur ``/api/extension/*``."""

    async def dispatch(
        self, request: Request, call_next  # type: ignore[no-untyped-def]
    ) -> Response:
        path = request.url.path
        if path.startswith("/api/extension/") or path == "/api/extension":
            with source_of_change_scope("extension"):
                return await call_next(request)
        return await call_next(request)
