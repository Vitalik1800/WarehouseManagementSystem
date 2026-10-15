from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status
)
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.user_activity_logs import (
    UserActivityLogResponse
)
from backend.app.services.user_activity_log_service import (
    UserActivityLogService
)


router = APIRouter(
    prefix="/user-activity-logs",
    tags=["User Activity Logs"]
)

AuthorizedUser = Annotated[
    User,
    Depends(require_roles("admin", "worker"))
]

DatabaseSession = Annotated[
    Session,
    Depends(get_db)
]


@router.get(
    "",
    response_model=list[UserActivityLogResponse],
    status_code=status.HTTP_200_OK,
    summary="List user activity logs",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_user_activity_logs(
    db: DatabaseSession,
    current_user: AuthorizedUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    actor_id: Annotated[int | None, Query(ge=1)] = None,
    action: Annotated[
        str | None,
        Query(min_length=1, max_length=100)
    ] = None,
    entity_type: Annotated[
        str | None,
        Query(min_length=1, max_length=50)
    ] = None,
    entity_id: Annotated[int | None, Query(ge=1)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: Literal["newest", "oldest"] = "newest"
) -> list[UserActivityLogResponse]:

    if date_from is not None and date_from.tzinfo is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not contain timezone information",
        )

    if date_to is not None and date_to.tzinfo is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_to must not contain timezone information"
        )

    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be earlier than or equal to date_to"
        )

    service = UserActivityLogService(db)

    try:
        activities = service.get_all(
            current_user_id=current_user.id,
            current_user_role=current_user.role,
            offset=offset,
            limit=limit,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc)
        ) from exc

    return [
        UserActivityLogResponse.model_validate(activity)
        for activity in activities
    ]
