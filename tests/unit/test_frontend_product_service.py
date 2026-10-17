from unittest.mock import Mock
import pytest
from frontend.app.services.product_service import ProductService, ProductServiceError

@pytest.fixture
def api():
    client = Mock()
    client.is_authenticated = True
    return client

@pytest.fixture
def item():
    return dict(id=1,sku='A-1',name='Товар',unit='pcs',quantity='12.50',description=None,category_id=2,location_id=3)

def test_list_and_filters(api,item):
    api.get.return_value=[item]
    result=ProductService(api).list_products(0,25,search=' Товар ',sku=' A-1 ',category_id=2,location_id=3)
    assert result[0]['quantity']=='12.50'
    api.get.assert_called_once_with('/products',params=dict(offset=0,limit=25,search='Товар',sku='A-1',category_id=2,location_id=3))

@pytest.mark.parametrize('offset,limit', [(-1,25),(0,0),(0,101),(True,25),(0,False)])
def test_bad_pagination(api,offset,limit):
    with pytest.raises(ValueError): ProductService(api).list_products(offset,limit)

@pytest.mark.parametrize('field,value', [('sku',''),('name',' '),('unit',''),('category_id',0),('location_id',None)])
def test_bad_required_fields(api,field,value):
    with pytest.raises(ValueError): ProductService._field(field,value)

def test_create_payload_excludes_quantity(api,item):
    api.post.return_value=item
    ProductService(api).create_product(sku='A-1',name='Товар',category_id=2,location_id=3)
    assert 'quantity' not in api.post.call_args.kwargs['json']

def test_update_can_clear_description(api,item):
    api.patch.return_value=item
    ProductService(api).update_product(1,description=None)
    api.patch.assert_called_once_with('/products/1',json={'description':None})

def test_update_rejects_null_references(api):
    with pytest.raises(ValueError): ProductService(api).update_product(1,location_id=None)

def test_delete(api):
    ProductService(api).delete_product(1)
    api.delete.assert_called_once_with('/products/1')

def test_bad_api_data(api,item):
    api.get.return_value=[{**item,'quantity':'NaN'}]
    with pytest.raises(ProductServiceError): ProductService(api).list_products()

def test_auth_required(api):
    api.is_authenticated=False
    with pytest.raises(ProductServiceError): ProductService(api).list_products()
