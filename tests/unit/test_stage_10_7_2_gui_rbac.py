"""Stage 10.7.2: GUI navigation and role checks (no live backend)."""
from unittest.mock import Mock, patch

import pytest

from frontend.app.components.main_layout import MainLayout
from frontend.app.components.sidebar import Sidebar
from frontend.app.views.categories_view import CategoriesView
from frontend.app.views.products_view import ProductsView
from frontend.app.views.storage_locations_view import StorageLocationsView
from frontend.app.views.suppliers_view import SuppliersView


PAGES = (
    ("products", "ProductsView"),
    ("categories", "CategoriesView"),
    ("suppliers", "SuppliersView"),
    ("storage_locations", "StorageLocationsView"),
)

MUTATORS = (
    (ProductsView, "create_product", "edit_product", "delete_product"),
    (CategoriesView, "create_category", "edit_category", "delete_category"),
    (SuppliersView, "create_supplier", "edit_supplier", "delete_supplier"),
    (StorageLocationsView, "create_location", "edit_location", "delete_location"),
)


def make_layout(role):
    layout = object.__new__(MainLayout)
    layout.current_user = {"id": 1, "role": role}
    layout.api_client = Mock()
    layout.current_page = "dashboard"
    layout.active_view = None
    layout.page_header = Mock()
    layout.sidebar = Mock()
    layout.status_label = Mock()
    layout.page_container = Mock()
    return layout


@pytest.mark.parametrize("role", ["worker", "admin"])
@pytest.mark.parametrize("page_id,view_name", PAGES)
def test_reference_page_passes_role_to_view(role, page_id, view_name):
    layout = make_layout(role)
    with patch(f"frontend.app.components.main_layout.{view_name}") as view_class:
        layout._show_page(page_id)
    view_class.assert_called_once_with(
        layout.page_container, api_client=layout.api_client, user_role=role
    )
    view_class.return_value.grid.assert_called_once_with(
        row=0, column=0, sticky="nsew"
    )
    assert layout.current_page == page_id
    assert layout.active_view is view_class.return_value


@pytest.mark.parametrize("view_class,create,edit,delete", MUTATORS)
def test_worker_cannot_call_mutating_view_methods(view_class, create, edit, delete):
    view = object.__new__(view_class)
    view.user_role = "worker"
    for name in (create, edit, delete):
        with pytest.raises(PermissionError):
            getattr(view_class, name)(view)


@pytest.mark.parametrize("role", ["worker", "admin"])
def test_sidebar_shows_reference_pages(role):
    sidebar = object.__new__(Sidebar)
    sidebar.user_role = role
    sidebar.buttons = {}
    with (
        patch("frontend.app.components.sidebar.ctk.CTkLabel"),
        patch("frontend.app.components.sidebar.ctk.CTkButton"),
        patch("frontend.app.components.sidebar.ctk.CTkFont"),
    ):
        sidebar._create_widgets()
    assert all(page_id in sidebar.buttons for page_id, _ in PAGES)
    assert ("users" in sidebar.buttons) is (role == "admin")
    assert ("register" in sidebar.buttons) is (role == "admin")


@pytest.mark.parametrize("page_id,view_name", PAGES)
def test_switching_reference_pages_destroys_previous_view(page_id, view_name):
    layout = make_layout("worker")
    old_view = Mock()
    layout.active_view = old_view
    with patch(f"frontend.app.components.main_layout.{view_name}"):
        layout._show_page(page_id)
    old_view.destroy.assert_called_once_with()
