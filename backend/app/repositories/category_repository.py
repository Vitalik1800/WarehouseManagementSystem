from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.app.models.category import Category
from backend.app.models.product import Product


class CategoryRepository:
    """Репозиторій для роботи з категоріями товарів."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, category_id: int) -> Category | None:
        return self.db.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        statement = select(Category).where(
            Category.name == name
        )

        return self.db.scalar(statement)

    def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50
    ) -> list[Category]:
        if offset < 0:
            raise ValueError("Offset must not be negative")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        statement = (
            select(Category)
            .order_by(Category.id)
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    def create(
        self,
        *,
        name: str,
        description: str | None = None
    ) -> Category:
        category = Category(
            name=name,
            description=description
        )

        self.db.add(category)
        self.db.flush()

        return category

    def has_products(self, category_id: int) -> bool:
        statement = select(
            exists().where(
                Product.category_id == category_id
            )
        )

        return bool(self.db.scalar(statement))

    def delete(self, category: Category) -> None:
        self.db.delete(category)
