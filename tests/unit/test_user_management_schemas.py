import pytest
from pydantic import ValidationError

from backend.app.schemas.users import (
    UserRoleUpdate,
    UserStatusUpdate,
    UserUpdate
)


def test_user_update_empty_payload():
    schema = UserUpdate()

    assert schema.model_dump(exclude_unset=True) == {}


def test_user_update_valid_fields():
    schema = UserUpdate(
        name="Test User",
        username="test_user"
    )

    assert schema.model_dump(exclude_unset=True) == {
        "name": "Test User",
        "username": "test_user"
    }


@pytest.mark.parametrize("field", ["name", "username"])
def test_user_update_rejects_explicit_null(field):
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({field: None})


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " "},
        {"name": "A"},
        {"username": "ab"},
        {"username": "invalid username"},
        {"username": "user!"}
    ]
)
def test_user_update_rejects_invalid_fields(payload):
    with pytest.raises(ValidationError):
        UserUpdate.model_validate(payload)


@pytest.mark.parametrize("role", ["admin", "worker"])
def test_user_role_update_valid(role):
    schema = UserRoleUpdate(role=role)

    assert schema.role == role


@pytest.mark.parametrize("role", ["manager", "guest", ""])
def test_user_role_update_rejects_invalid(role):
    with pytest.raises(ValidationError):
        UserRoleUpdate(role=role)


@pytest.mark.parametrize("is_active", [True, False])
def test_user_status_update_valid(is_active):
    schema = UserStatusUpdate(is_active=is_active)

    assert schema.is_active is is_active


def test_user_status_update_rejects_invalid_value():
    with pytest.raises(ValidationError):
        UserStatusUpdate(is_active="invalid")


@pytest.mark.parametrize(
    "field",
    ["role", "is_active", "password_hash", "password"]
)
def test_user_update_rejects_forbidden_fields(field):
    with pytest.raises(ValidationError) as exc_info:
        UserUpdate.model_validate({field: "test"})

    assert any(
        error["type"] == "extra_forbidden"
        for error in exc_info.value.errors()
    )


def test_user_update_rejects_mixed_allowed_and_forbidden_fields():
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({
            "name": "Updated User",
            "role": "admin"
        })
        