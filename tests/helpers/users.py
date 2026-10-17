from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.models.user import User


def create_test_user(
    db: Session,
    *,
    name: str = "Test User",
    username: str | None = None,
    password: str = "SecurePassword123!",
    role: str = "worker",
    is_active: bool = True
) -> User:
    if username is None:
        username = f"test_{uuid4().hex[:16]}"

    user = User(
        name=name,
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active
    )

    db.add(user)
    db.flush()

    return user
