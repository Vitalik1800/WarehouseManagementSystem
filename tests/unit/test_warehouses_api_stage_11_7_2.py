from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.api.dependencies.auth import get_current_user
from backend.app.services.warehouse_service import (
    WarehouseService, WarehouseNotFoundError, WarehouseAlreadyExistsError, WarehouseInUseError
)


def warehouse(**overrides):
    data = dict(id=1, name="Central", code="CENTRAL", description=None, is_active=True)
    data.update(overrides)
    return type("WarehouseStub", (), data)()


@pytest.fixture
def api(monkeypatch):
    service = MagicMock(spec=WarehouseService)
    service.list_warehouses.return_value = [warehouse()]
    service.get_warehouse.return_value = warehouse()
    service.create_warehouse.return_value = warehouse()
    service.update_warehouse.return_value = warehouse(name="Updated")
    monkeypatch.setattr("backend.app.api.routers.warehouses.WarehouseService", lambda db: service)
    role = {"value": "admin"}
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: type("UserStub", (), {"role": role["value"]})()
    try:
        with TestClient(app) as client:
            yield client, service, role
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_list_and_get_for_worker(api):
    client, service, role = api
    role["value"] = "worker"
    assert client.get("/warehouses").status_code == 200
    assert client.get("/warehouses/1").json()["code"] == "CENTRAL"
    service.list_warehouses.assert_called_with(offset=0, limit=50)


def test_worker_cannot_mutate(api):
    client, _, role = api
    role["value"] = "worker"
    assert client.post("/warehouses", json={"name": "A", "code": "A"}).status_code == 403
    assert client.patch("/warehouses/1", json={"name": "B"}).status_code == 403
    assert client.delete("/warehouses/1").status_code == 403


def test_admin_create_update_delete(api):
    client, service, _ = api
    assert client.post("/warehouses", json={"name": " Central ", "code": " CENTRAL "}).status_code == 201
    assert service.create_warehouse.call_args.args[0].name == "Central"
    assert client.patch("/warehouses/1", json={"name": "Updated"}).status_code == 200
    assert client.delete("/warehouses/1").status_code == 204
    service.delete_warehouse.assert_called_once_with(1)


def test_validation_and_pagination(api):
    client, _, _ = api
    assert client.get("/warehouses?limit=101").status_code == 422
    assert client.get("/warehouses?offset=-1").status_code == 422
    assert client.get("/warehouses/0").status_code == 422
    assert client.post("/warehouses", json={"name": " ", "code": "X"}).status_code == 422
    assert client.patch("/warehouses/1", json={"is_active": None}).status_code == 422


def test_missing_and_conflict(api):
    client, service, _ = api
    service.get_warehouse.side_effect = WarehouseNotFoundError("missing")
    assert client.get("/warehouses/999").status_code == 404
    service.update_warehouse.side_effect = WarehouseNotFoundError("missing")
    assert client.patch("/warehouses/999", json={"name": "New"}).status_code == 404
    service.create_warehouse.side_effect = WarehouseAlreadyExistsError("duplicate")
    assert client.post("/warehouses", json={"name": "A", "code": "A"}).status_code == 409
    service.delete_warehouse.side_effect = WarehouseInUseError("in use")
    assert client.delete("/warehouses/1").status_code == 409
