import logging
import sys

from logging.handlers import RotatingFileHandler
from pathlib import Path

from frontend.app.core.config import (
    get_frontend_settings
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIRECTORY = PROJECT_ROOT / "logs" / "frontend"
LOG_FILE = LOG_DIRECTORY / "frontend.log"

LOGGER_NAME = "warehouse.frontend"

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(name)s | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_frontend_logging() -> logging.Logger:
    get_frontend_settings()

    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    logger = logging.getLogger(LOGGER_NAME)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT
    )

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )

    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_frontend_logger(
    name: str | None = None
) -> logging.Logger:
    setup_frontend_logging()

    if name:
        return logging.getLogger(
            f"{LOGGER_NAME}.{name}"
        )

    return logging.getLogger(LOGGER_NAME)
