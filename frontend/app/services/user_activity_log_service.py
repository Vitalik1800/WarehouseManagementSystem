from __future__ import annotations

from datetime import datetime
from typing import Any

from frontend.app.api.client import APIClient


class UserActivityLogClientServiceError(Exception):
    """Invalid response or unavailable authenticated session."""


class UserActivityLogClientService:
    """Read-only frontend gateway to the user activity log API."""

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    @staticmethod
    def _positive_id(value: int | None, name: str) -> None:
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError(f"{name} must be a positive integer")

    @staticmethod
    def _filter_text(value: str | None, name: str, max_length: int) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_length:
            raise ValueError(f"{name} must contain 1-{max_length} characters")
        return value.strip()

    @staticmethod
    def _datetime(value: datetime | None, name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, datetime) or value.tzinfo is not None:
            raise ValueError(f"{name} must be a timezone-naive datetime")
        return value.isoformat(timespec="seconds")

    @staticmethod
    def _validate_row(item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise UserActivityLogClientServiceError("Invalid activity log record")
        event_id = item.get("id")
        actor_id = item.get("actor_id")
        action = item.get("action")
        entity_type = item.get("entity_type")
        entity_id = item.get("entity_id")
        details = item.get("details")
        created_at = item.get("created_at")
        if type(event_id) is not int or event_id < 1:
            raise UserActivityLogClientServiceError("Invalid activity ID")
        if actor_id is not None and (type(actor_id) is not int or actor_id < 1):
            raise UserActivityLogClientServiceError("Invalid actor ID")
        if not isinstance(action, str) or not 1 <= len(action) <= 100:
            raise UserActivityLogClientServiceError("Invalid action")
        if entity_type is not None and (not isinstance(entity_type, str) or not 1 <= len(entity_type) <= 50):
            raise UserActivityLogClientServiceError("Invalid entity type")
        if entity_id is not None and (type(entity_id) is not int or entity_id < 1):
            raise UserActivityLogClientServiceError("Invalid entity ID")
        if details is not None and (not isinstance(details, dict) or any(not isinstance(k, str) for k in details)):
            raise UserActivityLogClientServiceError("Invalid event details")
        if not isinstance(created_at, str):
            raise UserActivityLogClientServiceError("Invalid event timestamp")
        try:
            parsed_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise UserActivityLogClientServiceError("Invalid event timestamp") from exc
        if parsed_date.tzinfo is not None:
            raise UserActivityLogClientServiceError("Unexpected timezone in event timestamp")
        return {
            "id": event_id,
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
            "created_at": created_at,
        }

    def list_activity_logs(
        self,
        offset: int = 0,
        limit: int = 50,
        *,
        actor_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "newest",
    ) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        self._positive_id(actor_id, "actor_id")
        self._positive_id(entity_id, "entity_id")
        action = self._filter_text(action, "action", 100)
        entity_type = self._filter_text(entity_type, "entity_type", 50)
        start = self._datetime(date_from, "date_from")
        end = self._datetime(date_to, "date_to")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be earlier than or equal to date_to")
        if sort_by not in ("newest", "oldest") or not isinstance(sort_by, str):
            raise ValueError("sort_by must be newest or oldest")
        if not self.api_client.is_authenticated:
            raise UserActivityLogClientServiceError("Authentication required")
        params: dict[str, Any] = {"offset": offset, "limit": limit, "sort_by": sort_by}
        for key, value in (
            ("actor_id", actor_id), ("action", action),
            ("entity_type", entity_type), ("entity_id", entity_id),
            ("date_from", start), ("date_to", end),
        ):
            if value is not None:
                params[key] = value
        result = self.api_client.get("/user-activity-logs", params=params)
        if not isinstance(result, list) or len(result) > limit:
            raise UserActivityLogClientServiceError("Invalid activity log response")
        rows = [self._validate_row(item) for item in result]
        if len({row["id"] for row in rows}) != len(rows):
            raise UserActivityLogClientServiceError("Duplicate activity log IDs")
        return rows
