"""Two-connection MySQL test of refresh token rotation."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Event
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.repositories.user_session_repository import UserSessionRepository


def _digest():
    return sha256(uuid4().bytes).hexdigest()


def test_concurrent_refresh_rotation_only_one_wins(test_engine):
    """Second transaction cannot reuse a hash after first commits rotation."""
    old_hash, new_hash = _digest(), _digest()
    username = 'session_race_' + uuid4().hex[:24]
    user_id = None
    locked = Event()
    second_started = Event()
    release_first = Event()

    # The setup must be committed so both independent connections can see it.
    with Session(test_engine) as setup:
        user = User(
            name='Session concurrency test', username=username,
            password_hash='!disabled-test-account!', role='worker',
            is_active=False,
        )
        setup.add(user)
        setup.flush()
        user_id = user.id
        UserSessionRepository(setup).create(
            user_id=user_id, refresh_token_hash=old_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        setup.commit()

    def first_transaction():
        with Session(test_engine) as db:
            repo = UserSessionRepository(db)
            record = repo.get_valid_for_update(old_hash)
            assert record is not None
            locked.set()
            assert release_first.wait(10), 'Timed out waiting to release first lock'
            repo.rotate(record, new_token_hash=new_hash)
            db.commit()
            return True

    def second_transaction():
        assert locked.wait(10), 'First transaction never acquired row lock'
        second_started.set()
        with Session(test_engine) as db:
            repo = UserSessionRepository(db)
            record = repo.get_valid_for_update(old_hash)
            if record is None:
                db.rollback()
                return False
            repo.rotate(record, new_token_hash=_digest())
            db.commit()
            return True

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_transaction)
            second = pool.submit(second_transaction)
            try:
                assert locked.wait(10), 'First transaction did not lock session'
                assert second_started.wait(10), 'Second transaction did not start'
                # Ensure the second request has not completed while the first
                # transaction owns the row lock. This is a synchronization check,
                # not a benchmark of exact lock acquisition timing.
                try:
                    second.result(timeout=0.3)
                except FutureTimeout:
                    pass
                else:
                    raise AssertionError('Second transaction finished before lock release')
            finally:
                release_first.set()
            assert first.result(timeout=15) is True
            assert second.result(timeout=15) is False

        with Session(test_engine) as db:
            repo = UserSessionRepository(db)
            assert repo.get_by_token_hash(old_hash) is None
            assert repo.get_valid_for_update(new_hash) is not None
            db.rollback()
    finally:
        release_first.set()
        if user_id is not None:
            # CASCADE removes the associated session; only our test user is deleted.
            with Session(test_engine) as cleanup:
                cleanup.execute(delete(UserSession).where(UserSession.user_id == user_id))
                cleanup.execute(delete(User).where(User.id == user_id, User.username == username))
                cleanup.commit()
