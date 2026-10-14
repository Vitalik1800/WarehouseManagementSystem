from decimal import Decimal
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status
)
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.schemas.stock_balances import (
    StockBalanceResponse
)
from backend.app.services.stock_balance_service import (
    StockBalanceService
)


router = APIRouter(
    prefix="/stock-balances",
    tags=["Stock Balances"]
)


@router.get(
    "",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=list[StockBalanceResponse],
    status_code=status.HTTP_200_OK,
    summary="List current stock balances",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_stock_balances(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    stock_status: Annotated[
        Literal["in_stock", "out_of_stock"] | None,
        Query()
    ] = None,
    category_id: Annotated[
        int | None,
        Query(ge=1)
    ] = None,
    location_id: Annotated[
        int | None,
        Query(ge=1)
    ] = None,
    search: Annotated[
        str | None,
        Query()
    ] = None,
    min_quantity: Annotated[
        Decimal | None,
        Query(ge=0, allow_inf_nan=False)
    ] = None,
    max_quantity: Annotated[
        Decimal | None,
        Query(ge=0, allow_inf_nan=False)
    ] = None,
    sort_by: Annotated[
        Literal[
            "id",
            "quantity_asc",
            "quantity_desc"
        ],
        Query()
    ] = "id"
) -> list[StockBalanceResponse]:
    if (
        min_quantity is not None
        and max_quantity is not None
        and min_quantity > max_quantity
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "min_quantity cannot be greater "
                "than max_quantity"
            )
        )

    service = StockBalanceService(db)

    products = service.list_stock_balances(
        offset=offset,
        limit=limit,
        stock_status=stock_status,
        category_id=category_id,
        location_id=location_id,
        search=search,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
        sort_by=sort_by
    )

    return [
        StockBalanceResponse.model_validate(product)
        for product in products
    ]
