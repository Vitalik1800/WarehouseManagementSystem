
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.repositories.revoked_token_repository import (
    RevokedTokenRepository
)
from backend.app.services.auth_service import AuthService

from sqlalchemy import func, select

from backend.app.models.revoked_token import RevokedToken


def test_logout_saves_revoked_token_in_database(
    db_session: Session
):
    """Перевіряє збереження відкликаного JWT у MySQL."""
    service = AuthService(db_session)

    jti = str(uuid4())

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=1
    )

    token_payload = {
        "sub": "1",
        "jti": jti,
        "exp": int(expires_at.timestamp()),
        "type": "access"
    }

    service.logout(token_payload)

    repository = RevokedTokenRepository(db_session)

    revoked_token = repository.get_by_jti(jti)

    assert revoked_token is not None
    assert revoked_token.jti == jti
    assert repository.is_revoked(jti) is True


def test_logout_already_revoked_in_database(
    db_session: Session
):
    """Перевіряє повторне відкликання JWT у MySQL."""
    service = AuthService(db_session)

    jti = str(uuid4())

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=1
    )

    token_payload = {
        "sub": "1",
        "jti": jti,
        "exp": int(expires_at.timestamp()),
        "type": "access"
    }

    service.logout(token_payload)
    service.logout(token_payload)

    statement = select(func.count()).select_from(
        RevokedToken
    ).where(
        RevokedToken.jti == jti
    )

    token_count = db_session.scalar(statement)

    assert token_count == 1
