"""Secure CLI bootstrap for the initial warehouse administrator."""

import getpass
import re

from sqlalchemy.exc import IntegrityError

from backend.app.core.security import hash_password
from backend.app.db.session import SessionLocal
from backend.app.repositories.user_repository import UserRepository


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,50}$")


def has_active_admin(repository: UserRepository) -> bool:
    return repository.count_active_admins() > 0


def read_admin_credentials() -> tuple[str, str, str]:
    name = input("Administrator name: ").strip()
    username = input("Administrator username: ").strip()

    if not 2 <= len(name) <= 150:
        raise ValueError(
            "Administrator name must contain 2-150 characters."
        )

    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username must contain 3-50 letters, digits or underscores."
        )

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if not 8 <= len(password) <= 128:
        raise ValueError(
            "Password must contain 8-128 characters."
        )

    if password != confirmation:
        raise ValueError("Passwords do not match.")

    return name, username, password


def bootstrap_admin() -> int:
    with SessionLocal() as db:
        repository = UserRepository(db)

        if has_active_admin(repository):
            print("An active administrator already exists.")
            return 1

        try:
            name, username, password = read_admin_credentials()

            if repository.get_by_username(username) is not None:
                raise ValueError(
                    "This username is already in use."
                )

            # Recheck inside the transaction before creating a user.
            if has_active_admin(repository):
                print("An active administrator already exists.")
                return 1

            user = repository.create(
                name=name,
                username=username,
                password_hash=hash_password(password),
                role="admin",
            )

            db.commit()

            print(
                f"Administrator '{user.username}' created successfully."
            )

            return 0

        except (ValueError, IntegrityError) as exc:
            db.rollback()

            if isinstance(exc, IntegrityError):
                print("Database integrity error during bootstrap.")
            else:
                print(f"Bootstrap failed: {exc}")

            return 1

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    raise SystemExit(bootstrap_admin())
