from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database_errors import (
    is_missing_reference
)
from backend.app.models.product import Product
from backend.app.models.stock_movement import StockMovement
from backend.app.repositories.stock_movement_repository import (
    StockMovementRepository
)
from backend.app.repositories.supplier_repository import (
    SupplierRepository
)
from backend.app.schemas.stock_movements import (
    StockBalanceResponse,
    StockMovementCreate
)


MAX_STOCK_QUANTITY = Decimal("99999999999.999")


class StockMovementNotFoundError(Exception):
    pass


class StockProductNotFoundError(Exception):
    pass


class StockSupplierNotFoundError(Exception):
    pass


class InsufficientStockError(Exception):
    pass


class StockQuantityOverflowError(Exception):
    pass


class InventoryService:
    """Business logic for warehouse stock operations."""

    def __init__(self, db: Session) -> None:
        self.db= db
        self.movements = StockMovementRepository(db)
        self.suppliers = SupplierRepository(db)

    def _get_product(self, product_id: int) -> Product:
        product = self.movements.get_product(product_id)

        if product is None:
            raise StockProductNotFoundError(
                "Товар не знайдено"
            )

        return product

    def _validate_supplier(
        self,
        supplier_id: int | None
    ) -> None:
        if supplier_id is None:
            return

        if self.suppliers.get_by_id(supplier_id) is None:
            raise StockSupplierNotFoundError(
                "Постачальника не знайдено"
            )

    def _handle_missing_reference(
        self,
        *,
        product_id: int,
        supplier_id: int | None,
        error: IntegrityError
    ) -> None:
        if not is_missing_reference(error):
            return

        self._get_product(product_id)
        self._validate_supplier(supplier_id)

    def create_movement(
        self,
        data: StockMovementCreate,
        *,
        user_id: int
    ) -> StockMovement:
        self._get_product(data.product_id)

        if data.movement_type == "receipt":
            self._validate_supplier(data.supplier_id)

        try:
            if data.movement_type == "receipt":
                updated = self.movements.increase_stock(
                    data.product_id,
                    data.quantity
                )

                if not updated:
                    self._get_product(data.product_id)

                    raise StockQuantityOverflowError(
                        "Надходження перевищує максимально допустимий залишок"
                    )

            elif data.movement_type in ("issue", "writeoff"):
                updated = self.movements.decrease_stock(
                    data.product_id,
                    data.quantity
                )

                if not updated:
                    self._get_product(data.product_id)

                    raise InsufficientStockError(
                        "Недостатньо товару на складі"
                    )

            else:
                raise ValueError(
                    "Невідомий тип складської операції"
                )

            movement = self.movements.create(
                product_id=data.product_id,
                user_id=user_id,
                movement_type=data.movement_type,
                quantity=data.quantity,
                supplier_id=data.supplier_id,
                note=data.note
            )

            self.db.commit()
            self.db.refresh(movement)

            return movement

        except IntegrityError as exc:
            self.db.rollback()

            self._handle_missing_reference(
                product_id=data.product_id,
                supplier_id=data.supplier_id,
                error=exc
            )

            raise

        except Exception:
            self.db.rollback()
            raise

    def get_movement(
        self,
        movement_id: int
    ) -> StockMovement:
        movement = self.movements.get_by_id(movement_id)

        if movement is None:
            raise StockMovementNotFoundError(
                "Складську операцію не знайдено"
            )

        return movement

    def list_movements(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        product_id: int | None = None,
        user_id: int | None = None,
        supplier_id: int | None = None,
        movement_type: str | None = None
    ) -> list[StockMovement]:
        return self.movements.get_all(
            offset=offset,
            limit=limit,
            product_id=product_id,
            user_id=user_id,
            supplier_id=supplier_id,
            movement_type=movement_type
        )

    def get_stock_balance(
        self,
        product_id: int
    ) -> StockBalanceResponse:
        product = self._get_product(product_id)

        return StockBalanceResponse(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            unit=product.unit,
            quantity=product.quantity
        )
