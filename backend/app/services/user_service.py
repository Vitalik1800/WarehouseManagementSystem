from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.users import UserUpdate, UserRoleUpdate
from backend.app.services.user_activity_log_service import (
    UserActivityLogService
)


class UserNotFoundError(Exception):
    pass


class UsernameAlreadyExistsError(Exception):
    pass


class LastActiveAdminError(Exception):
    pass


class SelfAdministrativeActionError(Exception):
    """Заборонена адміністративна операція над власним обліковим записом."""
    pass


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.activities = UserActivityLogService(db)

    def update_user(
        self,
        user_id: int,
        data: UserUpdate,
        actor_id: int | None = None
    ) -> User:
        user = self.users.get_by_id(user_id)

        if user is None:
            raise UserNotFoundError("Користувача не знайдено")

        changes = data.model_dump(exclude_unset=True)

        if not changes:
            return user

        new_username = changes.get("username")

        if (
            new_username is not None
            and new_username != user.username
        ):
            existing_user = self.users.get_by_username(new_username)

            if existing_user is not None:
                raise UsernameAlreadyExistsError(
                    "Користувач із таким логіном уже існує"
                )

        changed_fields = sorted(
            field
            for field, value in changes.items()
            if getattr(user, field) != value
        )

        try:
            for field, value in changes.items():
                setattr(user, field, value)

            if changed_fields:
                self.activities.record(
                    action="user.updated",
                    actor_id=actor_id,
                    entity_type="user",
                    entity_id=user.id,
                    details={"changed_fields": changed_fields},
                )

            self.db.commit()
            self.db.refresh(user)

            return user

        except IntegrityError:
            self.db.rollback()

            if (
                new_username is not None
                and self.users.get_by_username(new_username) is not None
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
        data: UserRoleUpdate,
        actor_id: int | None = None
    ) -> User:
        try:
            # Блокуємо активних адміністраторів на час транзакції.
            active_admins = self.users.get_active_admins_for_update()

            user = self.users.get_by_id(user_id)

            if user is None:
                raise UserNotFoundError("Користувача не знайдено")

            # Повторна операція не створює запису аудиту.
            if user.role == data.role:
                self.db.commit()
                return user

            # Заборона самостійного пониження ролі адміністратора.
            if (
                actor_id is not None
                and user.id == actor_id
                and user.role == "admin"
                and data.role == "worker"
            ):
                raise SelfAdministrativeActionError(
                    "Адміністратор не може самостійно понизити свою роль"
                )

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

            old_role = user.role
            user.role = data.role

            self.activities.record(
                action="user.role_changed",
                actor_id=actor_id,
                entity_type="user",
                entity_id=user.id,
                details={
                    "old_role": old_role,
                    "new_role": data.role,
                },
            )

            self.db.commit()
            self.db.refresh(user)

            return user

        except Exception:
            self.db.rollback()
            raise

    def set_user_active(
        self,
        user_id: int,
        is_active: bool,
        actor_id: int | None = None
    ) -> User:
        try:
            active_admins = self.users.get_active_admins_for_update()

            user = self.users.get_by_id(user_id)

            if user is None:
                raise UserNotFoundError("Користувача не знайдено")

            # Повторна операція не створює запису аудиту.
            if user.is_active == is_active:
                self.db.commit()
                return user

            # Заборона самостійної деактивації адміністратора.
            if (
                actor_id is not None
                and user.id == actor_id
                and user.role == "admin"
                and not is_active
            ):
                raise SelfAdministrativeActionError(
                    "Адміністратор не може деактивувати "
                    "власний обліковий запис"
                )

            # Захист останнього активного адміністратора.
            if (
                not is_active
                and user.role == "admin"
                and user.is_active
                and len(active_admins) <= 1
            ):
                raise LastActiveAdminError(
                    "Не можна деактивувати останнього "
                    "активного адміністратора"
                )

            old_is_active = user.is_active
            user.is_active = is_active

            self.activities.record(
                action=(
                    "user.activated"
                    if is_active
                    else "user.deactivated"
                ),
                actor_id=actor_id,
                entity_type="user",
                entity_id=user.id,
                details={
                    "old_is_active": old_is_active,
                    "new_is_active": is_active,
                },
            )

            self.db.commit()
            self.db.refresh(user)

            return user

        except Exception:
            self.db.rollback()
            raise
