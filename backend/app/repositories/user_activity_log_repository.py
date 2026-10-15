from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user_activity_log import UserActivityLog


class UserActivityLogRepository:
    """Repository for user activity audit records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(
        self,
        activity_id: int
    ) -> UserActivityLog | None:
        return self.db.get(UserActivityLog, activity_id)

    def get_all(
        self,
        *,
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

        if offset < 0:
            raise ValueError(
                "Offset must not be negative"
            )

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit must be between 1 and 100"
            )

        if sort_by not in ("newest", "oldest"):
            raise ValueError(
                "Sort by must be newest or oldest"
            )

        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise ValueError(
                "Date from must not be later than date to"
            )

        statement = select(UserActivityLog)

        if actor_id is not None:
            statement = statement.where(
                UserActivityLog.actor_id == actor_id
            )

        if action is not None:
            statement = statement.where(
                UserActivityLog.action == action
            )

        if entity_type is not None:
            statement = statement.where(
                UserActivityLog.entity_type == entity_type
            )

        if entity_id is not None:
            statement = statement.where(
                UserActivityLog.entity_id == entity_id
            )

        if date_from is not None:
            statement = statement.where(
                UserActivityLog.created_at >= date_from
            )

        if date_to is not None:
            statement = statement.where(
                UserActivityLog.created_at <= date_to
            )

        if sort_by == "oldest":
            statement = statement.order_by(
                UserActivityLog.created_at.asc(),
                UserActivityLog.id.asc()
            )
        else:
            statement = statement.order_by(
                UserActivityLog.created_at.desc(),
                UserActivityLog.id.desc()
            )

        statement = (
            statement
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.scalars(statement).all()
        )

    def create(
        self,
        *,
        action: str,
        actor_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        details: dict[str, Any] | None = None
    ) -> UserActivityLog:

        if not action or not action.strip():
            raise ValueError(
                "Action must not be empty"
            )

        if len(action) > 100:
            raise ValueError(
                "Action must not exceed 100 characters"
            )

        if entity_type is not None and len(entity_type) > 50:
            raise ValueError(
                "Entity type must not exceed 50 characters"
            )

        activity = UserActivityLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details
        )

        self.db.add(activity)
        self.db.flush()

        return activity
