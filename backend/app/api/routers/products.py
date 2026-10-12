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
from backend.app.schemas.products import (
    ProductCreate,
    ProductUpdate,
    ProductResponse
)
from backend.app.services.product_service import (
    ProductService,
    ProductNotFoundError,
    ProductAlreadyExistsError,
    ProductCategoryNotFoundError,
    ProductLocationNotFoundError,
    ProductLocationChangeError,
    ProductInUseError
)

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.get(
    "",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=list[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="List products",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str | None, Query()] = None,
    sku: Annotated[str | None, Query()] = None,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    location_id: Annotated[int | None, Query(ge=1)] = None
) -> list[ProductResponse]:
    service = ProductService(db)

    products = service.list_products(
        offset=offset,
        limit=limit,
        search=search,
        sku=sku,
        category_id=category_id,
        location_id=location_id
    )

    return [
        ProductResponse.model_validate(product)
        for product in products
    ]


@router.get(
    "/{product_id}",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product by ID",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Product not found"},
        422: {"description": "Validation error"}
    }
)
def get_product(
    product_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> ProductResponse:
    service = ProductService(db)

    try:
        product = service.get_product(product_id)

    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc

    return ProductResponse.model_validate(product)


@router.post(
    "",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Category or location not found"},
        409: {"description": "Product SKU already exists"},
        422: {"description": "Validation error"}
    }
)
def create_product(
    data: ProductCreate,
    db: Annotated[Session, Depends(get_db)]
) -> ProductResponse:
    service = ProductService(db)

    try:
        product = service.create_product(data)

    except ProductAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    except (
        ProductCategoryNotFoundError,
        ProductLocationNotFoundError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc

    return ProductResponse.model_validate(product)


@router.patch(
    "/{product_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Product, category or location not found"},
        409: {"description": "SKU conflict or location change forbidden"},
        422: {"description": "Validation error"}
    }
)
def update_product(
    product_id: Annotated[int, Path(ge=1)],
    data: ProductUpdate,
    db: Annotated[Session, Depends(get_db)]
) -> ProductResponse:
    service = ProductService(db)

    try:
        product = service.update_product(
            product_id=product_id,
            data=data
        )

    except (
        ProductNotFoundError,
        ProductCategoryNotFoundError,
        ProductLocationNotFoundError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc

    except (
        ProductAlreadyExistsError,
        ProductLocationChangeError
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return ProductResponse.model_validate(product)



@router.delete(
    "/{product_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Product not found"},
        409: {"description": "Product is in use"},
        422: {"description": "Validation error"}
    }
)
def delete_product(
    product_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> Response:
    service = ProductService(db)

    try:
        service.delete_product(product_id)

    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc

    except ProductInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )