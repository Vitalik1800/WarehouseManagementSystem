from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.routers.auth import router as auth_router
from backend.app.api.routers.users import router as users_router
from backend.app.api.routers.categories import router as categories_router
from backend.app.api.routers.suppliers import router as suppliers_router
from backend.app.api.routers.storage_locations import router as locations_router
from backend.app.api.routers.products import router as products_router
from backend.app.api.routers.stock_movements import router as stock_movements_router
from backend.app.api.routers.stock_balances import router as stock_balances_router
from backend.app.api.routers.user_activity_logs import router as user_activity_logs_router
from backend.app.api.routers.dashboard import router as dashboard_router
from backend.app.api.routers.warehouses import router as warehouses_router

from backend.app.core.config import get_settings
from backend.app.core.logging_config import (
    get_backend_logger
)


settings = get_settings()
logger = get_backend_logger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Запуск API системи управління складом")

    yield

    logger.info("Зупинка API системи управління складом")


app = FastAPI(
    title=settings.app_name,
    description="REST API для автоматизації обліку товарів на складі",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(categories_router)
app.include_router(suppliers_router)
app.include_router(locations_router)
app.include_router(products_router)
app.include_router(stock_movements_router)
app.include_router(stock_balances_router)
app.include_router(user_activity_logs_router)
app.include_router(dashboard_router)
app.include_router(warehouses_router)


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
