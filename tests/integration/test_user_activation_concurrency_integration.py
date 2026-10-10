from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.models.user import User
from backend.app.services.user_service import (
    LastActiveAdminError,
    UserService,
)
from tests.db_config import create_test_engine

from backend.app.schemas.users import UserRoleUpdate


def test_concurrent_admin_deactivations_preserve_active_admin():
    engine = create_test_engine()

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    prefix = uuid4().hex[:12]
    admin_ids = []

    try:
        # Переконуємося, що немає інших активних адміністраторів.
        with session_factory() as session:
            existing_admin = session.scalar(
                select(User).where(
                    User.role == "admin",
                    User.is_active.is_(True),
                ).limit(1)
            )

            assert existing_admin is None, (
                "Для конкурентного тесту потрібна база "
                "без інших активних адміністраторів"
            )

            # Створюємо двох активних адміністраторів.
            for index in range(2):
                admin = User(
                    name=f"Activation Concurrency Admin {index}",
                    username=f"activation_concurrent_{prefix}_{index}",
                    password_hash="test_hash",
                    role="admin",
                    is_active=True,
                )

                session.add(admin)
                session.flush()
                admin_ids.append(admin.id)

            session.commit()

        # Синхронізуємо запуск двох потоків.
        barrier = Barrier(2)

        def deactivate_admin(user_id: int):
            with session_factory() as session:
                service = UserService(session)

                barrier.wait(timeout=10)

                try:
                    service.set_user_active(
                        user_id=user_id,
                        is_active=False,
                    )
                    return "success"

                except LastActiveAdminError:
                    return "protected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(deactivate_admin, admin_id)
                for admin_id in admin_ids
            ]

            results = [
                future.result(timeout=30)
                for future in futures
            ]

        # Перевіряємо кінцевий стан бази.
        with session_factory() as session:
            remaining_admins = session.scalars(
                select(User).where(
                    User.id.in_(admin_ids),
                    User.role == "admin",
                    User.is_active.is_(True),
                )
            ).all()

            assert len(remaining_admins) == 1

            assert results.count("success") == 1
            assert results.count("protected") == 1

    finally:
        # Видаляємо тільки записи, створені цим тестом.
        try:
            if admin_ids:
                with session_factory() as session:
                    users = session.scalars(
                        select(User).where(
                            User.id.in_(admin_ids)
                        )
                    ).all()

                    for user in users:
                        session.delete(user)

                    session.commit()
        finally:
            engine.dispose()


def test_concurrent_deactivation_and_demotion_preserve_active_admin():
    engine = create_test_engine()

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    prefix = uuid4().hex[:12]
    admin_ids = []

    try:
        with session_factory() as session:
            existing_admin = session.scalar(
                select(User).where(
                    User.role == "admin",
                    User.is_active.is_(True),
                ).limit(1)
            )

            assert existing_admin is None, (
                "Для конкурентного тесту потрібна база "
                "без інших активних адміністраторів"
            )

            for index in range(2):
                admin = User(
                    name=f"Mixed Concurrency Admin {index}",
                    username=f"mixed_concurrent_{prefix}_{index}",
                    password_hash="test_hash",
                    role="admin",
                    is_active=True,
                )

                session.add(admin)
                session.flush()
                admin_ids.append(admin.id)

            session.commit()

        barrier = Barrier(2)

        def deactivate_admin(user_id: int):
            with session_factory() as session:
                service = UserService(session)
                barrier.wait(timeout=10)

                try:
                    service.set_user_active(
                        user_id=user_id,
                        is_active=False,
                    )
                    return "success"

                except LastActiveAdminError:
                    return "protected"

        def demote_admin(user_id: int):
            with session_factory() as session:
                service = UserService(session)
                barrier.wait(timeout=10)

                try:
                    service.change_user_role(
                        user_id,
                        UserRoleUpdate(role="worker"),
                    )
                    return "success"

                except LastActiveAdminError:
                    return "protected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(deactivate_admin, admin_ids[0]),
                executor.submit(demote_admin, admin_ids[1]),
            ]

            results = [
                future.result(timeout=30)
                for future in futures
            ]

        with session_factory() as session:
            remaining_admins = session.scalars(
                select(User).where(
                    User.id.in_(admin_ids),
                    User.role == "admin",
                    User.is_active.is_(True),
                )
            ).all()

            assert len(remaining_admins) == 1
            assert results.count("success") == 1
            assert results.count("protected") == 1

    finally:
        try:
            if admin_ids:
                with session_factory() as session:
                    users = session.scalars(
                        select(User).where(
                            User.id.in_(admin_ids)
                        )
                    ).all()

                    for user in users:
                        session.delete(user)

                    session.commit()
        finally:
            engine.dispose()
