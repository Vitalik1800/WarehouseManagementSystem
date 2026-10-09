from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies.auth import get_current_user
from backend.app.core.permissions import require_roles
from backend.app.models.user import User


def test_admin_only_endpoint():
    """Перевіряє RBAC через механізм залежностей FastAPI."""

    app = FastAPI()

    @app.get("/admin-only")
    def admin_only(
        user: User = Depends(require_roles("admin"))
    ):
        return {
            "message": "Access granted",
            "role": user.role
        }

    client = TestClient(app)

    admin = User(
        id=1,
        name="Administrator",
        username="admin_test",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    worker = User(
        id=2,
        name="Worker",
        username="worker_test",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    try:
        app.dependency_overrides[get_current_user] = lambda: admin

        response = client.get("/admin-only")

        assert response.status_code == 200
        assert response.json() == {
            "message": "Access granted",
            "role": "admin"
        }

        app.dependency_overrides[get_current_user] = lambda: worker

        response = client.get("/admin-only")

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Недостатньо прав для виконання цієї дії"
        }
    finally:
        app.dependency_overrides.clear()
