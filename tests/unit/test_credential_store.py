"""Tests use a fake backend; no real Windows credentials are accessed."""
from unittest.mock import Mock

import pytest

from frontend.app.services.credential_store import CredentialStore, CredentialStoreError


def test_save_load_delete():
    data = {}
    backend = Mock()
    backend.set_password.side_effect = lambda service, account, value: data.__setitem__((service, account), value)
    backend.get_password.side_effect = lambda service, account: data.get((service, account))
    backend.delete_password.side_effect = lambda service, account: data.pop((service, account))
    store = CredentialStore(backend=backend)
    assert store.load() is None
    store.save("secret-refresh-token")
    assert store.load() == "secret-refresh-token"
    store.delete()
    assert store.load() is None


def test_delete_missing_is_safe():
    backend = Mock()
    backend.get_password.return_value = None
    CredentialStore(backend=backend).delete()
    backend.delete_password.assert_not_called()


@pytest.mark.parametrize("token", ["", "  ", None, 123])
def test_reject_invalid_tokens(token):
    backend = Mock()
    with pytest.raises(ValueError):
        CredentialStore(backend=backend).save(token)
    backend.set_password.assert_not_called()


def test_backend_error_is_wrapped():
    backend = Mock()
    backend.get_password.side_effect = RuntimeError("test failure")
    with pytest.raises(CredentialStoreError):
        CredentialStore(backend=backend).load()


def test_backend_save_error_is_wrapped():
    backend = Mock()
    backend.set_password.side_effect = RuntimeError("test failure")
    with pytest.raises(CredentialStoreError):
        CredentialStore(backend=backend).save("token")


def test_backend_delete_error_is_wrapped():
    backend = Mock()
    backend.get_password.return_value = "token"
    backend.delete_password.side_effect = RuntimeError("test failure")
    with pytest.raises(CredentialStoreError):
        CredentialStore(backend=backend).delete()
