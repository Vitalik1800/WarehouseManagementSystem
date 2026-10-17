import pytest

from frontend.app.components.main_layout import MainLayout
from frontend.app.components.sidebar import Sidebar


def make_layout(current_user):
    layout = object.__new__(MainLayout)
    layout.current_user = current_user
    layout.api_client = None
    return layout


def test_users_navigation_item_exists():
    assert ("users", "Користувачі") in Sidebar.NAVIGATION_ITEMS


@pytest.mark.parametrize(
    "current_user",
    [
        {"id": 2, "role": "worker"},
        {"id": 3, "role": "guest"},
        {"id": 4},
        None,
    ],
)
def test_users_page_rejects_non_admin(current_user):
    layout = make_layout(current_user)

    with pytest.raises(
        PermissionError,
        match="Лише адміністратор",
    ):
        MainLayout._show_page(layout, "users")


@pytest.mark.parametrize(
    "current_user",
    [
        {"id": 2, "role": "worker"},
        {"id": 3, "role": "guest"},
        None,
    ],
)
def test_register_page_rejects_non_admin(current_user):
    layout = make_layout(current_user)

    with pytest.raises(
        PermissionError,
        match="Лише адміністратор",
    ):
        MainLayout._show_page(layout, "register")


@pytest.mark.parametrize(
    "page_id",
    ["users", "register"],
)
def test_admin_page_requires_api_client(page_id):
    layout = make_layout(
        {"id": 1, "role": "admin"}
    )

    with pytest.raises(
        RuntimeError,
        match="підключення до API",
    ):
        MainLayout._show_page(layout, page_id)


def test_unknown_page_is_rejected():
    layout = make_layout(
        {"id": 1, "role": "admin"}
    )

    with pytest.raises(
        ValueError,
        match="Unknown page",
    ):
        MainLayout._show_page(layout, "unknown_page")
