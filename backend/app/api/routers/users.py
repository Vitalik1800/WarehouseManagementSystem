from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.auth import UserResponse


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get(
    "",
    dependencies=[Depends(require_roles("admin"))],
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List users (admin only)",
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)
def list_users(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[UserResponse]:
    users = UserRepository(db).get_all(offset=offset, limit=limit)
    return [UserResponse.model_validate(user) for user in users]
