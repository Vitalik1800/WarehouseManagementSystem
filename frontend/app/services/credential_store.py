"""Refresh token storage using the native Windows Credential Manager only."""
import sys

import keyring
import keyring.backends.Windows
from keyring.backends.fail import Keyring as FailKeyring


class CredentialStoreError(RuntimeError):
    """Secure storage is not available or an operation failed."""


class CredentialStore:
    SERVICE_NAME = "WarehouseManagementSystem.RefreshToken.v1"
    ACCOUNT_NAME = "current-user"

    def __init__(self, backend=None):
        # Dependency injection is intended for tests only.
        self._backend = backend

    def _get_backend(self):
        if self._backend is not None:
            return self._backend
        if sys.platform != "win32":
            raise CredentialStoreError("Windows Credential Manager is required")
        try:
            backend = keyring.get_keyring()
        except Exception as exc:
            raise CredentialStoreError("Unable to initialize secure storage") from exc
        # Fail closed: never silently use plaintext/file/third-party keyring backends.
        if not isinstance(backend, keyring.backends.Windows.WinVaultKeyring):
            raise CredentialStoreError("Native Windows Credential Manager backend is required")
        return backend

    def load(self) -> str | None:
        try:
            value = self._get_backend().get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("Unable to read secure session") from exc
        return value if isinstance(value, str) and value else None

    def save(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Refresh token cannot be empty")
        try:
            self._get_backend().set_password(self.SERVICE_NAME, self.ACCOUNT_NAME, token)
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("Unable to save secure session") from exc

    def delete(self) -> None:
        try:
            backend = self._get_backend()
            if backend.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME) is not None:
                backend.delete_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("Unable to delete secure session") from exc
