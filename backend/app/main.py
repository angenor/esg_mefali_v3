"""Point d'entrée FastAPI avec lifespan, CORS et routers."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# Référence globale au graphe compilé LangGraph
compiled_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Cycle de vie de l'application : initialisation et nettoyage."""
    global compiled_graph

    # Démarrage : initialiser le graphe LangGraph
    if settings.openrouter_api_key:
        try:
            from app.graph.graph import create_compiled_graph

            compiled_graph = await create_compiled_graph()
            logger.info("Graphe LangGraph initialisé avec succès")
        except Exception as e:
            logger.warning("Impossible d'initialiser le graphe LangGraph : %s", e)
            compiled_graph = None
    else:
        logger.warning("OPENROUTER_API_KEY non configurée — graphe LangGraph désactivé")

    yield

    # Arrêt
    compiled_graph = None


app = FastAPI(
    title="ESG Mefali API",
    description="Plateforme conversationnelle IA pour la finance durable des PME africaines",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routers
from app.api.auth import router as auth_router  # noqa: E402
from app.api.chat import router as chat_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.modules.company.router import router as company_router  # noqa: E402
from app.modules.documents.router import router as documents_router  # noqa: E402
from app.modules.esg.router import router as esg_router  # noqa: E402
from app.modules.reports.router import router as reports_router  # noqa: E402
from app.modules.carbon.router import router as carbon_router  # noqa: E402
from app.modules.financing.router import router as financing_router  # noqa: E402
from app.modules.applications.router import router as applications_router  # noqa: E402
from app.modules.credit.router import router as credit_router  # noqa: E402
from app.modules.dashboard.router import router as dashboard_router  # noqa: E402
from app.modules.action_plan.router import router as action_plan_router  # noqa: E402
# F02 — modules account (invitations équipe) et admin (back-office Mefali).
from app.modules.account.router import router as account_router  # noqa: E402
from app.modules.admin.router import router as admin_router  # noqa: E402
# F01 — Catalogue de sources verifiees.
from app.modules.sources.router import router as sources_router  # noqa: E402

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(company_router, prefix="/api/company", tags=["company"])
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(esg_router, prefix="/api/esg", tags=["esg"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(carbon_router, prefix="/api/carbon", tags=["carbon"])
app.include_router(financing_router, prefix="/api/financing", tags=["financing"])
app.include_router(applications_router, prefix="/api/applications", tags=["applications"])
app.include_router(credit_router, prefix="/api/credit", tags=["credit"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(action_plan_router, prefix="/api/action-plan", tags=["action-plan"])
app.include_router(account_router, prefix="/api/account", tags=["account"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(sources_router, prefix="/api/sources", tags=["sources"])
app.include_router(health_router, prefix="/api", tags=["health"])
