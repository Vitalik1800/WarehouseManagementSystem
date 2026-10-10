from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.auth import UserResponse

from backend.app.schemas.users import UserUpdate

from backend.app.services.user_service import (
    UserService,
    UserNotFoundError,
    UsernameAlreadyExistsError
)


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


@router.get(
    "/{user_id}",
    dependencies=[Depends(require_roles("admin"))],
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user by ID (admin only)",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "User not found"},
        422: {"description": "Validation error"}
    }
)
def get_user(
    user_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> UserResponse:
    user = UserRepository(db).get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Користувача не знайдено"
        )

    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    dependencies=[Depends(require_roles("admin"))],
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user (admin only)",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "User not found"},
        409: {"description": "Username already exists"},
        422: {"description": "Validation error"}
    }
)
def update_user(
    user_id: Annotated[int, Path(ge=1)],
    data: UserUpdate,
    db: Annotated[Session, Depends(get_db)]
) -> UserResponse:
    service = UserService(db)

    try:
        user = service.update_user(
            user_id=user_id,
            data=data
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return UserResponse.model_validate(user)
