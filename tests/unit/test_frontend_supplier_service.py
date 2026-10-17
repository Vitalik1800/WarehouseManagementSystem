"""Supplier frontend contract tests (no real network)."""
from unittest.mock import Mock
import pytest
from frontend.app.services.supplier_service import SupplierService, SupplierServiceError

DATA = {'id': 3, 'name': 'Постачальник', 'contact_person': 'Олена', 'phone': '+380123',
        'email': 'test@example.com', 'address': 'Київ'}

@pytest.fixture
def pair():
    api = Mock()
    api.is_authenticated = True
    return SupplierService(api), api

def test_list_pagination(pair):
    service, api = pair
    api.get.return_value = [DATA]
    assert service.list_suppliers(25, 26) == [DATA]
    api.get.assert_called_once_with('/suppliers', params={'offset': 25, 'limit': 26})

@pytest.mark.parametrize('offset,limit', [(-1, 1), (0, 0), (0, 101), (True, 5), (0, False)])
def test_invalid_pagination(pair, offset, limit):
    with pytest.raises(ValueError):
        pair[0].list_suppliers(offset, limit)

@pytest.mark.parametrize('response', [None, {}, [DATA] * 2, [{'id': 3}], [{**DATA, 'id': True}],
                                      [{**DATA, 'name': ''}], [{**DATA, 'phone': 123}]])
def test_invalid_response(pair, response):
    service, api = pair
    api.get.return_value = response
    with pytest.raises(SupplierServiceError):
        service.list_suppliers(limit=1)

def test_get_supplier(pair):
    service, api = pair
    api.get.return_value = DATA
    assert service.get_supplier(3) == DATA
    api.get.assert_called_once_with('/suppliers/3')

def test_get_wrong_id(pair):
    service, api = pair
    api.get.return_value = DATA
    with pytest.raises(SupplierServiceError):
        service.get_supplier(2)

def test_create_payload(pair):
    service, api = pair
    api.post.return_value = DATA
    service.create_supplier('  Постачальник  ', 'Олена', '+380123', 'test@example.com', 'Київ')
    assert api.post.call_args.kwargs['json']['name'] == 'Постачальник'

def test_update_clear_optional_fields(pair):
    service, api = pair
    api.patch.return_value = DATA
    service.update_supplier(3, phone=None, email=None, address=None)
    api.patch.assert_called_once_with('/suppliers/3', json={'phone': None, 'email': None, 'address': None})

def test_update_only_name(pair):
    service, api = pair
    api.patch.return_value = DATA
    service.update_supplier(3, name=' Нова назва ')
    assert api.patch.call_args.kwargs['json'] == {'name': 'Нова назва'}

def test_update_requires_field(pair):
    with pytest.raises(ValueError):
        pair[0].update_supplier(3)

def test_delete(pair):
    service, api = pair
    service.delete_supplier(3)
    api.delete.assert_called_once_with('/suppliers/3')

@pytest.mark.parametrize('method,args', [('get_supplier', (0,)), ('delete_supplier', (-1,)),
                                          ('update_supplier', (True,))])
def test_invalid_id(pair, method, args):
    with pytest.raises(ValueError):
        getattr(pair[0], method)(*args)

@pytest.mark.parametrize('field,value', [('name', ''), ('name', 'a'*151), ('phone', '1'*31),
                                         ('contact_person', 'a'*151), ('email', 'invalid')])
def test_invalid_fields(pair, field, value):
    service, api = pair
    with pytest.raises(ValueError):
        service.create_supplier(**{'name': 'Valid', field: value})
    api.post.assert_not_called()

def test_unauthenticated(pair):
    service, api = pair
    api.is_authenticated = False
    with pytest.raises(SupplierServiceError):
        service.list_suppliers()
    api.get.assert_not_called()

def test_duplicate_ids(pair):
    service, api = pair
    api.get.return_value = [DATA, DATA]
    with pytest.raises(SupplierServiceError):
        service.list_suppliers()

def test_api_error_propagates(pair):
    service, api = pair
    api.delete.side_effect = RuntimeError('API 409')
    with pytest.raises(RuntimeError, match='409'):
        service.delete_supplier(3)
