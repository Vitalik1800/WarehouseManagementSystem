from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.routers.auth import router as auth_router

from backend.app.core.config import get_settings
from backend.app.core.logging_config import (
    get_backend_logger
)


settings = get_settings()
logger = get_backend_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск API системи управління складом")

    yield

    logger.info("Зупинка API системи управління складом")


app = FastAPI(
    title=settings.app_name,
    description="REST API для автоматизації обліку товарів на складі",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan
)

app.include_router(auth_router)


@app.get("/", tags=["Система"])
def root():
    return {
        "application": settings.app_name,
        "message": "API системи управління складом",
        "version": app.version
    }


@app.get("/health", tags=["Система"])
def health_check():
    return {
        "status": "ok",
        "service": "backend"
    }
