from backend.app.core.security import verify_password
from backend.app.models.user import User
from tests.helpers.users import create_test_user


def test_create_test_user(db_session):
    user = create_test_user(
        db_session,
        name="Warehouse Worker",
        username="factory_worker",
        password="SecurePassword123!"
    )

    assert user.id is not None
    assert user.name == "Warehouse Worker"
    assert user.username == "factory_worker"
    assert user.role == "worker"
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(
        "SecurePassword123!",
        user.password_hash
    )

    saved_user = db_session.get(User, user.id)

    assert saved_user is not None
    assert saved_user.id == user.id


def test_create_inactive_admin(db_session):
    user = create_test_user(
        db_session,
        name="Inactive Administrator",
        role="admin",
        is_active=False
    )

    assert user.role == "admin"
    assert user.is_active is False
