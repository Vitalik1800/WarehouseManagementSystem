from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.users import UserUpdate, UserRoleUpdate


class UserNotFoundError(Exception):
    pass


class UsernameAlreadyExistsError(Exception):
    pass


class LastActiveAdminError(Exception):
    pass


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def update_user(
        self,
        user_id: int,
        data: UserUpdate
    ) -> User:
        user = self.users.get_by_id(user_id)

        if user is None:
            raise UserNotFoundError(
                "Користувача не знайдено"
            )

        changes = data.model_dump(exclude_unset=True)

        if not changes:
            return user

        new_username = changes.get("username")

        if (
            new_username is not None
            and new_username != user.username
        ):
            existing_user = self.users.get_by_username(
                new_username
            )

            if existing_user is not None:
                raise UsernameAlreadyExistsError(
                    "Користувач із таким логіном уже існує"
                )

        try:
            for field, value in changes.items():
                setattr(user, field, value)

            self.db.commit()
            self.db.refresh(user)

            return user

        except IntegrityError:
            self.db.rollback()

            if (
                new_username is not None
                and self.users.get_by_username(new_username)
                is not None
            ):
                raise UsernameAlreadyExistsError(
                    "Користувач із таким логіном уже існує"
                ) from None

            raise

        except Exception:
            self.db.rollback()
            raise

    def change_user_role(
        self,
        user_id: int,
        data: UserRoleUpdate
    ) -> User:
        try:
            # Отримуємо блокування активних адміністраторів.
            active_admins = self.users.get_active_admins_for_update()

            user = self.users.get_by_id(user_id)

            if user is None:
                raise UserNotFoundError("Користувача не знайдено")

            # Повторне встановлення тієї самої ролі.
            if user.role == data.role:
                self.db.commit()
                return user

            # Захист останнього активного адміністратора.
            if (
                user.role == "admin"
                and user.is_active
                and data.role == "worker"
                and len(active_admins) <= 1
            ):
                raise LastActiveAdminError(
                    "Не можна змінити роль останнього "
                    "активного адміністратора"
                )

            user.role = data.role

            self.db.commit()
            self.db.refresh(user)

            return user

        except Exception:
            self.db.rollback()
            raise
