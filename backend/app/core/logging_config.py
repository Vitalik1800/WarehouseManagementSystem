import logging
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIRECTORY = PROJECT_ROOT / "logs" / "backend"
LOG_FILE = LOG_DIRECTORY / "backend.log"

LOGGER_NAME = "warehouse.backend"

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(name)s | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_backend_logging() -> logging.Logger:
    settings = get_settings()

    log_level = getattr(logging, settings.log_level)

    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    logger = logging.getLogger(LOGGER_NAME)

    logger.setLevel(
        log_level
    )

    logger.propagate = False

    # Avoid adding duplicate handlers.

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT
    )

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    console_handler.setLevel(
        log_level
    )

    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )

    file_handler.setLevel(
        log_level
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_backend_logger(
        name: str | None = None
) -> logging.Logger:
    setup_backend_logging()

    if name:
        return logging.getLogger(
            f"{LOGGER_NAME}.{name}"
        )

    return logging.getLogger(LOGGER_NAME)
