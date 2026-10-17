from unittest.mock import Mock

import pytest

from frontend.app.components.data_table import DataTable


def make_table(
    mode="server",
    page=1,
    has_next=False,
    loading=False,
):
    table = object.__new__(DataTable)
    table.pagination_mode = mode
    table.current_page = page
    table.page_size = 25
    table.rows = []
    table.columns = ("ID", "Name")
    table.has_next_page = has_next
    table.pagination_loading = loading
    table.on_page_change = Mock()
    table.on_page_size_change = Mock()
    table._render_page = Mock()
    return table


def test_server_total_pages_without_next():
    table = make_table(page=3, has_next=False)

    assert table.get_total_pages() == 3


def test_server_total_pages_with_next():
    table = make_table(page=3, has_next=True)

    assert table.get_total_pages() == 4


def test_server_visible_rows_are_not_sliced():
    table = make_table(page=5)
    table.rows = [(i, f"User {i}") for i in range(25)]

    assert table.get_visible_rows() == table.rows


def test_server_next_page_callback():
    table = make_table(page=2, has_next=True)

    table.next_page()

    table.on_page_change.assert_called_once_with(3)
    assert table.current_page == 2


def test_server_previous_page_callback():
    table = make_table(page=3)

    table.previous_page()

    table.on_page_change.assert_called_once_with(2)
    assert table.current_page == 3


def test_server_first_page_cannot_go_back():
    table = make_table(page=1)

    table.previous_page()

    table.on_page_change.assert_not_called()


def test_server_last_page_cannot_go_forward():
    table = make_table(page=2, has_next=False)

    table.next_page()

    table.on_page_change.assert_not_called()


def test_server_loading_blocks_navigation():
    table = make_table(
        page=2,
        has_next=True,
        loading=True,
    )

    table.next_page()
    table.previous_page()

    table.on_page_change.assert_not_called()


def test_server_set_page():
    table = make_table()

    table.set_server_page(
        [(26, "User 26")],
        page=2,
        has_next_page=True,
    )

    assert table.current_page == 2
    assert table.has_next_page is True
    assert table.rows == [(26, "User 26")]
    table._render_page.assert_called()


def test_server_set_page_rejects_invalid_number():
    table = make_table()

    with pytest.raises(ValueError):
        table.set_server_page([], page=0, has_next_page=False)


def test_client_rejects_server_page():
    table = make_table(mode="client")

    with pytest.raises(RuntimeError):
        table.set_server_page([], page=1, has_next_page=False)



def test_server_loading_can_be_cleared_after_error():
    table = make_table(loading=True)

    table.set_pagination_loading(False)

    assert table.pagination_loading is False
    table._render_page.assert_called_once()


def test_server_rejects_navigation_beyond_last_page():
    table = make_table(page=4, has_next=False)

    with pytest.raises(ValueError):
        table.go_to_page(5)

    table.on_page_change.assert_not_called()


def test_server_loading_state():
    table = make_table()

    table.set_pagination_loading(True)

    assert table.pagination_loading is True
    table._render_page.assert_called_once()


def test_client_total_pages_unchanged():
    table = make_table(mode="client")
    table.rows = [(i, str(i)) for i in range(51)]

    assert table.get_total_pages() == 3


def test_client_visible_rows_unchanged():
    table = make_table(mode="client", page=2)
    table.rows = [(i, str(i)) for i in range(60)]

    assert table.get_visible_rows() == table.rows[25:50]


def test_server_page_size_callback():
    table = make_table()
    table.page_size_selector = Mock()

    table._on_page_size_change("50")

    table.on_page_size_change.assert_called_once_with(50)
    assert table.page_size == 25


def test_server_page_size_without_callback():
    table = make_table()
    table.page_size_selector = Mock()
    table.on_page_size_change = None

    table._on_page_size_change("50")

    table.page_size_selector.set.assert_called_once_with("25")
    assert table.page_size == 25
