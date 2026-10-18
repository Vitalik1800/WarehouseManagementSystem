from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.auth import (
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
    UserLogin,
    UserResponse
)
from backend.app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
)

from backend.app.core.security import create_access_token
from backend.app.services.refresh_token_service import RefreshTokenService, InvalidRefreshTokenError

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

    service.record_successful_login(
        user_id=user.id
    )

    refresh_token = RefreshTokenService(db).issue(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Оновлення токенів доступу",
)
def refresh_tokens(
    data: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    try:
        tokens = RefreshTokenService(db).refresh(data.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний або прострочений refresh-токен",
        ) from exc
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
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
    db: Annotated[Session, Depends(get_db)],
    data: LogoutRequest | None = None,
) -> None:
    """Відкликає поточний JWT користувача."""
    service = AuthService(db)
    if data is not None and data.refresh_token is not None:
        # Never revoke a session owned by another user.
        from hashlib import sha256
        from backend.app.repositories.user_session_repository import UserSessionRepository
        digest = sha256(data.refresh_token.encode("utf-8")).hexdigest()
        candidate = UserSessionRepository(db).get_by_token_hash(digest)
        if candidate is None or candidate.user_id != current_user.id:
            raise HTTPException(status_code=401, detail="Недійсна сесія")
        RefreshTokenService(db).revoke(data.refresh_token)
    service.logout(
        token_payload=payload,
        actor_id=current_user.id
    )
