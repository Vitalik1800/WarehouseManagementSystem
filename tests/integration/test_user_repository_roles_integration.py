from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository


def test_count_active_admins(db_session):
    users = [
        User(
            name="Active Admin 1",
            username="role_test_admin_1",
            password_hash="test_hash",
            role="admin",
            is_active=True,
        ),
        User(
            name="Active Admin 2",
            username="role_test_admin_2",
            password_hash="test_hash",
            role="admin",
            is_active=True,
        ),
        User(
            name="Inactive Admin",
            username="role_test_admin_3",
            password_hash="test_hash",
            role="admin",
            is_active=False,
        ),
        User(
            name="Active Worker",
            username="role_test_worker_1",
            password_hash="test_hash",
            role="worker",
            is_active=True,
        ),
        User(
            name="Inactive Worker",
            username="role_test_worker_2",
            password_hash="test_hash",
            role="worker",
            is_active=False,
        ),
    ]

    db_session.add_all(users)
    db_session.flush()

    repository = UserRepository(db_session)

    assert repository.count_active_admins() == 2
