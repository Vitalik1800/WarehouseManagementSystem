from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from backend.app.core.permissions import require_roles
from backend.app.db.session import get_db
from backend.app.schemas.storage_locations import (
    StorageLocationCreate,
    StorageLocationUpdate,
    StorageLocationResponse,
)
from backend.app.services.storage_location_service import (
    StorageLocationService,
    StorageLocationNotFoundError,
    StorageLocationAlreadyExistsError,
    StorageLocationInUseError,
)


router = APIRouter(
    prefix="/storage-locations",
    tags=["Storage Locations"]
)


@router.get(
    "",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=list[StorageLocationResponse],
    status_code=status.HTTP_200_OK,
    summary="List storage locations",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation error"}
    }
)
def list_storage_locations(
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[StorageLocationResponse]:
    locations = StorageLocationService(db).list_locations(
        offset=offset,
        limit=limit
    )

    return [
        StorageLocationResponse.model_validate(location)
        for location in locations
    ]


@router.get(
    "/{location_id}",
    dependencies=[
        Depends(require_roles("admin", "worker"))
    ],
    response_model=StorageLocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get storage location by ID",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Storage location not found"},
        422: {"description": "Validation error"}
    }
)
def get_storage_location(
    location_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> StorageLocationResponse:
    service = StorageLocationService(db)

    try:
        location = service.get_location(location_id)

    except StorageLocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StorageLocationResponse.model_validate(location)


@router.post(
    "",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=StorageLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create storage location",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        409: {"description": "Storage location already exists"},
        422: {"description": "Validation error"}
    }
)
def create_storage_location(
    data: StorageLocationCreate,
    db: Annotated[Session, Depends(get_db)]
) -> StorageLocationResponse:
    service = StorageLocationService(db)

    try:
        location = service.create_location(data)

    except StorageLocationAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return StorageLocationResponse.model_validate(location)


@router.patch(
    "/{location_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    response_model=StorageLocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update storage location",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Storage location not found"},
        409: {"description": "Storage location already exists"},
        422: {"description": "Validation error"}
    }
)
def update_storage_location(
    location_id: Annotated[int, Path(ge=1)],
    data: StorageLocationUpdate,
    db: Annotated[Session, Depends(get_db)]
) -> StorageLocationResponse:
    service = StorageLocationService(db)

    try:
        location = service.update_location(
            location_id=location_id,
            data=data
        )

    except StorageLocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except StorageLocationAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return StorageLocationResponse.model_validate(location)


@router.delete(
    "/{location_id}",
    dependencies=[
        Depends(require_roles("admin"))
    ],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete storage location",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Storage location not found"},
        409: {"description": "Storage location is in use"},
        422: {"description": "Validation error"}
    }
)
def delete_storage_location(
    location_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)]
) -> Response:
    service = StorageLocationService(db)

    try:
        service.delete_location(location_id)

    except StorageLocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except StorageLocationInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
