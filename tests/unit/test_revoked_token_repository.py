from unittest.mock import Mock

from backend.app.models.revoked_token import RevokedToken
from backend.app.repositories.revoked_token_repository import (
    RevokedTokenRepository,
)

from datetime import datetime, timezone


def test_get_by_jti_success():
    """Перевіряє пошук відкликаного токена за JTI."""
    db = Mock()
    expected_token = RevokedToken(
        id=1,
        jti="550e8400-e29b-41d4-a716-446655440000",
    )

    db.scalar.return_value = expected_token

    repository = RevokedTokenRepository(db)

    result = repository.get_by_jti(
        "550e8400-e29b-41d4-a716-446655440000"
    )

    assert result is expected_token

    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]

    assert str(statement.compile(
        compile_kwargs={"literal_binds": True}
    )).find(
        "'550e8400-e29b-41d4-a716-446655440000'"
    ) != -1


def test_get_by_jti_not_found():
    """Перевіряє пошук JTI, якого немає в базі."""
    db = Mock()
    db.scalar.return_value = None

    repository = RevokedTokenRepository(db)

    result = repository.get_by_jti(
        "550e8400-e29b-41d4-a716-446655440001"
    )

    assert result is None

    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]

    compiled_statement = str(
        statement.compile(
            compile_kwargs={"literal_binds": True}
        )
    )

    assert (
        "'550e8400-e29b-41d4-a716-446655440001'"
        in compiled_statement
    )


def test_is_revoked_true():
    """Перевіряє, що відкликаний JWT розпізнається."""
    db = Mock()

    jti = "550e8400-e29b-41d4-a716-446655440002"

    revoked_token = RevokedToken(
        id=2,
        jti=jti,
    )

    db.scalar.return_value = revoked_token

    repository = RevokedTokenRepository(db)

    result = repository.is_revoked(jti)

    assert result is True

    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]

    compiled_statement = str(
        statement.compile(
            compile_kwargs={"literal_binds": True}
        )
    )

    assert f"'{jti}'" in compiled_statement


def test_is_revoked_false():
    """Перевіряє, що невідкликаний JWT розпізнається."""
    db = Mock()

    jti = "550e8400-e29b-41d4-a716-446655440003"

    db.scalar.return_value = None

    repository = RevokedTokenRepository(db)

    result = repository.is_revoked(jti)

    assert result is False

    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]

    compiled_statement = str(
        statement.compile(
            compile_kwargs={"literal_binds": True}
        )
    )

    assert f"'{jti}'" in compiled_statement


def test_create_revoked_token_success():
    """Перевіряє створення запису відкликаного JWT."""
    db = Mock()

    jti = "550e8400-e29b-41d4-a716-446655440004"

    expires_at = datetime(
        2026, 10, 10, 12, 0, 0,
        tzinfo=timezone.utc
    )

    repository = RevokedTokenRepository(db)

    result = repository.create(
        jti=jti,
        expires_at=expires_at
    )

    assert isinstance(result, RevokedToken)

    assert result.jti == jti
    assert result.expires_at == expires_at

    db.add.assert_called_once_with(result)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
