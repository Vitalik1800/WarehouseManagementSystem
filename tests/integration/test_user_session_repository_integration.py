"""MySQL integration tests for refresh-token session persistence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.repositories.user_session_repository import UserSessionRepository


def _digest() -> str:
    return sha256(uuid4().bytes).hexdigest()


def _user_id(db_session: Session) -> int:
    # Create a disposable user inside the test's rollback-only transaction.
    # No password can be used to log in to this account.
    user = User(
        name='Session integration test',
        username=f'session_test_{uuid4().hex[:24]}',
        password_hash='!disabled-test-account!',
        role='worker',
        is_active=False,
    )
    db_session.add(user)
    db_session.flush()
    return user.id


def _create(db_session: Session, *, expires_at=None) -> tuple[UserSessionRepository, UserSession, str]:
    repo = UserSessionRepository(db_session)
    token_hash = _digest()
    session = repo.create(
        user_id=_user_id(db_session),
        refresh_token_hash=token_hash,
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(days=7),
    )
    return repo, session, token_hash


def test_create_and_lookup(db_session: Session):
    repo, session, token_hash = _create(db_session)
    assert session.id is not None
    assert db_session.get(UserSession, session.id) is not None
    assert repo.get_by_token_hash(token_hash).id == session.id
    assert repo.get_by_token_hash(_digest()) is None
    assert repo.get_valid_for_update(token_hash).id == session.id


def test_expired_session_is_invalid(db_session: Session):
    repo, session, token_hash = _create(
        db_session, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    assert repo.get_by_token_hash(token_hash).id == session.id
    assert repo.get_valid_for_update(token_hash) is None


def test_rotation_invalidates_old_hash(db_session: Session):
    repo, session, old_hash = _create(db_session)
    new_hash = _digest()
    locked = repo.get_valid_for_update(old_hash)
    assert locked is not None
    repo.rotate(locked, new_token_hash=new_hash)
    assert repo.get_by_token_hash(old_hash) is None
    assert repo.get_valid_for_update(old_hash) is None
    assert repo.get_valid_for_update(new_hash).id == session.id


def test_revoke_is_idempotent(db_session: Session):
    repo, session, token_hash = _create(db_session)
    repo.revoke(session)
    first_revocation = session.revoked_at
    assert first_revocation is not None
    assert repo.get_valid_for_update(token_hash) is None
    repo.revoke(session)
    assert session.revoked_at == first_revocation


@pytest.mark.parametrize('invalid_hash', ['', 'ABC', 'z' * 64, 'A' * 64])
def test_reject_invalid_hash_on_create(db_session: Session, invalid_hash: str):
    repo = UserSessionRepository(db_session)
    with pytest.raises(ValueError):
        repo.create(
            user_id=1, refresh_token_hash=invalid_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )


def test_reject_invalid_hash_on_rotation(db_session: Session):
    repo, session, original_hash = _create(db_session)
    with pytest.raises(ValueError):
        repo.rotate(session, new_token_hash='not-a-sha256-hash')
    assert repo.get_by_token_hash(original_hash).id == session.id


def test_reject_invalid_user_id(db_session: Session):
    repo = UserSessionRepository(db_session)
    with pytest.raises(ValueError):
        repo.create(
            user_id=0, refresh_token_hash=_digest(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
