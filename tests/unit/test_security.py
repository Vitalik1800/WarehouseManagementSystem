from backend.app.core.security import (
    hash_password,
    verify_password,
)


def test_password_hash_uses_argon2id():
    password_hash = hash_password("StrongPass123")

    assert password_hash.startswith("$argon2id$")


def test_password_hash_is_not_plaintext():
    password = "StrongPass123"

    password_hash = hash_password(password)

    assert password_hash != password


def test_correct_password_verification():
    password = "StrongPass123"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_incorrect_password_verification():
    password_hash = hash_password("StrongPass123")

    assert verify_password(
        "WrongPass123",
        password_hash,
    ) is False


def test_same_password_produces_different_hashes():
    password = "StrongPass123"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash

    assert verify_password(password, first_hash) is True
    assert verify_password(password, second_hash) is True


def test_unicode_password():
    password = "МійНадійнийПароль123!"

    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True
    assert verify_password("ІншийПароль123!", password_hash) is False
