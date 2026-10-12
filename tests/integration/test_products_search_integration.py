from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.models import Category, Product, StorageLocation
from backend.app.repositories.product_repository import ProductRepository


@pytest.fixture
def product_data(db_session):
    marker = uuid4().hex[:12]

    category_a = Category(name=f"SearchCategoryA_{marker}")
    category_b = Category(name=f"SearchCategoryB_{marker}")

    location_a = StorageLocation(name=f"SearchLocationA_{marker}")
    location_b = StorageLocation(name=f"SearchLocationB_{marker}")

    db_session.add_all([
        category_a,
        category_b,
        location_a,
        location_b,
    ])
    db_session.flush()

    products = [
        Product(
            sku=f"SAMSUNG_{marker}",
            name="Samsung Galaxy",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_a.id,
            location_id=location_a.id,
        ),
        Product(
            sku=f"APPLE_{marker}",
            name="Apple iPhone",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_a.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"LENOVO_{marker}",
            name="Lenovo ThinkPad",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_a.id,
        ),
        Product(
            sku=f"PERCENT_{marker}",
            name="Discount 50% Special",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"UNDERSCORE_{marker}",
            name="item_name",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"BACKSLASH_{marker}",
            name=r"folder\item",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"PERCENT_CONTROL_{marker}",
            name="Discount 500 Special",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"UNDERSCORE_CONTROL_{marker}",
            name="itemXname",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"BACKSLASH_CONTROL_{marker}",
            name="folderXitem",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
    ]

    db_session.add_all(products)
    db_session.flush()

    return {
        "repository": ProductRepository(db_session),
        "products": products,
        "category_a": category_a,
        "category_b": category_b,
        "location_a": location_a,
        "location_b": location_b,
    }


def find_created(result, products):
    ids = {product.id for product in products}
    return [product for product in result if product.id in ids]


# ============================================================
# SEARCH
# ============================================================


def test_search_by_name(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(search="Samsung Galaxy")

    assert products[0] in result


def test_search_by_sku(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(search=products[1].sku)

    assert products[1] in result


def test_search_case_insensitive(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(search="sAmSuNg GaLaXy")

    assert products[0] in result


def test_search_trims_whitespace(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(search="  Samsung Galaxy  ")

    assert products[0] in result


# ============================================================
# FILTERS
# ============================================================


def test_filter_by_exact_sku(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(sku=products[0].sku)

    assert [product.id for product in result] == [products[0].id]


def test_filter_by_category(product_data):
    repository = product_data["repository"]
    category = product_data["category_a"]

    result = repository.get_all(category_id=category.id)

    assert all(product.category_id == category.id for product in result)


def test_filter_by_location(product_data):
    repository = product_data["repository"]
    location = product_data["location_a"]

    result = repository.get_all(location_id=location.id)

    assert all(product.location_id == location.id for product in result)


def test_combined_filters(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(
        search="Samsung",
        sku=products[0].sku,
        category_id=products[0].category_id,
        location_id=products[0].location_id,
    )

    assert [product.id for product in result] == [products[0].id]


def test_combined_filters_no_matches(product_data):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(
        sku=products[0].sku,
        category_id=product_data["category_b"].id,
    )

    assert result == []


# ============================================================
# PAGINATION AND ORDERING
# ============================================================


def test_pagination_limit(product_data):
    repository = product_data["repository"]

    result = repository.get_all(limit=2)

    assert len(result) == 2


def test_pagination_offset(product_data):
    repository = product_data["repository"]

    first_page = repository.get_all(offset=0, limit=2)
    second_page = repository.get_all(offset=2, limit=2)

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert set(p.id for p in first_page).isdisjoint(
        p.id for p in second_page
    )


def test_ordered_by_id(product_data):
    repository = product_data["repository"]

    result = repository.get_all(limit=100)

    ids = [product.id for product in result]

    assert ids == sorted(ids)


def test_large_offset_returns_empty(product_data):
    repository = product_data["repository"]

    result = repository.get_all(offset=1000000, limit=10)

    assert result == []


@pytest.mark.parametrize(
    ("search", "index"),
    [
        ("50%", 3),
        ("item_name", 4),
        (r"folder\item", 5),
    ],
)
def test_search_special_characters(product_data, search, index):
    repository = product_data["repository"]
    products = product_data["products"]

    result = repository.get_all(search=search)

    assert [product.id for product in result] == [
        products[index].id
    ]
