from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from backend.app.api.dependencies.auth import get_current_user
from backend.app.models.user import User


def require_roles(
    *allowed_roles: str
) -> Callable:
    """Створює FastAPI-залежність для перевірки ролі користувача."""

    if not allowed_roles:
        raise ValueError(
            "At least one allowed role must be specified"
        )

    def check_roles(
        current_user: Annotated[
            User,
            Depends(get_current_user)
        ]
    ) -> User:
        """Перевіряє, чи має користувач необхідну роль."""

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостатньо прав для виконання цієї дії"
            )

        return current_user

    return check_roles
