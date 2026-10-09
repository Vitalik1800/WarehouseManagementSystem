import jwt
import pytest

from jwt.exceptions import InvalidSignatureError

from backend.app.core.security import (
    create_access_token,
    decode_access_token,
)

from datetime import datetime, timedelta, timezone

from backend.app.core.config import get_settings


def test_jwt_rejects_forged_signature():
    """JWT signed with another secret must be rejected."""

    valid_token = create_access_token(user_id=1)

    forged_payload = jwt.decode(
        valid_token,
        options={"verify_signature": False},
    )

    forged_token = jwt.encode(
        forged_payload,
        "attacker-controlled-secret-key-for-security-testing-2026",
        algorithm="HS256",
    )

    with pytest.raises(InvalidSignatureError):
        decode_access_token(forged_token)


def test_jwt_rejects_none_algorithm():
    """JWT without a cryptographic signature must be rejected."""

    valid_token = create_access_token(user_id=1)

    payload = jwt.decode(
        valid_token,
        options={"verify_signature": False},
    )

    unsigned_token = jwt.encode(
        payload,
        key="",
        algorithm="none",
    )

    with pytest.raises(jwt.exceptions.InvalidAlgorithmError):
        decode_access_token(unsigned_token)


def test_jwt_rejects_expired_token():
    """Expired JWT access tokens must be rejected."""

    settings = get_settings()

    now = datetime.now(timezone.utc)

    payload = {
        "sub": "1",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "jti": "expired-token-test-id",
        "type": "access",
    }

    expired_token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.exceptions.ExpiredSignatureError):
        decode_access_token(expired_token)


@pytest.mark.parametrize(
    "missing_claim",
    ["sub", "iat", "exp", "jti", "type"],
)
def test_jwt_rejects_missing_required_claim(missing_claim):
    """JWT must contain all required claims."""

    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload = {
        "sub": "1",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": "missing-claim-test-id",
        "type": "access",
    }

    del payload[missing_claim]

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.exceptions.MissingRequiredClaimError) as exc_info:
        decode_access_token(token)

    assert exc_info.value.claim == missing_claim


@pytest.mark.parametrize(
    "token_type",
    ["refresh", "reset_password", "invalid", ""],
)
def test_jwt_rejects_invalid_token_type(token_type):
    """Only access tokens must be accepted."""

    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload = {
        "sub": "1",
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": "invalid-token-type-test-id",
        "type": token_type,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.exceptions.InvalidTokenError):
        decode_access_token(token)
