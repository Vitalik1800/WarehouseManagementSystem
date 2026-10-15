from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    details: dict[str, Any] | None
    created_at: datetime
