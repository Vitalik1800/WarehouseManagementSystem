"""Opaque rotating refresh tokens for persistent user sessions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy.orm import Session

from backend.app.core.security import create_access_token
from backend.app.models.user import User
from backend.app.repositories.user_session_repository import UserSessionRepository


REFRESH_TOKEN_LIFETIME = timedelta(days=30)


class InvalidRefreshTokenError(Exception):
    """Refresh token is missing, expired, revoked, or belongs to an inactive user."""


@dataclass(frozen=True)
class RefreshedTokens:
    access_token: str
    refresh_token: str


def _token_hash(token: str) -> str:
    if not isinstance(token, str) or not token or len(token) > 512:
        raise InvalidRefreshTokenError('Invalid refresh token')
    return sha256(token.encode('utf-8')).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(48)


class RefreshTokenService:
    """Transaction-owning refresh session service.

    Never log or persist raw refresh tokens. The caller must deliver the raw
    token over a protected channel and store it securely on the client.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = UserSessionRepository(db)

    def issue(self, user_id: int) -> str:
        """Create a new session after successful password authentication."""
        user = self.db.get(User, user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError('Inactive or missing user')
        token = _new_token()
        try:
            self.sessions.create(
                user_id=user_id,
                refresh_token_hash=_token_hash(token),
                expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_LIFETIME,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return token

    def refresh(self, token: str) -> RefreshedTokens:
        """Atomically consume the old token and rotate to a new one."""
        digest = _token_hash(token)
        try:
            session = self.sessions.get_valid_for_update(digest)
            if session is None:
                raise InvalidRefreshTokenError('Invalid refresh token')
            user = self.db.get(User, session.user_id)
            if user is None or not user.is_active:
                raise InvalidRefreshTokenError('Inactive or missing user')
            new_token = _new_token()
            self.sessions.rotate(session, new_token_hash=_token_hash(new_token))
            access_token = create_access_token(user_id=user.id)
            self.db.commit()
            return RefreshedTokens(access_token=access_token, refresh_token=new_token)
        except Exception:
            self.db.rollback()
            raise

    def revoke(self, token: str) -> bool:
        """Revoke the session associated with a token; return False if unknown."""
        digest = _token_hash(token)
        try:
            session = self.sessions.get_by_token_hash(digest, for_update=True)
            if session is None:
                self.db.rollback()
                return False
            self.sessions.revoke(session)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
