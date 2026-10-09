from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.app.api.dependencies.auth import get_token_payload


def test_get_token_payload_rejects_nonpositive_user_id():
    """Rejects a JWT payload with a nonpositive user ID."""

    db = Mock()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test.jwt.token",
    )

    payload = {
        "sub": "0",
        "jti": "test-jti",
        "exp": 2000000000,
    }

    with patch(
        "backend.app.api.dependencies.auth.decode_access_token",
        return_value=payload,
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_token_payload(
                credentials=credentials,
                db=db,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer"
    }


@pytest.mark.parametrize(
    ("jti", "expiration"),
    [
        (None, 2000000000),
        ("", 2000000000),
        ("valid-jti", "2000000000"),
    ],
)
def test_get_token_payload_rejects_invalid_claims(
    jti,
    expiration,
):
    """Rejects invalid JWT claims."""

    db = Mock()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test.jwt.token",
    )

    payload = {
        "sub": "42",
        "jti": jti,
        "exp": expiration,
    }

    with patch(
        "backend.app.api.dependencies.auth.decode_access_token",
        return_value=payload,
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_token_payload(
                credentials=credentials,
                db=db,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer"
    }
