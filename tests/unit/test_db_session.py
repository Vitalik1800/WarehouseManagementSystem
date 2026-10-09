from unittest.mock import Mock, patch

import pytest

from backend.app.db.session import get_db


def test_get_db_closes_session_after_use():
    """Checks that the database session closes after use."""

    db = Mock()

    with patch(
        "backend.app.db.session.SessionLocal",
        return_value=db,
    ) as session_factory:
        generator = get_db()

        session = next(generator)

        assert session is db
        db.close.assert_not_called()

        with pytest.raises(StopIteration):
            next(generator)

        session_factory.assert_called_once_with()
        db.close.assert_called_once()


def test_get_db_closes_session_on_exception():
    """Checks that the database session closes on error."""

    db = Mock()

    with patch(
        "backend.app.db.session.SessionLocal",
        return_value=db,
    ):
        generator = get_db()

        session = next(generator)

        assert session is db

        with pytest.raises(RuntimeError, match="Test database error"):
            generator.throw(
                RuntimeError("Test database error")
            )

        db.close.assert_called_once()
