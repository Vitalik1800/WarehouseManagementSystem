from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from jwt.exceptions import InvalidTokenError

from backend.app.core.config import get_settings
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
)


def make_token(payload: dict, secret: str | None = None) -> str:
    settings = get_settings()

    return jwt.encode(
        payload,
        secret or settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def valid_payload() -> dict:
    now = datetime.now(timezone.utc)

    return {
        "sub": "1",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": str(uuid4()),
        "type": "access",
    }


def test_create_and_decode_access_token():
    token = create_access_token(1)
    payload = decode_access_token(token)

    assert payload["sub"] == "1"
    assert payload["type"] == "access"
    assert payload["jti"]
    assert payload["exp"] > payload["iat"]


def test_tokens_have_unique_jti():
    first = decode_access_token(create_access_token(1))
    second = decode_access_token(create_access_token(1))

    assert first["jti"] != second["jti"]


@pytest.mark.parametrize("user_id", [0, -1])
def test_invalid_user_id_rejected(user_id):
    with pytest.raises(ValueError):
        create_access_token(user_id)


def test_expired_token_rejected():
    payload = valid_payload()
    payload["exp"] = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )

    token = make_token(payload)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_wrong_signature_rejected():
    token = make_token(
        valid_payload(),
        secret="incorrect-secret-key-for-testing-only",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "missing_field",
    ["sub", "iat", "exp", "jti", "type"],
)
def test_missing_required_claim_rejected(missing_field):
    payload = valid_payload()
    payload.pop(missing_field)

    token = make_token(payload)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "invalid_sub",
    ["0", "-1", "abc", ""],
)
def test_invalid_subject_rejected(invalid_sub):
    payload = valid_payload()
    payload["sub"] = invalid_sub

    token = make_token(payload)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_invalid_token_type_rejected():
    payload = valid_payload()
    payload["type"] = "refresh"

    token = make_token(payload)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_empty_jti_rejected():
    payload = valid_payload()
    payload["jti"] = ""

    token = make_token(payload)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_malformed_token_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token("invalid.jwt.token")
