
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database_errors import (
    is_duplicate_entry,
    is_missing_reference,
    is_row_referenced
)
from backend.app.models.product import Product
from backend.app.repositories.category_repository import (
    CategoryRepository
)
from backend.app.repositories.product_repository import (
    ProductRepository
)
from backend.app.repositories.storage_location_repository import (
    StorageLocationRepository
)
from backend.app.schemas.products import (
    ProductCreate,
    ProductUpdate
)


class ProductNotFoundError(Exception):
    pass


class ProductAlreadyExistsError(Exception):
    pass


class ProductCategoryNotFoundError(Exception):
    pass


class ProductLocationNotFoundError(Exception):
    pass


class ProductInUseError(Exception):
    pass


class ProductLocationChangeError(Exception):
    pass


class ProductService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)
        self.locations = StorageLocationRepository(db)

    def _validate_category(self, category_id: int) -> None:
        if self.categories.get_by_id(category_id) is None:
            raise ProductCategoryNotFoundError(
                "Категорію товару не знайдено"
            )

    def _validate_location(self, location_id: int) -> None:
        if self.locations.get_by_id(location_id) is None:
            raise ProductLocationNotFoundError(
                "Місце зберігання не знайдено"
            )

    def _handle_missing_reference(
        self,
        *,
        category_id: int,
        location_id: int,
        error: IntegrityError
    ) -> None:
        if not is_missing_reference(error):
            return

        self._validate_category(category_id)
        self._validate_location(location_id)

    def create_product(self, data: ProductCreate) -> Product:
        if self.products.get_by_sku(data.sku) is not None:
            raise ProductAlreadyExistsError(
                "Товар із таким артикулом уже існує"
            )

        self._validate_category(data.category_id)
        self._validate_location(data.location_id)

        try:
            product = self.products.create(
                sku=data.sku,
                name=data.name,
                unit=data.unit,
                description=data.description,
                category_id=data.category_id,
                location_id=data.location_id
            )

            self.db.commit()
            self.db.refresh(product)

            return product

        except IntegrityError as exc:
            self.db.rollback()

            if is_duplicate_entry(exc):
                raise ProductAlreadyExistsError(
                    "Товар із таким артикулом уже існує"
                ) from exc

            self._handle_missing_reference(
                category_id=data.category_id,
                location_id=data.location_id,
                error=exc
            )

            raise

        except Exception:
            self.db.rollback()
            raise

    def get_product(self, product_id: int) -> Product:
        product = self.products.get_by_id(product_id)

        if product is None:
            raise ProductNotFoundError(
                "Товар не знайдено"
            )

        return product

    def list_products(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: str | None = None,
        sku: str | None = None,
        category_id: int | None = None,
        location_id: int | None = None
    ) -> list[Product]:
        return self.products.get_all(
            offset=offset,
            limit=limit,
            search=search,
            sku=sku,
            category_id=category_id,
            location_id=location_id
        )

    def update_product(
        self,
        product_id: int,
        data: ProductUpdate
    ) -> Product:
        product = self.get_product(product_id)
        changes = data.model_dump(exclude_unset=True)

        if not changes:
            return product

        new_sku = changes.get("sku")

        if new_sku is not None and new_sku != product.sku:
            existing = self.products.get_by_sku(new_sku)

            if existing is not None:
                raise ProductAlreadyExistsError(
                    "Товар із таким артикулом уже існує"
                )

        if (
            "category_id" in changes
            and changes["category_id"] != product.category_id
        ):
            self._validate_category(changes["category_id"])

        if (
            "location_id" in changes
            and changes["location_id"] != product.location_id
        ):
            if product.quantity != Decimal("0.000"):
                raise ProductLocationChangeError(
                    "Неможливо змінити місце зберігання "
                    "товару з ненульовим залишком"
                )

            self._validate_location(changes["location_id"])

        effective_category_id = changes.get("category_id", product.category_id)
        effective_location_id = changes.get("location_id", product.location_id)

        try:
            for field, value in changes.items():
                setattr(product, field, value)

            self.db.commit()
            self.db.refresh(product)

            return product

        except IntegrityError as exc:
            self.db.rollback()

            if is_duplicate_entry(exc):
                raise ProductAlreadyExistsError(
                    "Товар із таким артикулом уже існує"
                ) from exc

            if is_missing_reference(exc):
                self._handle_missing_reference(
                    category_id=effective_category_id,
                    location_id=effective_location_id,
                    error=exc
                )

            raise

        except Exception:
            self.db.rollback()
            raise

    def delete_product(self, product_id: int) -> None:
        product = self.get_product(product_id)

        if self.products.has_stock_movements(product_id):
            raise ProductInUseError(
                "Неможливо видалити товар, "
                "оскільки він має історію складських операцій"
            )

        try:
            self.products.delete(product)
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            if is_row_referenced(exc):
                raise ProductInUseError(
                    "Неможливо видалити товар, "
                    "оскільки він використовується "
                    "в інших записах"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise
