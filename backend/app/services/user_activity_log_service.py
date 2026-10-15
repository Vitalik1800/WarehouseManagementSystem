from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.user_activity_log import UserActivityLog
from backend.app.repositories.user_activity_log_repository import (
    UserActivityLogRepository
)


class UserActivityLogService:
    """Business logic for user activity auditing."""

    ALLOWED_DETAIL_FIELDS = frozenset({
        "changed_fields",
        "old_role",
        "new_role",
        "old_is_active",
        "new_is_active"
    })

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = UserActivityLogRepository(db)

    def record(
        self,
        *,
        action: str,
        actor_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        details: dict[str, Any] | None = None
    ) -> UserActivityLog:
        """Record an event without committing the transaction."""

        safe_details = None

        if details is not None:
            unknown_fields = (
                set(details) - self.ALLOWED_DETAIL_FIELDS
            )

            if unknown_fields:
                raise ValueError(
                    "Unsupported audit detail fields: "
                    + ", ".join(sorted(unknown_fields))
                )

            safe_details = dict(details)

        return self.activities.create(
            action=action,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=safe_details
        )

    def get_all(
        self,
        *,
        current_user_id: int,
        current_user_role: str,
        offset: int = 0,
        limit: int = 50,
        actor_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "newest"
    ) -> list[UserActivityLog]:
        """Admins see all events; workers see only their own."""

        if current_user_role == "admin":
            effective_actor_id = actor_id

        elif current_user_role == "worker":
            if (
                    actor_id is not None
                    and actor_id != current_user_id
            ):
                raise PermissionError(
                    "Cannot view another user's activity"
                )

            effective_actor_id = current_user_id

        else:
            raise PermissionError(
                "Unsupported user role"
            )

        return self.activities.get_all(
            offset=offset,
            limit=limit,
            actor_id=effective_actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by
        )
