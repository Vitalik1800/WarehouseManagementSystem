from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status
)
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.stock_movements import (
    StockMovementCreate,
    StockMovementResponse
)
from backend.app.services.inventory_service import (
    InventoryService,
    InsufficientStockError,
    StockMovementNotFoundError,
    StockProductNotFoundError,
    StockQuantityOverflowError,
    StockSupplierNotFoundError
)


router = APIRouter(
    prefix="/stock-movements",
    tags=["Stock Movements"]
)

AuthorizedUser = Annotated[
    User,
    Depends(require_roles("admin", "worker"))
]

DatabaseSession = Annotated[
    Session,
    Depends(get_db)
]


def _create_movement(
    data: StockMovementCreate,
    db: Session,
    current_user: User
) -> StockMovementResponse:
    service = InventoryService(db)

    try:
        movements = service.create_movement(
            data=data,
            user_id=current_user.id
        )

    except (
        StockProductNotFoundError,
        StockSupplierNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        InsufficientStockError,
        StockQuantityOverflowError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return StockMovementResponse.model_validate(movements)


@router.post(
    "/receipts",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive stock",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Product or supplier not found"},
        409: {"description": "Stock quantity overflow"},
        422: {"description": "Validation error"}
    }
)
def receive_stock(
    data: StockMovementCreate,
    db: DatabaseSession,
    current_user: AuthorizedUser
) -> StockMovementResponse:
    if data.movement_type != "receipt":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Movement type must be receipt",
        )

    return _create_movement(data, db, current_user)


@router.post(
    "/issues",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue stock",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Product not found"},
        409: {"description": "Insufficient stock"},
        422: {"description": "Validation error"}
    }
)
def issue_stock(
    data: StockMovementCreate,
    db: DatabaseSession,
    current_user: AuthorizedUser
) -> StockMovementResponse:
    if data.movement_type != "issue":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Movement type must be issue",
        )

    return _create_movement(data, db, current_user)


@router.post(
    "/writeoffs",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Write off stock",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Product not found"},
        409: {"description": "Insufficient stock"},
        422: {"description": "Validation error"}
    }
)
def writeoff_stock(
    data: StockMovementCreate,
    db: DatabaseSession,
    current_user: AuthorizedUser
) -> StockMovementResponse:
    if data.movement_type != "writeoff":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Movement type must be writeoff",
        )

    return _create_movement(data, db, current_user)


@router.get(
    "",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=list[StockMovementResponse],
    status_code=status.HTTP_200_OK,
    summary="List stock movements",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_stock_movements(
    db: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    product_id: Annotated[int | None, Query(ge=1)] = None,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    supplier_id: Annotated[int | None, Query(ge=1)] = None,
    movement_type: Annotated[
        str | None,
        Query(pattern="^(receipt|issue|writeoff)$")
    ] = None
) -> list[StockMovementResponse]:
    service = InventoryService(db)

    movements = service.list_movements(
        offset=offset,
        limit=limit,
        product_id=product_id,
        user_id=user_id,
        supplier_id=supplier_id,
        movement_type=movement_type
    )

    return [
        StockMovementResponse.model_validate(movement)
        for movement in movements
    ]


@router.get(
    "/{movement_id}",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=StockMovementResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stock movement by ID",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Stock movement not found"},
        422: {"description": "Validation error"}
    }
)
def get_stock_movement(
    movement_id: Annotated[int, Path(ge=1)],
    db: DatabaseSession
) -> StockMovementResponse:
    service = InventoryService(db)

    try:
        movement = service.get_movement(movement_id)

    except StockMovementNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StockMovementResponse.model_validate(movement)
