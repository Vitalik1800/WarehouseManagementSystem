from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User


class UserRepository:
    """Репозиторій для роботи з користувачами."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        """Знаходить користувача за ідентифікатором."""
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        """Знаходить користувача за логіном."""
        statement = select(User).where(
            User.username == username
        )

        return self.db.scalar(statement)

    def create(
        self,
        *,
        name: str,
        username: str,
        password_hash: str,
        role: str = "worker"
    ) -> User:
        """Додає нового користувача до поточної транзакції."""
        user = User(
            name=name,
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=True
        )

        self.db.add(user)
        self.db.flush()

        return user
