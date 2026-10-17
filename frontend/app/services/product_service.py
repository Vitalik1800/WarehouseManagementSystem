"""Validated API access for products; quantity is read-only."""
from decimal import Decimal, InvalidOperation
from typing import Any
from frontend.app.api.client import APIClient

class ProductServiceError(Exception):
    pass

_UNSET = object()
_TEXT = {'sku': 64, 'name': 200, 'unit': 20}

class ProductService:
    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    def _auth(self) -> None:
        if not self.api_client.is_authenticated:
            raise ProductServiceError('Потрібна авторизація')

    @staticmethod
    def _id(value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError('ID має бути додатним цілим числом')
        return value

    @staticmethod
    def _field(key: str, value: Any) -> Any:
        if key in _TEXT:
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= _TEXT[key]:
                raise ValueError(f'{key}: довжина від 1 до {_TEXT[key]} символів')
            return value.strip()
        if key == 'description':
            if value is not None and not isinstance(value, str):
                raise ValueError('Опис має бути рядком або None')
            return value.strip() if value is not None else None
        if key in ('category_id', 'location_id'):
            return ProductService._id(value)
        raise ValueError(f'Невідоме поле: {key}')

    @classmethod
    def _validate(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ProductServiceError('Некоректний формат товару')
        try:
            result = {'id': cls._id(data['id'])}
            for key in ('sku','name','unit','description','category_id','location_id'):
                result[key] = cls._field(key, data[key])
            raw = data['quantity']
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
                raise ValueError('Некоректна кількість')
            quantity = Decimal(str(raw))
            if not quantity.is_finite():
                raise ValueError('Некоректна кількість')
            result['quantity'] = str(quantity)
        except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
            raise ProductServiceError(f'Некоректні дані товару: {exc}') from exc
        return result

    def list_products(self, offset: int = 0, limit: int = 50, *, search: str | None = None,
                      sku: str | None = None, category_id: int | None = None,
                      location_id: int | None = None) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError('offset має бути >= 0')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit має бути від 1 до 100')
        params: dict[str, Any] = {'offset': offset, 'limit': limit}
        for key, value in {'search':search, 'sku':sku}.items():
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError(f'{key} має бути рядком')
                if value.strip():
                    params[key] = value.strip()
        for key, value in {'category_id':category_id, 'location_id':location_id}.items():
            if value is not None:
                params[key] = self._id(value)
        self._auth()
        data = self.api_client.get('/products', params=params)
        if not isinstance(data, list) or len(data) > limit:
            raise ProductServiceError('Некоректний список товарів')
        items = [self._validate(item) for item in data]
        if len({item['id'] for item in items}) != len(items):
            raise ProductServiceError('Повторювані ID товарів')
        return items

    def get_product(self, product_id: int) -> dict[str, Any]:
        self._id(product_id)
        self._auth()
        result = self._validate(self.api_client.get(f'/products/{product_id}'))
        if result['id'] != product_id:
            raise ProductServiceError('API повернув інший товар')
        return result

    def create_product(self, *, sku: str, name: str, unit: str = 'pcs',
                       description: str | None = None, category_id: int, location_id: int) -> dict[str, Any]:
        values = locals().copy()
        payload = {key:self._field(key,values[key]) for key in
                   ('sku','name','unit','description','category_id','location_id')}
        self._auth()
        return self._validate(self.api_client.post('/products', json=payload))

    def update_product(self, product_id: int, *, sku: str | object = _UNSET,
                       name: str | object = _UNSET, unit: str | object = _UNSET,
                       description: str | None | object = _UNSET,
                       category_id: int | object = _UNSET,
                       location_id: int | object = _UNSET) -> dict[str, Any]:
        self._id(product_id)
        values = locals().copy()
        payload = {key:self._field(key,values[key]) for key in
                   ('sku','name','unit','description','category_id','location_id') if values[key] is not _UNSET}
        if not payload:
            raise ValueError('Потрібно вказати хоча б одне поле')
        self._auth()
        result = self._validate(self.api_client.patch(f'/products/{product_id}', json=payload))
        if result['id'] != product_id:
            raise ProductServiceError('API повернув інший товар')
        return result

    def delete_product(self, product_id: int) -> None:
        self._id(product_id)
        self._auth()
        self.api_client.delete(f'/products/{product_id}')
