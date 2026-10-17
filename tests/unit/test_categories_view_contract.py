"""Headless contract checks for CategoriesView integration."""
import ast
from pathlib import Path

from frontend.app.views.categories_view import CategoriesView
from frontend.app.components.data_table import DataTable


def test_view_has_expected_operations():
    for name in ("refresh", "load_page", "change_page_size", "create_category", "edit_category", "delete_category", "destroy"):
        assert callable(getattr(CategoriesView, name))


def test_pagination_contract():
    assert CategoriesView.PAGE_SIZE in DataTable.PAGE_SIZE_OPTIONS
    assert DataTable.PAGE_SIZE_OPTIONS == (25, 50, 100)


def test_view_declares_role_guard():
    source = Path(CategoriesView.__module__.replace('.', '/') + '.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name in ("create_category", "edit_category", "delete_category"):
        assert any(isinstance(node, ast.Raise) for node in ast.walk(functions[name]))


def test_main_layout_routes_categories():
    from frontend.app.components.main_layout import MainLayout
    source = Path('frontend/app/components/main_layout.py').read_text(encoding='utf-8')
    assert 'elif page_id == "categories":' in source
    assert 'CategoriesView(' in source
    assert MainLayout is not None
