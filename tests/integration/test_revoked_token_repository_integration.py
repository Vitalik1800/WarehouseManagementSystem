from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.revoked_token import RevokedToken
from backend.app.repositories.revoked_token_repository import (
    RevokedTokenRepository
)


def test_create_revoked_token_in_database(db_session: Session):
    """Перевіряє збереження відкликаного JWT у MySQL."""
    jti = str(uuid4())

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    repository = RevokedTokenRepository(db_session)

    created_token = repository.create(
        jti=jti,
        expires_at=expires_at
    )

    assert isinstance(created_token, RevokedToken)
    assert created_token.id is not None
    assert created_token.jti == jti

    saved_token = db_session.get(
        RevokedToken,
        created_token.id
    )

    assert saved_token is not None
    assert saved_token.jti == jti
    assert saved_token.expires_at is not None


def test_get_revoked_token_by_jti_in_database(db_session: Session):
    """Перевіряє пошук відкликаного JWT за JTI у MySQL."""
    jti = str(uuid4())

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    repository = RevokedTokenRepository(db_session)

    created_token = repository.create(
        jti=jti,
        expires_at=expires_at
    )

    found_token = repository.get_by_jti(jti)

    assert found_token is not None
    assert isinstance(found_token, RevokedToken)

    assert found_token.id == created_token.id
    assert found_token.jti == jti


def test_get_revoked_token_by_jti_not_found_in_database(
    db_session: Session
):
    """Перевіряє пошук неіснуючого JTI у MySQL."""
    jti = str(uuid4())

    repository = RevokedTokenRepository(db_session)

    found_token = repository.get_by_jti(jti)

    assert found_token is None


def test_is_revoked_true_in_database(db_session: Session):
    """Перевіряє виявлення відкликаного JWT у MySQL."""
    jti = str(uuid4())

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    repository = RevokedTokenRepository(db_session)

    repository.create(
        jti=jti,
        expires_at=expires_at
    )

    result = repository.is_revoked(jti)

    assert result is True


def test_is_revoked_false_in_database(db_session: Session):
    """Перевіряє невідкликаний JWT у MySQL."""
    jti = str(uuid4())

    repository = RevokedTokenRepository(db_session)

    result = repository.is_revoked(jti)

    assert result is False
