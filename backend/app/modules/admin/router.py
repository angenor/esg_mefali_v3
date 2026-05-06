"""Router back-office Admin (F02 squelette + endpoint health)."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin
from app.models.user import User
from app.schemas.admin import AdminHealthResponse

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/health", response_model=AdminHealthResponse)
async def admin_health(
    current_admin: User = Depends(get_current_admin),
) -> AdminHealthResponse:
    """Health check du back-office. 200 si Admin, 403 sinon."""
    return AdminHealthResponse(
        status="ok",
        role=current_admin.role,
        service="admin-backoffice",
    )
