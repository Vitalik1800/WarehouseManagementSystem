from unittest.mock import Mock

import pytest

from frontend.app.services.category_service import CategoryService, CategoryServiceError


def client(authenticated=True):
    api = Mock()
    api.is_authenticated = authenticated
    return api


def category(category_id=1, name='Tools', description=None):
    return {'id': category_id, 'name': name, 'description': description}


def test_list_categories_pagination():
    api = client()
    api.get.return_value = [category()]
    result = CategoryService(api).list_categories(offset=25, limit=25)
    assert result == [category()]
    api.get.assert_called_once_with('/categories', params={'offset': 25, 'limit': 25})


@pytest.mark.parametrize('offset,limit', [(-1, 25), (0, 0), (0, 101), (True, 25), (0, True)])
def test_invalid_pagination(offset, limit):
    with pytest.raises(ValueError):
        CategoryService(client()).list_categories(offset, limit)


def test_list_rejects_duplicate_ids():
    api = client()
    api.get.return_value = [category(), category(name='Other')]
    with pytest.raises(CategoryServiceError, match='ID'):
        CategoryService(api).list_categories()


def test_list_rejects_too_many_results():
    api = client()
    api.get.return_value = [category(i + 1) for i in range(3)]
    with pytest.raises(CategoryServiceError):
        CategoryService(api).list_categories(limit=2)


@pytest.mark.parametrize('bad', [None, [], {'id': 0, 'name': 'A'}, {'id': True, 'name': 'A'}, {'id': 1, 'name': '  '}, {'id': 1, 'name': 'A', 'description': 2}])
def test_invalid_category_response(bad):
    with pytest.raises(CategoryServiceError):
        CategoryService._validate_category(bad)


def test_get_category():
    api = client()
    api.get.return_value = category(7)
    assert CategoryService(api).get_category(7)['id'] == 7
    api.get.assert_called_once_with('/categories/7')


def test_get_rejects_mismatched_id():
    api = client()
    api.get.return_value = category(8)
    with pytest.raises(CategoryServiceError):
        CategoryService(api).get_category(7)


def test_create_trims_name():
    api = client()
    api.post.return_value = category()
    CategoryService(api).create_category('  Tools  ', 'Description')
    api.post.assert_called_once_with('/categories', json={'name': 'Tools', 'description': 'Description'})


@pytest.mark.parametrize('name', ['', '   ', 'x' * 101, None, 10])
def test_create_rejects_invalid_name(name):
    with pytest.raises(ValueError):
        CategoryService(client()).create_category(name)


def test_update_name_only():
    api = client()
    api.patch.return_value = category()
    CategoryService(api).update_category(1, name=' Tools ')
    api.patch.assert_called_once_with('/categories/1', json={'name': 'Tools'})


def test_update_explicitly_clears_description():
    api = client()
    api.patch.return_value = category()
    CategoryService(api).update_category(1, description=None)
    api.patch.assert_called_once_with('/categories/1', json={'description': None})


def test_update_requires_changes():
    with pytest.raises(ValueError):
        CategoryService(client()).update_category(1)


def test_delete():
    api = client()
    CategoryService(api).delete_category(3)
    api.delete.assert_called_once_with('/categories/3')


@pytest.mark.parametrize('operation', ['list', 'get', 'create', 'update', 'delete'])
def test_authentication_required(operation):
    service = CategoryService(client(False))
    calls = {
        'list': lambda: service.list_categories(),
        'get': lambda: service.get_category(1),
        'create': lambda: service.create_category('Tools'),
        'update': lambda: service.update_category(1, name='Tools'),
        'delete': lambda: service.delete_category(1),
    }
    with pytest.raises(CategoryServiceError, match='авторизація'):
        calls[operation]()
