from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status
)
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.repositories.category_repository import (
    CategoryRepository
)
from backend.app.schemas.categories import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse
)
from backend.app.services.category_service import (
    CategoryService,
    CategoryNotFoundError,
    CategoryAlreadyExistsError,
    CategoryInUseError
)


router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)


@router.get(
    "",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List categories",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[CategoryResponse]:
    categories = CategoryRepository(db).get_all(
        offset=offset,
        limit=limit
    )

    return [
        CategoryResponse.model_validate(category)
        for category in categories
    ]


@router.get(
    "/{category_id}",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category by ID",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Category not found"},
        422: {"description": "Validation error"}
    }
)
def get_category(
    category_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> CategoryResponse:
    category = CategoryRepository(db).get_by_id(
        category_id
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категорію не знайдено"
        )

    return CategoryResponse.model_validate(category)


@router.post(
    "",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        409: {"description": "Category already exists"},
        422: {"description": "Validation error"}
    }
)
def create_category(
    data: CategoryCreate,
    db: Annotated[Session, Depends(get_db)]
) -> CategoryResponse:
    service = CategoryService(db)

    try:
        category = service.create_category(data)

    except CategoryAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return CategoryResponse.model_validate(category)


@router.patch(
    "/{category_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update category",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Category not found"},
        409: {"description": "Category already exists"},
        422: {"description": "Validation error"}
    }
)
def update_category(
    category_id: Annotated[int, Path(ge=1)],
    data: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)]
) -> CategoryResponse:
    service = CategoryService(db)

    try:
        category = service.update_category(
            category_id=category_id,
            data=data
        )

    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc

    except CategoryAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return CategoryResponse.model_validate(category)


@router.delete(
    "/{category_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete category",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Category not found"},
        409: {"description": "Category is in use"},
        422: {"description": "Validation error"}
    }
)
def delete_category(
    category_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> Response:
    service = CategoryService(db)

    try:
        service.delete_category(category_id)

    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc

    except CategoryInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
