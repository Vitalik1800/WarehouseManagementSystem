from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from frontend.app.services import session_restore


def _setup(monkeypatch, result=None, token="access", error=None):
    client = SimpleNamespace(_access_token=token, close=Mock())
    auth = Mock()
    if error:
        auth.restore_session.side_effect = error
    else:
        auth.restore_session.return_value = result
    factory = Mock(return_value=client)
    monkeypatch.setattr(session_restore, "APIClient", factory)
    monkeypatch.setattr(session_restore, "AuthService", Mock(return_value=auth))
    return client, auth, factory


def test_restore_success_closes_dedicated_client(monkeypatch):
    client, auth, factory = _setup(monkeypatch, {"id": 7}, "jwt")
    settings = object()
    result = session_restore.restore_session_worker(settings)
    assert result == session_restore.RestoredSession({"id": 7}, "jwt")
    factory.assert_called_once_with(settings=settings)
    auth.restore_session.assert_called_once_with()
    client.close.assert_called_once_with()


def test_restore_no_saved_session(monkeypatch):
    client, _, _ = _setup(monkeypatch)
    assert session_restore.restore_session_worker(object()) is None
    client.close.assert_called_once_with()


def test_restore_network_failure_still_closes(monkeypatch):
    client, _, _ = _setup(monkeypatch, error=ConnectionError("offline"))
    with pytest.raises(ConnectionError):
        session_restore.restore_session_worker(object())
    client.close.assert_called_once_with()


@pytest.mark.parametrize("user,token", [({"id": 1}, None), ({"id": 1}, ""), ("invalid", "jwt")])
def test_restore_rejects_incomplete_session(monkeypatch, user, token):
    client, _, _ = _setup(monkeypatch, user, token)
    with pytest.raises(RuntimeError):
        session_restore.restore_session_worker(object())
    client.close.assert_called_once_with()
