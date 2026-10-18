from unittest.mock import Mock
import pytest
from frontend.app.services.warehouse_service import WarehouseClientService, WarehouseClientServiceError

@pytest.fixture
def client():
    obj = Mock()
    obj.is_authenticated = True
    return obj

def warehouse():
    return {"id": 1, "name": "Основний", "code": "MAIN", "description": None, "is_active": True}

def test_list(client):
    client.get.return_value = [warehouse()]
    assert WarehouseClientService(client).list_warehouses() == [warehouse()]
    client.get.assert_called_once_with("/warehouses", params={"offset": 0, "limit": 50})

def test_create(client):
    client.post.return_value = warehouse()
    WarehouseClientService(client).create_warehouse(" Основний ", " MAIN ", None, True)
    client.post.assert_called_once_with("/warehouses", json={"name": "Основний", "code": "MAIN", "description": None, "is_active": True})

def test_update(client):
    client.patch.return_value = warehouse()
    assert WarehouseClientService(client).update_warehouse(1, "Основний", "MAIN", None, True)["id"] == 1

def test_delete(client):
    WarehouseClientService(client).delete_warehouse(1)
    client.delete.assert_called_once_with("/warehouses/1")

def test_auth(client):
    client.is_authenticated = False
    with pytest.raises(WarehouseClientServiceError):
        WarehouseClientService(client).list_warehouses()

def test_invalid_response(client):
    client.get.return_value = [{"id": True}]
    with pytest.raises(WarehouseClientServiceError):
        WarehouseClientService(client).list_warehouses()

def test_invalid_input(client):
    with pytest.raises(ValueError):
        WarehouseClientService(client).create_warehouse("", "X", None, True)
    with pytest.raises(ValueError):
        WarehouseClientService(client).delete_warehouse(0)
