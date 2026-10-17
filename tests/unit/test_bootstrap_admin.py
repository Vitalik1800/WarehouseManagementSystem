from unittest.mock import MagicMock, patch

import pytest

from scripts.bootstrap_admin import (
    bootstrap_admin,
    has_active_admin,
    read_admin_credentials
)

from sqlalchemy.exc import IntegrityError


@pytest.fixture
def repository():
    return MagicMock()


def test_has_active_admin_true(repository):
    repository.count_active_admins.return_value = 1

    assert has_active_admin(repository) is True


def test_has_active_admin_false(repository):
    repository.count_active_admins.return_value = 0

    assert has_active_admin(repository) is False


@patch("scripts.bootstrap_admin.getpass.getpass")
@patch("builtins.input")
def test_read_admin_credentials(mock_input, mock_getpass):
    mock_input.side_effect = [
        " Test Administrator ",
        " admin_01 "
    ]
    mock_getpass.side_effect = [
        "SecurePassword123!",
        "SecurePassword123!"
    ]

    assert read_admin_credentials() == (
        "Test Administrator",
        "admin_01",
        "SecurePassword123!"
    )


@pytest.mark.parametrize(
    "name,username",
    [
        ("A", "admin_01"),
        ("", "admin_01"),
        ("Test Administrator", "ab"),
        ("Test Administrator", "invalid username"),
        ("Test Administrator", "admin-name")
    ]
)
@patch("builtins.input")
def test_read_admin_credentials_invalid_identity(
    mock_input,
    name,
    username
):
    mock_input.side_effect = [name, username]

    with pytest.raises(ValueError):
        read_admin_credentials()


@patch("scripts.bootstrap_admin.getpass.getpass")
@patch("builtins.input")
def test_read_admin_credentials_password_mismatch(
    mock_input,
    mock_getpass
):
    mock_input.side_effect = ["Administrator", "admin_01"]
    mock_getpass.side_effect = [
        "SecurePassword123!",
        "DifferentPassword123!"
    ]

    with pytest.raises(ValueError, match="Passwords do not match"):
        read_admin_credentials()


@patch("scripts.bootstrap_admin.getpass.getpass")
@patch("builtins.input")
def test_read_admin_credentials_short_password(
    mock_input,
    mock_getpass
):
    mock_input.side_effect = ["Administrator", "admin_01"]
    mock_getpass.side_effect = ["short", "short"]

    with pytest.raises(ValueError, match="8-128"):
        read_admin_credentials()


@patch("scripts.bootstrap_admin.SessionLocal")
def test_bootstrap_rejects_existing_active_admin(mock_session_local):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    with patch(
        "scripts.bootstrap_admin.UserRepository"
    ) as mock_repository_class:
        repository = mock_repository_class.return_value
        repository.count_active_admins.return_value = 1

        result = bootstrap_admin()

    assert result == 1
    repository.create.assert_not_called()
    db.commit.assert_not_called()


@patch("scripts.bootstrap_admin.hash_password")
@patch("scripts.bootstrap_admin.read_admin_credentials")
@patch("scripts.bootstrap_admin.SessionLocal")
def test_bootstrap_creates_admin(
    mock_session_local,
    mock_credentials,
    mock_hash_password
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    mock_credentials.return_value = (
        "Test Administrator",
        "admin_01",
        "SecurePassword123!"
    )
    mock_hash_password.return_value = "hashed_password"

    with patch(
        "scripts.bootstrap_admin.UserRepository"
    ) as mock_repository_class:
        repository = mock_repository_class.return_value
        repository.count_active_admins.return_value = 0
        repository.get_by_username.return_value = None
        repository.create.return_value.username = "admin_01"

        result = bootstrap_admin()

    assert result == 0

    repository.create.assert_called_once_with(
        name="Test Administrator",
        username="admin_01",
        password_hash="hashed_password",
        role="admin"
    )

    db.commit.assert_called_once()


@patch("scripts.bootstrap_admin.read_admin_credentials")
@patch("scripts.bootstrap_admin.SessionLocal")
def test_bootstrap_rejects_duplicate_username(
    mock_session_local,
    mock_credentials
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    mock_credentials.return_value = (
        "Test Administrator",
        "admin_01",
        "SecurePassword123!"
    )

    with patch(
        "scripts.bootstrap_admin.UserRepository"
    ) as mock_repository_class:
        repository = mock_repository_class.return_value
        repository.count_active_admins.return_value = 0
        repository.get_by_username.return_value = object()

        result = bootstrap_admin()

    assert result == 1
    repository.create.assert_not_called()
    db.rollback.assert_called_once()


@patch("scripts.bootstrap_admin.read_admin_credentials")
@patch("scripts.bootstrap_admin.SessionLocal")
def test_bootstrap_rechecks_active_admin(
    mock_session_local,
    mock_credentials
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    mock_credentials.return_value = (
        "Test Administrator",
        "admin_01",
        "SecurePassword123!"
    )

    with patch(
        "scripts.bootstrap_admin.UserRepository"
    ) as mock_repository_class:
        repository = mock_repository_class.return_value
        repository.count_active_admins.side_effect = [0, 1]
        repository.get_by_username.return_value = None

        result = bootstrap_admin()

    assert result == 1
    repository.create.assert_not_called()
    db.commit.assert_not_called()


@patch("scripts.bootstrap_admin.hash_password")
@patch("scripts.bootstrap_admin.read_admin_credentials")
@patch("scripts.bootstrap_admin.SessionLocal")
def test_bootstrap_rolls_back_on_integrity_error(
    mock_session_local,
    mock_credentials,
    mock_hash_password
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    mock_credentials.return_value = (
        "Test Administrator",
        "admin_01",
        "SecurePassword123!"
    )
    mock_hash_password.return_value = "hashed_password"

    with patch(
        "scripts.bootstrap_admin.UserRepository"
    ) as mock_repository_class:
        repository = mock_repository_class.return_value
        repository.count_active_admins.return_value = 0
        repository.get_by_username.return_value = None
        repository.create.side_effect = IntegrityError(
            statement="INSERT INTO users",
            params={},
            orig=Exception("Duplicate entry")
        )

        result = bootstrap_admin()

    assert result == 1
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@patch("scripts.bootstrap_admin.read_admin_credentials")
@patch("scripts.bootstrap_admin.SessionLocal")
def test_bootstrap_rolls_back_on_invalid_credentials(
    mock_session_local,
    mock_credentials
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db
    mock_credentials.side_effect = ValueError(
        "Passwords do not match."
    )

    with patch(
        "scripts.bootstrap_admin.UserRepository"
    ) as mock_repository_class:
        repository = mock_repository_class.return_value
        repository.count_active_admins.return_value = 0

        result = bootstrap_admin()

    assert result == 1
    repository.create.assert_not_called()
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
