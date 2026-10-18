from typing import Any

from frontend.app.api.client import APIClient, APIClientError, APIRequestError
from frontend.app.services.credential_store import CredentialStore, CredentialStoreError


class AuthenticationError(APIClientError):
    """Invalid authentication data or inability to preserve a secure session."""


class AuthService:
    def __init__(self, api_client: APIClient, credential_store: CredentialStore | None = None) -> None:
        self.api_client = api_client
        self.credential_store = credential_store if credential_store is not None else CredentialStore()

    @staticmethod
    def _validate_tokens(response: Any) -> tuple[str, str]:
        if not isinstance(response, dict):
            raise AuthenticationError("Backend returned invalid authentication data")
        access = response.get("access_token")
        refresh = response.get("refresh_token")
        if (not isinstance(access, str) or not access.strip()
                or not isinstance(refresh, str) or not refresh.strip()
                or response.get("token_type", "bearer") != "bearer"):
            raise AuthenticationError("Backend returned invalid authentication data")
        return access, refresh

    def login(self, username: str, password: str) -> dict[str, Any]:
        if not username or not username.strip():
            raise ValueError("Username cannot be empty")
        if not password:
            raise ValueError("Password cannot be empty")
        self.api_client.clear_access_token()
        response = self.api_client.post("/auth/login", json={"username": username.strip(), "password": password})
        access, refresh = self._validate_tokens(response)
        # Persist first: never report a successful persistent login if secure storage failed.
        self.credential_store.save(refresh)
        self.api_client.set_access_token(access)
        return response

    def restore_session(self) -> dict[str, Any] | None:
        """Restore a persisted session; return the user profile or None if none exists.

        Network errors are propagated without deleting credentials. HTTP 401 removes
        the invalid credential. A failed secure write prevents a successful restore.
        """
        self.api_client.clear_access_token()
        refresh = self.credential_store.load()
        if refresh is None:
            return None
        try:
            response = self.api_client.post("/auth/refresh", json={"refresh_token": refresh})
        except APIRequestError as exc:
            if exc.status_code == 401:
                self.credential_store.delete()
                return None
            raise
        access, new_refresh = self._validate_tokens(response)
        self.credential_store.save(new_refresh)
        self.api_client.set_access_token(access)
        try:
            return self.get_current_user()
        except APIRequestError as exc:
            self.api_client.clear_access_token()
            if exc.status_code == 401:
                self.credential_store.delete()
                return None
            raise
        except Exception:
            self.api_client.clear_access_token()
            raise

    def get_current_user(self) -> dict[str, Any]:
        if not self.api_client.is_authenticated:
            raise AuthenticationError("User is not authenticated")
        try:
            response = self.api_client.get("/auth/me")
        except APIRequestError as exc:
            if exc.status_code == 401:
                self.api_client.clear_access_token()
            raise
        if not isinstance(response, dict):
            raise AuthenticationError("Backend returned an invalid user response")
        return response

    def logout(self) -> None:
        """Explicit logout clears local persistence, then revokes remote tokens."""
        refresh = self.credential_store.load()
        # Explicit logout must remove persistence even without an access token.
        self.credential_store.delete()
        try:
            if self.api_client.is_authenticated:
                try:
                    body = {"refresh_token": refresh} if refresh else None
                    if body is None:
                        self.api_client.post("/auth/logout")
                    else:
                        self.api_client.post("/auth/logout", json=body)
                except APIRequestError as exc:
                    if exc.status_code != 401:
                        raise
        finally:
            self.api_client.clear_access_token()

    @property
    def is_authenticated(self) -> bool:
        return self.api_client.is_authenticated
