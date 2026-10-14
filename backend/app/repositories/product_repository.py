from decimal import Decimal

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.models.stock_movement import StockMovement


class ProductRepository:
    """Repository for working with warehouse products."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def get_by_sku(self, sku: str) -> Product | None:
        statement = select(Product).where(
            Product.sku == sku
        )

        return self.db.scalar(statement)

    def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: str | None = None,
        sku: str | None = None,
        category_id: int | None = None,
        location_id: int | None = None
    ) -> list[Product]:
        if offset < 0:
            raise ValueError("Offset must not be negative")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        statement = select(Product)

        if search is not None:
            search = search.strip()

            if search:
                pattern = (
                    "%"
                    + search.replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                    + "%"
                )

                statement = statement.where(
                    or_(
                        Product.name.ilike(
                            pattern,
                            escape="\\"
                        ),
                        Product.sku.ilike(
                            pattern,
                            escape="\\"
                        )
                    )
                )

        if sku is not None:
            statement = statement.where(
                Product.sku == sku
            )

        if category_id is not None:
            statement = statement.where(
                Product.category_id == category_id
            )

        if location_id is not None:
            statement = statement.where(
                Product.location_id == location_id
            )

        statement = (
            statement
            .order_by(Product.id)
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    def get_stock_balances(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        stock_status: str | None = None,
        category_id: int | None = None,
        location_id: int | None = None,
        search: str | None = None,
        min_quantity: Decimal | None = None,
        max_quantity: Decimal | None = None,
        sort_by: str = "id"
    ) -> list[Product]:
        """Return products filtered and sorted by current stock balances."""
        if offset < 0:
            raise ValueError("Offset must not be negative")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        if stock_status not in (
            None,
            "in_stock",
            "out_of_stock",
        ):
            raise ValueError("Invalid stock status")

        if sort_by not in (
            "id",
            "quantity_asc",
            "quantity_desc",
        ):
            raise ValueError("Invalid sort field")

        for quantity in (min_quantity, max_quantity):
            if (
                quantity is not None
                and not quantity.is_finite()
            ):
                raise ValueError("Quantity must be finite")

        if (
            min_quantity is not None
            and min_quantity < Decimal("0")
        ):
            raise ValueError("Quantity must not be negative")

        if (
            max_quantity is not None
            and max_quantity < Decimal("0")
        ):
            raise ValueError("Quantity must not be negative")

        if (
            min_quantity is not None
            and max_quantity is not None
            and min_quantity > max_quantity
        ):
            raise ValueError(
                "Minimum quantity must not exceed maximum quantity"
            )

        statement = select(Product)

        if stock_status == "in_stock":
            statement = statement.where(
                Product.quantity > Decimal("0")
            )

        elif stock_status == "out_of_stock":
            statement = statement.where(
                Product.quantity == Decimal("0")
            )

        if category_id is not None:
            statement = statement.where(
                Product.category_id == category_id
            )

        if location_id is not None:
            statement = statement.where(
                Product.location_id == location_id
            )

        if search is not None:
            normalized_search = search.strip()

            if normalized_search:
                escaped_search = (
                    normalized_search
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )

                pattern = f"%{escaped_search}%"

                statement = statement.where(
                    or_(
                        Product.name.ilike(
                            pattern,
                            escape="\\",
                        ),
                        Product.sku.ilike(
                            pattern,
                            escape="\\",
                        ),
                    )
                )

        if min_quantity is not None:
            statement = statement.where(
                Product.quantity >= min_quantity
            )

        if max_quantity is not None:
            statement = statement.where(
                Product.quantity <= max_quantity
            )

        if sort_by == "quantity_asc":
            statement = statement.order_by(
                Product.quantity.asc(),
                Product.id,
            )

        elif sort_by == "quantity_desc":
            statement = statement.order_by(
                Product.quantity.desc(),
                Product.id,
            )

        else:
            statement = statement.order_by(Product.id)

        statement = (
            statement
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    def create(
        self,
        *,
        sku: str,
        name: str,
        category_id: int,
        location_id: int,
        unit: str = "pcs",
        description: str | None = None
    ) -> Product:
        product = Product(
            sku=sku,
            name=name,
            unit=unit,
            quantity=Decimal("0.000"),
            description=description,
            category_id=category_id,
            location_id=location_id
        )

        self.db.add(product)
        self.db.flush()

        return product

    def has_stock_movements(self, product_id: int) -> bool:
        statement = select(
            exists().where(
                StockMovement.product_id == product_id
            )
        )

        return bool(self.db.scalar(statement))

    def delete(self, product: Product) -> None:
        self.db.delete(product)
