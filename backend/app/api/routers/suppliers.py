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
from backend.app.schemas.suppliers import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse
)
from backend.app.services.supplier_service import (
    SupplierService,
    SupplierNotFoundError,
    SupplierInUseError
)


router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"]
)


@router.get(
    "",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=list[SupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="List suppliers",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_suppliers(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[SupplierResponse]:
    suppliers = SupplierService(db).list_suppliers(
        offset=offset,
        limit=limit
    )

    return [
        SupplierResponse.model_validate(supplier)
        for supplier in suppliers
    ]


@router.get(
    "/{supplier_id}",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supplier by ID",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Supplier not found"},
        422: {"description": "Validation error"}
    }
)
def get_supplier(
    supplier_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> SupplierResponse:
    service = SupplierService(db)

    try:
        supplier = service.get_supplier(supplier_id)

    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return SupplierResponse.model_validate(supplier)


@router.post(
    "",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create supplier",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def create_supplier(
    data: SupplierCreate,
    db: Annotated[Session, Depends(get_db)]
) -> SupplierResponse:
    supplier = SupplierService(db).create_supplier(data)

    return SupplierResponse.model_validate(supplier)


@router.patch(
    "/{supplier_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Update supplier",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Supplier not found"},
        422: {"description": "Validation error"}
    }
)
def update_supplier(
    supplier_id: Annotated[int, Path(ge=1)],
    data: SupplierUpdate,
    db: Annotated[Session, Depends(get_db)]
) -> SupplierResponse:
    service = SupplierService(db)

    try:
        supplier = service.update_supplier(
            supplier_id=supplier_id,
            data=data
        )

    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return SupplierResponse.model_validate(supplier)


@router.delete(
    "/{supplier_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete supplier",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Supplier not found"},
        409: {"description": "Supplier is in use"},
        422: {"description": "Validation error"}
    }
)
def delete_supplier(
    supplier_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> Response:
    service = SupplierService(db)

    try:
        service.delete_supplier(supplier_id)

    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except SupplierInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
