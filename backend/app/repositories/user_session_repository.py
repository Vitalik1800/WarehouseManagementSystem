"""Persistence operations for long-lived user sessions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user_session import UserSession


def _utc_naive(value: datetime) -> datetime:
    """Normalize timestamps for MySQL DATETIME comparisons."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None)


class UserSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, user_id: int, refresh_token_hash: str,
               expires_at: datetime) -> UserSession:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        if len(refresh_token_hash) != 64 or any(c not in "0123456789abcdef" for c in refresh_token_hash):
            raise ValueError("refresh_token_hash must be a lowercase SHA-256 hex digest")
        session = UserSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            created_at=datetime.now(timezone.utc),
            expires_at=_utc_naive(expires_at),
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_by_token_hash(self, refresh_token_hash: str, *,
                          for_update: bool = False) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.refresh_token_hash == refresh_token_hash
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def get_valid_for_update(self, refresh_token_hash: str, *,
                             now: datetime | None = None) -> UserSession | None:
        """Lock an active, unexpired session for atomic token rotation."""
        current = _utc_naive(now or datetime.now(timezone.utc))
        stmt = (select(UserSession)
                .where(UserSession.refresh_token_hash == refresh_token_hash,
                       UserSession.revoked_at.is_(None),
                       UserSession.expires_at > current)
                .with_for_update())
        return self.db.scalar(stmt)

    def rotate(self, session: UserSession, *, new_token_hash: str) -> None:
        """Update the token hash inside the caller's transaction."""
        if len(new_token_hash) != 64 or any(c not in "0123456789abcdef" for c in new_token_hash):
            raise ValueError("new_token_hash must be a lowercase SHA-256 hex digest")
        session.refresh_token_hash = new_token_hash
        self.db.flush()

    def revoke(self, session: UserSession, *, now: datetime | None = None) -> None:
        if session.revoked_at is None:
            session.revoked_at = _utc_naive(now or datetime.now(timezone.utc))
            self.db.flush()
