from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse
)
from backend.app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    UsernameAlreadyExistsError
)

from backend.app.core.security import create_access_token

from backend.app.api.dependencies.auth import (
    get_current_user,
    get_token_payload
)

from backend.app.models.user import User


router = APIRouter(
    prefix="/auth",
    tags=["Автентифікація"]
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Реєстрація нового користувача",
    responses={
        409: {
            "description": "Користувач із таким логіном уже існує"
        }
    }
)
def register_user(
    data: UserRegister,
    db: Annotated[Session, Depends(get_db)]
) -> UserResponse:
    """Реєструє нового користувача системи."""
    service = AuthService(db)

    try:
        user = service.register(data)
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Вхід користувача в систему",
    responses={
        401: {
            "description": "Неправильний логін або пароль"
        }
    }
)
def login_user(
    data: UserLogin,
    db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    """Перевіряє облікові дані та видає JWT-токен."""
    service = AuthService(db)

    try:
        user = service.authenticate(
            username=data.username,
            password=data.password
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний логін або пароль",
            headers={"WWW-Authenticate": "Bearer"}
        ) from exc

    access_token = create_access_token(
        user_id=user.id
    )

    return TokenResponse(
        access_token=access_token
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Отримання поточного користувача",
    responses={
        401: {
            "description": "Відсутній або недійсний токен доступу"
        }
    }
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserResponse:
    """Повертає інформацію про поточного авторизованого користувача."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Вихід користувача із системи",
    responses={
        401: {
            "description": "Відсутній, недійсний або відкликаний JWT"
        }
    }
)
def logout_user(
    payload: Annotated[dict, Depends(get_token_payload)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    """Відкликає поточний JWT користувача."""
    service = AuthService(db)
    service.logout(payload)
