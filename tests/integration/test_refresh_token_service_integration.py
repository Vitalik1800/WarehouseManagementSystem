"""Refresh service integration checks against warehouse_test_db only."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.services.refresh_token_service import (
    InvalidRefreshTokenError, RefreshTokenService,
)


@pytest.fixture
def active_test_user(test_engine):
    """Committed fixture for a service that owns its transactions; cleaned up afterward."""
    username = f'refresh_test_{uuid4().hex[:20]}'
    with Session(test_engine) as db:
        user = User(name='Refresh integration test', username=username,
                    password_hash='!disabled-test-account!', role='worker', is_active=True)
        db.add(user)
        db.commit()
        user_id = user.id
    try:
        yield user_id
    finally:
        with Session(test_engine) as db:
            # FK ON DELETE CASCADE deletes the test user's sessions.
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


def test_issue_persists_only_hash(test_engine, active_test_user):
    with Session(test_engine) as db:
        token = RefreshTokenService(db).issue(active_test_user)
        assert isinstance(token, str) and len(token) >= 40
        digest = sha256(token.encode()).hexdigest()
        saved = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == digest))
        assert saved is not None
        assert saved.user_id == active_test_user
        assert saved.refresh_token_hash != token
        assert saved.revoked_at is None
        assert saved.expires_at > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=29)


def test_refresh_rotates_and_rejects_old_token(test_engine, active_test_user):
    with Session(test_engine) as db:
        service = RefreshTokenService(db)
        original = service.issue(active_test_user)
        original_hash = sha256(original.encode()).hexdigest()
        old_expiry = db.scalar(select(UserSession.expires_at).where(UserSession.refresh_token_hash == original_hash))
        refreshed = service.refresh(original)
        assert refreshed.refresh_token != original
        assert decode_access_token(refreshed.access_token)['sub'] == str(active_test_user)
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(original)
        new_hash = sha256(refreshed.refresh_token.encode()).hexdigest()
        session = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == new_hash))
        assert session is not None
        assert session.expires_at == old_expiry
        assert service.refresh(refreshed.refresh_token).refresh_token != refreshed.refresh_token


def test_revoke_blocks_refresh(test_engine, active_test_user):
    with Session(test_engine) as db:
        service = RefreshTokenService(db)
        token = service.issue(active_test_user)
        assert service.revoke(token) is True
        assert service.revoke(token) is True  # idempotent at service level
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(token)
        assert service.revoke('unknown-token') is False


def test_expired_token_rejected(test_engine, active_test_user):
    with Session(test_engine) as db:
        service = RefreshTokenService(db)
        token = service.issue(active_test_user)
        session = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == sha256(token.encode()).hexdigest()))
        session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(token)


def test_inactive_user_rejected(test_engine, active_test_user):
    with Session(test_engine) as db:
        service = RefreshTokenService(db)
        token = service.issue(active_test_user)
        user = db.get(User, active_test_user)
        user.is_active = False
        db.commit()
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(token)
        with pytest.raises(InvalidRefreshTokenError):
            service.issue(active_test_user)


@pytest.mark.parametrize('token', ['', 'x' * 513, None])
def test_malformed_token_rejected(test_engine, token):
    with Session(test_engine) as db:
        service = RefreshTokenService(db)
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(token)
        with pytest.raises(InvalidRefreshTokenError):
            service.revoke(token)
