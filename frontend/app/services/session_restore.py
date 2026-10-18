"""Restore a persisted login without touching Tkinter widgets."""
from dataclasses import dataclass
from typing import Any

from frontend.app.api.client import APIClient
from frontend.app.services.auth_service import AuthService


@dataclass(frozen=True)
class RestoredSession:
    user: dict[str, Any]
    access_token: str


def restore_session_worker(settings) -> RestoredSession | None:
    # Dedicated client: never share an httpx.Client with the GUI during startup.
    client = APIClient(settings=settings)
    try:
        user = AuthService(client).restore_session()
        if user is None:
            return None
        token = client._access_token
        if not isinstance(user, dict) or not isinstance(token, str) or not token:
            raise RuntimeError("Session restore returned incomplete authentication data")
        return RestoredSession(user=user, access_token=token)
    finally:
        client.close()
