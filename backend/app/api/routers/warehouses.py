from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.schemas.warehouses import WarehouseCreate, WarehouseUpdate, WarehouseResponse
from backend.app.services.warehouse_service import (
    WarehouseService, WarehouseNotFoundError,
    WarehouseAlreadyExistsError, WarehouseInUseError,
)

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("", response_model=list[WarehouseResponse], dependencies=[Depends(require_roles("admin", "worker"))])
def list_warehouses(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return WarehouseService(db).list_warehouses(offset=offset, limit=limit)


@router.get("/{warehouse_id}", response_model=WarehouseResponse, dependencies=[Depends(require_roles("admin", "worker"))])
def get_warehouse(warehouse_id: Annotated[int, Path(ge=1)], db: Annotated[Session, Depends(get_db)]):
    try:
        return WarehouseService(db).get_warehouse(warehouse_id)
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin"))])
def create_warehouse(data: WarehouseCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        return WarehouseService(db).create_warehouse(data)
    except WarehouseAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{warehouse_id}", response_model=WarehouseResponse, dependencies=[Depends(require_roles("admin"))])
def update_warehouse(warehouse_id: Annotated[int, Path(ge=1)], data: WarehouseUpdate, db: Annotated[Session, Depends(get_db)]):
    try:
        return WarehouseService(db).update_warehouse(warehouse_id, data)
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WarehouseAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("admin"))])
def delete_warehouse(warehouse_id: Annotated[int, Path(ge=1)], db: Annotated[Session, Depends(get_db)]):
    try:
        WarehouseService(db).delete_warehouse(warehouse_id)
    except WarehouseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WarehouseInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
