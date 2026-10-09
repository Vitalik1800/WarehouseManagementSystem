from backend.app.core.logging_config import (
    setup_backend_logging
)

from backend.app.core.logging_config import (
    LOGGER_NAME,
    get_backend_logger,
    setup_backend_logging
)


def test_setup_backend_logging_does_not_duplicate_handlers():
    """Repeated setup must not add duplicate logging handlers."""

    logger = setup_backend_logging()

    original_handlers = tuple(logger.handlers)

    logger_again = setup_backend_logging()

    assert logger_again is logger
    assert tuple(logger_again.handlers) == original_handlers


def test_get_backend_logger_without_name():
    """Returns the main backend logger when no name is provided."""

    logger = get_backend_logger()

    assert logger.name == LOGGER_NAME
    assert logger is setup_backend_logging()
