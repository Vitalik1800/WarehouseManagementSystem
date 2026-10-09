from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import get_settings


def test_root_endpoint():
    """Checks the root API endpoint."""

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["application"] == get_settings().app_name
    assert data["version"] == app.version
    assert data["message"] == "API системи управління складом"


def test_health_endpoint():
    """Checks the API health endpoint."""

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "service": "backend",
    }
