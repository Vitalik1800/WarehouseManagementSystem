from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.user import User
from backend.app.schemas.users import UserRoleUpdate
from backend.app.services.user_service import (
    LastActiveAdminError,
    UserService,
)
from tests.db_config import create_test_engine


def test_concurrent_admin_demotions_preserve_active_admin():
    engine = create_test_engine()

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    prefix = uuid4().hex[:12]
    admin_ids = []

    try:
        # Створюємо двох активних адміністраторів.
        with session_factory() as session:
            existing_admins = session.scalar(
                select(User).where(
                    User.role == "admin",
                    User.is_active.is_(True),
                ).limit(1)
            )

            assert existing_admins is None, (
                "Для конкурентного тесту потрібна база "
                "без інших активних адміністраторів"
            )

            for index in range(2):
                admin = User(
                    name=f"Concurrency Admin {index}",
                    username=f"concurrent_{prefix}_{index}",
                    password_hash="test_hash",
                    role="admin",
                    is_active=True,
                )
                session.add(admin)
                session.flush()
                admin_ids.append(admin.id)

            session.commit()

        # Синхронізуємо старт двох потоків.
        barrier = Barrier(2)

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
                executor.submit(demote_admin, admin_id)
                for admin_id in admin_ids
            ]

            results = [
                future.result(timeout=30)
                for future in futures
            ]

        # Перевіряємо кінцевий стан.
        with session_factory() as session:
            remaining_admins = session.scalars(
                select(User).where(
                    User.id.in_(admin_ids),
                    User.role == "admin",
                    User.is_active.is_(True),
                )
            ).all()

            assert len(remaining_admins) >= 1

            assert results.count("success") == 1
            assert results.count("protected") == 1

    finally:
        # Видаляємо тільки користувачів цього тесту.
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
