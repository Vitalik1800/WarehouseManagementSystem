import pytest

from pymysql.err import IntegrityError as PyMySQLIntegrityError
from sqlalchemy.exc import IntegrityError

from backend.app.core.database_errors import (
    MYSQL_DUPLICATE_ENTRY,
    MYSQL_NO_REFERENCED_ROW,
    MYSQL_ROW_IS_REFERENCED,
    get_mysql_error_code,
    is_duplicate_entry,
    is_missing_reference,
    is_row_referenced,
)


def make_integrity_error(code: int) -> IntegrityError:
    original_error = PyMySQLIntegrityError(
        code,
        "Test database integrity error",
    )

    return IntegrityError(
        statement="TEST",
        params={},
        orig=original_error,
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1062, True),
        (1451, False),
        (1452, False),
        (1048, False),
    ],
)
def test_is_duplicate_entry(
    code: int,
    expected: bool,
) -> None:
    error = make_integrity_error(code)

    assert is_duplicate_entry(error) is expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1062, False),
        (1451, True),
        (1452, False),
        (1048, False),
    ],
)
def test_is_row_referenced(
    code: int,
    expected: bool,
) -> None:
    error = make_integrity_error(code)

    assert is_row_referenced(error) is expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1062, False),
        (1451, False),
        (1452, True),
        (1048, False),
    ],
)
def test_is_missing_reference(
    code: int,
    expected: bool,
) -> None:
    error = make_integrity_error(code)

    assert is_missing_reference(error) is expected


@pytest.mark.parametrize(
    "code",
    [
        1062,
        1451,
        1452,
        1048,
        9999,
    ],
)
def test_get_mysql_error_code(code: int) -> None:
    error = make_integrity_error(code)

    assert get_mysql_error_code(error) == code


def test_get_mysql_error_code_without_arguments() -> None:
    error = IntegrityError(
        statement="TEST",
        params={},
        orig=Exception(),
    )

    assert get_mysql_error_code(error) is None


def test_get_mysql_error_code_with_string_code() -> None:
    error = IntegrityError(
        statement="TEST",
        params={},
        orig=Exception("1062", "Test error"),
    )

    assert get_mysql_error_code(error) is None


def test_get_mysql_error_code_with_boolean_code() -> None:
    error = IntegrityError(
        statement="TEST",
        params={},
        orig=Exception(True, "Test error"),
    )

    assert get_mysql_error_code(error) is None


def test_mysql_error_constants() -> None:
    assert MYSQL_DUPLICATE_ENTRY == 1062
    assert MYSQL_ROW_IS_REFERENCED == 1451
    assert MYSQL_NO_REFERENCED_ROW == 1452
