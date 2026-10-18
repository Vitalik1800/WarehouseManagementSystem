"""Stage 11.5: stock navigation contracts without a running Tk window."""
from unittest.mock import Mock, patch

import pytest

from frontend.app.components.main_layout import MainLayout
from frontend.app.components.sidebar import Sidebar


PAGES = (
    ("stock_movements", "Складські операції", "StockMovementsView"),
    ("stock_balances", "Залишки", "StockBalancesView"),
)


def make_layout(role="admin", *, connected=True):
    layout = object.__new__(MainLayout)
    layout.current_user = ({"id": 1, "role": role} if role is not None else None)
    layout.api_client = Mock() if connected else None
    layout.current_page = "dashboard"
    layout.active_view = None
    layout.page_header = Mock()
    layout.sidebar = Mock()
    layout.status_label = Mock()
    layout.page_container = Mock()
    return layout


@pytest.mark.parametrize("page_id,label,view_name", PAGES)
def test_stock_menu_item_and_description_exist(page_id, label, view_name):
    assert (page_id, label) in Sidebar.NAVIGATION_ITEMS
    assert MainLayout.PAGE_DESCRIPTIONS[page_id]


@pytest.mark.parametrize("page_id,label,view_name", PAGES)
@pytest.mark.parametrize("role", ["admin", "worker"])
def test_stock_page_constructs_expected_view(page_id, label, view_name, role):
    layout = make_layout(role)
    with patch(f"frontend.app.components.main_layout.{view_name}") as view_class:
        layout._show_page(page_id)

    view_class.assert_called_once_with(
        layout.page_container,
        api_client=layout.api_client,
        user_role=role,
    )
    view_class.return_value.grid.assert_called_once_with(
        row=0, column=0, sticky="nsew"
    )
    layout.page_header.set_title.assert_called_once_with(label)
    layout.sidebar.set_active_page.assert_called_once_with(page_id)
    assert layout.current_page == page_id
    assert layout.active_view is view_class.return_value


@pytest.mark.parametrize("page_id,label,view_name", PAGES)
def test_stock_page_destroys_previous_view(page_id, label, view_name):
    layout = make_layout()
    previous = Mock()
    layout.active_view = previous
    with patch(f"frontend.app.components.main_layout.{view_name}") as view_class:
        layout._show_page(page_id)
    previous.destroy.assert_called_once_with()
    assert layout.active_view is view_class.return_value


@pytest.mark.parametrize("page_id,label,view_name", PAGES)
def test_stock_page_requires_api(page_id, label, view_name):
    layout = make_layout(connected=False)
    with patch(f"frontend.app.components.main_layout.{view_name}") as view_class:
        with pytest.raises(RuntimeError, match="підключення до API"):
            layout._show_page(page_id)
    view_class.assert_not_called()


@pytest.mark.parametrize("role", ["admin", "worker"])
def test_sidebar_displays_both_stock_pages(role):
    sidebar = object.__new__(Sidebar)
    sidebar.user_role = role
    sidebar.buttons = {}
    with (
        patch("frontend.app.components.sidebar.ctk.CTkLabel"),
        patch("frontend.app.components.sidebar.ctk.CTkButton"),
        patch("frontend.app.components.sidebar.ctk.CTkFont"),
    ):
        sidebar._create_widgets()
    assert "stock_movements" in sidebar.buttons
    assert "stock_balances" in sidebar.buttons


def test_switching_between_stock_pages_destroys_first_view():
    layout = make_layout()
    with (
        patch("frontend.app.components.main_layout.StockMovementsView") as movements,
        patch("frontend.app.components.main_layout.StockBalancesView") as balances,
    ):
        layout._show_page("stock_movements")
        layout._show_page("stock_balances")
    movements.return_value.destroy.assert_called_once_with()
    assert layout.active_view is balances.return_value
    assert layout.current_page == "stock_balances"
