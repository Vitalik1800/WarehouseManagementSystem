from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from backend.app.core.permissions import require_roles


def test_admin_has_access():
    """Адміністратор має доступ до дозволеної операції."""
    user = Mock()
    user.role = "admin"

    dependency = require_roles("admin")
    result = dependency(current_user=user)

    assert result is user


def test_worker_cannot_access_admin_operation():
    """Працівник отримує HTTP 403 для адміністративної операції."""
    user = Mock()
    user.role = "worker"

    dependency = require_roles("admin")

    with pytest.raises(HTTPException) as exc_info:
        dependency(current_user=user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "Недостатньо прав для виконання цієї дії"
    )


@pytest.mark.parametrize("role", ["admin", "worker"])
def test_multiple_allowed_roles(role):
    """Обидві дозволені ролі проходять перевірку."""
    user = Mock()
    user.role = role

    dependency = require_roles("admin", "worker")
    result = dependency(current_user=user)

    assert result is user


def test_require_roles_without_roles():
    """Порожній перелік ролей заборонений."""
    with pytest.raises(ValueError) as exc_info:
        require_roles()

    assert str(exc_info.value) == (
        "At least one allowed role must be specified"
    )
