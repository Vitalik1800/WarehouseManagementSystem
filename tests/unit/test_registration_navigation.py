from unittest.mock import Mock, patch

import pytest

from frontend.app.components.main_layout import MainLayout
from frontend.app.components.sidebar import Sidebar
from frontend.app.services.user_registration_service import (
    UserRegistrationService,
)


def make_layout(role="admin", api_client=None):
    layout = object.__new__(MainLayout)

    layout.current_user = (
        {"id": 1, "username": "tester", "role": role}
        if role is not None
        else None
    )
    layout.api_client = api_client if api_client is not None else Mock()
    layout.current_page = "dashboard"
    layout.active_view = None

    layout.page_header = Mock()
    layout.sidebar = Mock()
    layout.status_label = Mock()
    layout.page_container = Mock()

    return layout


def test_register_navigation_item_exists():
    assert (
        "register",
        "Реєстрація користувача",
    ) in Sidebar.NAVIGATION_ITEMS


def test_register_page_description_exists():
    assert "register" in MainLayout.PAGE_DESCRIPTIONS


@pytest.mark.parametrize("role", ["worker", None, "manager", ""])
def test_non_admin_cannot_open_register(role):
    layout = make_layout(role=role)

    with pytest.raises(PermissionError):
        layout._show_page("register")

    assert layout.current_page == "dashboard"
    layout.page_header.set_title.assert_not_called()


def test_admin_requires_api_client():
    layout = make_layout()
    layout.api_client = None

    with pytest.raises(RuntimeError):
        layout._show_page("register")

    assert layout.current_page == "dashboard"


def test_admin_opens_register_view():
    client = Mock()
    layout = make_layout(api_client=client)

    with (
        patch(
            "frontend.app.components.main_layout.UserRegistrationService"
        ) as service_class,
        patch(
            "frontend.app.components.main_layout.RegisterView"
        ) as view_class,
    ):
        layout._show_page("register")

    service_class.assert_called_once_with(client)
    view_class.assert_called_once_with(
        layout.page_container,
        registration_service=service_class.return_value,
    )

    view_class.return_value.grid.assert_called_once_with(
        row=0,
        column=0,
        sticky="nsew",
    )

    assert layout.current_page == "register"
    assert layout.active_view is view_class.return_value


def test_switching_to_dashboard_destroys_register_view():
    layout = make_layout()
    previous_view = Mock()
    layout.active_view = previous_view

    with patch(
        "frontend.app.components.main_layout.DashboardView"
    ) as dashboard_class:
        layout._show_page("dashboard")

    previous_view.destroy.assert_called_once()
    dashboard_class.assert_called_once_with(
        layout.page_container,
        api_client=layout.api_client,
    )

    assert layout.active_view is dashboard_class.return_value


def test_sidebar_filters_registration_for_worker():
    sidebar = object.__new__(Sidebar)
    sidebar.user_role = "worker"
    sidebar.buttons = {}

    with (
        patch(
            "frontend.app.components.sidebar.ctk.CTkLabel"
        ),
        patch(
            "frontend.app.components.sidebar.ctk.CTkButton"
        ),
        patch(
            "frontend.app.components.sidebar.ctk.CTkFont"
        ),
    ):
        sidebar._create_widgets()

    assert "dashboard" in sidebar.buttons
    assert "register" not in sidebar.buttons


def test_sidebar_shows_registration_for_admin():
    sidebar = object.__new__(Sidebar)
    sidebar.user_role = "admin"
    sidebar.buttons = {}

    with (
        patch(
            "frontend.app.components.sidebar.ctk.CTkLabel"
        ),
        patch(
            "frontend.app.components.sidebar.ctk.CTkButton"
        ),
        patch(
            "frontend.app.components.sidebar.ctk.CTkFont"
        ),
    ):
        sidebar._create_widgets()

    assert "register" in sidebar.buttons


def test_sidebar_rejects_hidden_registration():
    sidebar = object.__new__(Sidebar)
    sidebar.user_role = "worker"
    sidebar.buttons = {"dashboard": Mock()}
    sidebar.on_navigate = Mock()

    with pytest.raises(ValueError):
        sidebar.navigate("register")

    sidebar.on_navigate.assert_not_called()
