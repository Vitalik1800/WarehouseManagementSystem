import pytest

from frontend.app.api.client import APIConnectionError, APIRequestError
from frontend.app.services.auth_service import AuthService, AuthenticationError
from frontend.app.services.credential_store import CredentialStoreError


class FakeStore:
    def __init__(self, token=None):
        self.token = token
        self.fail_save = False
        self.deleted = 0
    def load(self):
        return self.token
    def save(self, token):
        if self.fail_save:
            raise CredentialStoreError("write failed")
        self.token = token
    def delete(self):
        self.token = None
        self.deleted += 1


class FakeClient:
    def __init__(self):
        self.token = None
        self.calls = []
        self.responses = {}
    def set_access_token(self, token):
        self.token = token
    def clear_access_token(self):
        self.token = None
    @property
    def is_authenticated(self):
        return self.token is not None
    def post(self, path, **kwargs):
        self.calls.append((path, kwargs))
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return value
    def get(self, path):
        self.calls.append((path, {}))
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return value


def tokens(a="access", r="refresh"):
    return {"access_token": a, "refresh_token": r, "token_type": "bearer"}


def test_login_saves_refresh_and_access():
    api, store = FakeClient(), FakeStore()
    api.responses["/auth/login"] = tokens()
    result = AuthService(api, store).login(" alice ", "password")
    assert result == tokens()
    assert store.token == "refresh" and api.token == "access"
    assert api.calls[0][1]["json"]["username"] == "alice"


def test_login_store_failure_does_not_authenticate():
    api, store = FakeClient(), FakeStore()
    store.fail_save = True
    api.responses["/auth/login"] = tokens()
    with pytest.raises(CredentialStoreError):
        AuthService(api, store).login("alice", "password")
    assert not api.is_authenticated


def test_login_requires_both_tokens():
    api, store = FakeClient(), FakeStore()
    api.responses["/auth/login"] = {"access_token": "a"}
    with pytest.raises(AuthenticationError):
        AuthService(api, store).login("alice", "password")
    assert store.token is None


def test_restore_rotates_and_fetches_profile():
    api, store = FakeClient(), FakeStore("old")
    api.responses["/auth/refresh"] = tokens("new-access", "new-refresh")
    api.responses["/auth/me"] = {"id": 4, "username": "alice"}
    profile = AuthService(api, store).restore_session()
    assert profile["id"] == 4
    assert store.token == "new-refresh" and api.token == "new-access"
    assert api.calls[0][1]["json"] == {"refresh_token": "old"}


def test_restore_no_saved_token():
    api, store = FakeClient(), FakeStore()
    assert AuthService(api, store).restore_session() is None
    assert api.calls == []


def test_restore_401_deletes_saved_token():
    api, store = FakeClient(), FakeStore("old")
    api.responses["/auth/refresh"] = APIRequestError(401, "invalid")
    assert AuthService(api, store).restore_session() is None
    assert store.token is None and store.deleted == 1


def test_restore_network_error_preserves_saved_token():
    api, store = FakeClient(), FakeStore("old")
    api.responses["/auth/refresh"] = APIConnectionError("offline")
    with pytest.raises(APIConnectionError):
        AuthService(api, store).restore_session()
    assert store.token == "old" and not api.is_authenticated


def test_restore_save_failure_does_not_authenticate():
    api, store = FakeClient(), FakeStore("old")
    store.fail_save = True
    api.responses["/auth/refresh"] = tokens("new-access", "new-refresh")
    with pytest.raises(CredentialStoreError):
        AuthService(api, store).restore_session()
    assert not api.is_authenticated


def test_restore_profile_401_removes_saved_token():
    api, store = FakeClient(), FakeStore("old")
    api.responses["/auth/refresh"] = tokens("new-access", "new-refresh")
    api.responses["/auth/me"] = APIRequestError(401, "unauthorized")
    assert AuthService(api, store).restore_session() is None
    assert store.token is None and not api.is_authenticated


def test_logout_revokes_refresh_and_clears_local():
    api, store = FakeClient(), FakeStore("refresh")
    api.token = "access"
    api.responses["/auth/logout"] = None
    AuthService(api, store).logout()
    assert store.token is None and not api.is_authenticated
    assert api.calls[0] == ("/auth/logout", {"json": {"refresh_token": "refresh"}})


def test_logout_without_access_still_clears_refresh():
    api, store = FakeClient(), FakeStore("refresh")
    AuthService(api, store).logout()
    assert store.token is None and api.calls == []


def test_logout_network_error_still_clears_local():
    api, store = FakeClient(), FakeStore("refresh")
    api.token = "access"
    api.responses["/auth/logout"] = APIConnectionError("offline")
    with pytest.raises(APIConnectionError):
        AuthService(api, store).logout()
    assert store.token is None and not api.is_authenticated
