from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.category import Category
from backend.app.repositories.category_repository import (
    CategoryRepository
)
from backend.app.schemas.categories import (
    CategoryCreate,
    CategoryUpdate
)

from backend.app.core.database_errors import (
    is_duplicate_entry,
    is_row_referenced
)


class CategoryNotFoundError(Exception):
    pass


class CategoryAlreadyExistsError(Exception):
    pass


class CategoryInUseError(Exception):
    pass


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = CategoryRepository(db)

    def create_category(
        self,
        data: CategoryCreate
    ) -> Category:
        if self.categories.get_by_name(data.name) is not None:
            raise CategoryAlreadyExistsError(
                "Категорія з такою назвою вже існує"
            )

        try:
            category = self.categories.create(
                name=data.name,
                description=data.description
            )

            self.db.commit()
            self.db.refresh(category)

            return category

        except IntegrityError as exc:
            self.db.rollback()

            if is_duplicate_entry(exc):
                raise CategoryAlreadyExistsError(
                    "Категорія з такою назвою вже існує"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise

    def update_category(
        self,
        category_id: int,
        data: CategoryUpdate
    ) -> Category:
        category = self.categories.get_by_id(category_id)

        if category is None:
            raise CategoryNotFoundError(
                "Категорію не знайдено"
            )

        changes = data.model_dump(exclude_unset=True)

        if not changes:
            return category

        new_name = changes.get("name")

        if new_name is not None and new_name != category.name:
            existing = self.categories.get_by_name(new_name)

            if existing is not None:
                raise CategoryAlreadyExistsError(
                    "Категорія з такою назвою вже існує"
                )

        try:
            for field, value in changes.items():
                setattr(category, field, value)

            self.db.commit()
            self.db.refresh(category)

            return category

        except IntegrityError as exc:
            self.db.rollback()

            if is_duplicate_entry(exc):
                raise CategoryAlreadyExistsError(
                    "Категорія з такою назвою вже існує"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise

    def delete_category(self, category_id: int) -> None:
        category = self.categories.get_by_id(category_id)

        if category is None:
            raise CategoryNotFoundError(
                "Категорію не знайдено"
            )

        if self.categories.has_products(category_id):
            raise CategoryInUseError(
                "Неможливо видалити категорію, "
                "оскільки до неї прив'язані товари"
            )

        try:
            self.categories.delete(category)
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            if is_row_referenced(exc):
                raise CategoryInUseError(
                    "Неможливо видалити категорію, "
                    "оскільки вона використовується"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise

