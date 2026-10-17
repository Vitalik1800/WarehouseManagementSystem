"""Validated API access for suppliers."""
import re
from typing import Any
from frontend.app.api.client import APIClient

class SupplierServiceError(Exception):
    """Invalid supplier data returned by the API or missing authorization."""

_UNSET = object()
_FIELDS = ('name', 'contact_person', 'phone', 'email', 'address')

class SupplierService:
    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    def _require_auth(self) -> None:
        if not self.api_client.is_authenticated:
            raise SupplierServiceError('Потрібна авторизація')

    @staticmethod
    def _id(value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError('ID постачальника має бути додатним цілим числом')
        return value

    @staticmethod
    def _field(key: str, value: str | None) -> str | None:
        if value is None:
            if key == 'name':
                raise ValueError('Назва не може бути порожньою')
            return None
        if not isinstance(value, str):
            raise ValueError(f'{key}: очікується рядок або None')
        value = value.strip()
        if key == 'name' and not 1 <= len(value) <= 150:
            raise ValueError('Назва повинна містити 1–150 символів')
        if key == 'contact_person' and len(value) > 150:
            raise ValueError('Контактна особа: максимум 150 символів')
        if key == 'phone' and len(value) > 30:
            raise ValueError('Телефон: максимум 30 символів')
        if key == 'email' and value and (len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value)):
            raise ValueError('Некоректний email')
        if key != 'name' and not value:
            return None
        return value

    @classmethod
    def _validate_supplier(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise SupplierServiceError('Некоректний формат постачальника')
        try:
            supplier_id = cls._id(value.get('id'))
            fields = {key: cls._field(key, value[key]) for key in _FIELDS}
        except (KeyError, ValueError, TypeError) as exc:
            raise SupplierServiceError(f'Некоректні дані постачальника: {exc}') from exc
        return {'id': supplier_id, **fields}

    def list_suppliers(self, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError('offset має бути цілим числом >= 0')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit має бути від 1 до 100')
        self._require_auth()
        result = self.api_client.get('/suppliers', params={'offset': offset, 'limit': limit})
        if not isinstance(result, list) or len(result) > limit:
            raise SupplierServiceError('Некоректний список постачальників')
        suppliers = [self._validate_supplier(item) for item in result]
        ids = [item['id'] for item in suppliers]
        if len(ids) != len(set(ids)):
            raise SupplierServiceError('Повторювані ID постачальників')
        return suppliers

    def get_supplier(self, supplier_id: int) -> dict[str, Any]:
        self._id(supplier_id)
        self._require_auth()
        result = self._validate_supplier(self.api_client.get(f'/suppliers/{supplier_id}'))
        if result['id'] != supplier_id:
            raise SupplierServiceError('API повернув іншого постачальника')
        return result

    def create_supplier(self, name: str, contact_person: str | None = None, phone: str | None = None,
                        email: str | None = None, address: str | None = None) -> dict[str, Any]:
        payload = {key: self._field(key, value) for key, value in dict(name=name, contact_person=contact_person,
                   phone=phone, email=email, address=address).items()}
        self._require_auth()
        return self._validate_supplier(self.api_client.post('/suppliers', json=payload))

    def update_supplier(self, supplier_id: int, *, name: str | object = _UNSET,
                        contact_person: str | None | object = _UNSET,
                        phone: str | None | object = _UNSET,
                        email: str | None | object = _UNSET,
                        address: str | None | object = _UNSET) -> dict[str, Any]:
        self._id(supplier_id)
        values = dict(name=name, contact_person=contact_person, phone=phone, email=email, address=address)
        payload = {key: self._field(key, value) for key, value in values.items() if value is not _UNSET}
        if not payload:
            raise ValueError('Потрібно вказати хоча б одне поле')
        self._require_auth()
        result = self._validate_supplier(self.api_client.patch(f'/suppliers/{supplier_id}', json=payload))
        if result['id'] != supplier_id:
            raise SupplierServiceError('API повернув іншого постачальника')
        return result

    def delete_supplier(self, supplier_id: int) -> None:
        self._id(supplier_id)
        self._require_auth()
        self.api_client.delete(f'/suppliers/{supplier_id}')
