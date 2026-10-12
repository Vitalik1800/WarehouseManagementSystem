from sqlalchemy.exc import IntegrityError


MYSQL_DUPLICATE_ENTRY = 1062
MYSQL_ROW_IS_REFERENCED = 1451
MYSQL_NO_REFERENCED_ROW = 1452


def get_mysql_error_code(
    error: IntegrityError
) -> int | None:
    """Extract MySQL error code from SQLAlchemy IntegrityError."""

    original_error = error.orig
    arguments = getattr(original_error, "args", ())

    if not arguments:
        return None

    code = arguments[0]

    if isinstance(code, int) and not isinstance(code, bool):
        return code

    return None


def is_duplicate_entry(
    error: IntegrityError
) -> bool:
    """Check whether a unique constraint was violated."""

    return get_mysql_error_code(error) == MYSQL_DUPLICATE_ENTRY


def is_row_referenced(
    error: IntegrityError
) -> bool:
    """Check whether a referenced parent row cannot be deleted."""

    return get_mysql_error_code(error) == MYSQL_ROW_IS_REFERENCED


def is_missing_reference(
    error: IntegrityError
) -> bool:
    """Check whether a referenced row does not exist."""

    return get_mysql_error_code(error) == MYSQL_NO_REFERENCED_ROW
