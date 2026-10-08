from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.core.config import get_settings
from backend.app.core.logging_config import (
    get_backend_logger
)


settings = get_settings()
logger = get_backend_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WarehouseManagementSystem API starting")

    yield

    logger.info("WarehouseManagementSystem API stopping")


app = FastAPI(
    title=settings.app_name,
    description="REST API for warehouse inventory management",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan
)


@app.get("/", tags=["System"])
def root():
    return {
        "application": settings.app_name,
        "message": "WarehouseManagementSystem API",
        "version": app.version
    }


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "backend"
    }
