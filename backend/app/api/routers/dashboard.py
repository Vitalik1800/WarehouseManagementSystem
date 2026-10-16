from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.services.dashboard_service import DashboardService


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get(
    "/summary",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard summary",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"}
    }
)
def get_dashboard_summary(
    db: Annotated[Session, Depends(get_db)],
) -> DashboardSummaryResponse:
    service = DashboardService(db)
    return service.get_summary()
