import pytest

from pydantic import ValidationError

from backend.app.schemas.users import UserCreate


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("name", "   ", "string_too_short"),
        ("username", "   ", "string_too_short")
    ],
)
def test_user_create_rejects_blank_values(
    field,
    value,
    expected_error,
):
    """Rejects fields containing only whitespace."""

    data = {
        "name": "Test User",
        "username": "test_user",
        "password": "SecurePassword123",
    }

    data[field] = value

    with pytest.raises(ValidationError) as exc_info:
        UserCreate(**data)

    errors = exc_info.value.errors()

    assert any(
        error["loc"] == (field,)
        and error["type"] == expected_error
        for error in errors
    )
