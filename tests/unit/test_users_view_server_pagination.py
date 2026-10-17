from concurrent.futures import Future
from unittest.mock import Mock

import pytest

from frontend.app.views.users_view import UsersView


def make_view():
    view = object.__new__(UsersView)

    view._closed = False
    view._future = None
    view._poll_job = None
    view.current_page = 1
    view._requested_page = 1

    view.PAGE_SIZE = 25
    view._requested_page_size = 25
    view.table = Mock()
    view.table.page_size = 25
    view.table.page_size = 25
    view._requested_page_size = 25
    view.table.page_size = 25
    view.POLL_INTERVAL_MS = 50

    view.table = Mock()
    view.table.page_size = 25
    view.status_label = Mock()
    view.refresh_button = Mock()
    view.user_service = Mock()
    view._executor = Mock()
    view.after = Mock(return_value="poll-job")

    return view


def make_user(user_id):
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "username": f"user{user_id}",
        "role": "admin",
        "is_active": True,
    }


def test_load_first_page():
    view = make_view()

    view.load_page(1)

    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        0,
        26,
    )
    view.table.set_pagination_loading.assert_called_with(True)


def test_load_second_page():
    view = make_view()

    view.load_page(2)

    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        25,
        26,
    )


def test_load_fourth_page():
    view = make_view()

    view.load_page(4)

    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        75,
        26,
    )


def test_refresh_current_page():
    view = make_view()
    view.current_page = 3

    view.refresh()

    assert view._requested_page == 3
    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        50,
        26,
    )


def test_invalid_page_rejected():
    view = make_view()

    with pytest.raises(ValueError):
        view.load_page(0)

    view._executor.submit.assert_not_called()


def test_loading_blocks_duplicate_request():
    view = make_view()
    view._future = Mock()

    view.load_page(2)

    view._executor.submit.assert_not_called()


def test_closed_view_does_not_load():
    view = make_view()
    view._closed = True

    view.load_page(2)

    view._executor.submit.assert_not_called()


def test_start_loading_schedules_poll():
    view = make_view()

    view.load_page(2)

    view.after.assert_called_once_with(
        view.POLL_INTERVAL_MS,
        view._check_result,
    )


def test_apply_users_updates_server_page():
    view = make_view()

    view._apply_users(
        [make_user(26)],
        page=2,
        has_next_page=True,
    )

    view.table.set_server_page.assert_called_once()
    args, kwargs = view.table.set_server_page.call_args

    assert len(args[0]) == 1
    assert kwargs["page"] == 2
    assert kwargs["has_next_page"] is True
    assert view.current_page == 2


def test_apply_users_formats_user_row():
    view = make_view()

    view._apply_users(
        [make_user(1)],
        page=1,
        has_next_page=False,
    )

    rows = view.table.set_server_page.call_args.args[0]

    assert rows == [
        (
            1,
            "User 1",
            "user1",
            "Адміністратор",
            "Активний",
        )
    ]


def test_completed_future_detects_next_page():
    view = make_view()
    future = Future()
    future.set_result([make_user(i) for i in range(1, 27)])

    view._future = future
    view._requested_page = 1

    view._check_result()

    args, kwargs = view.table.set_server_page.call_args

    assert len(args[0]) == 25
    assert kwargs["page"] == 1
    assert kwargs["has_next_page"] is True
    assert view._future is None
    view.table.set_pagination_loading.assert_called_with(False)


def test_completed_future_detects_last_page():
    view = make_view()
    future = Future()
    future.set_result([make_user(i) for i in range(1, 11)])

    view._future = future
    view._requested_page = 1

    view._check_result()

    args, kwargs = view.table.set_server_page.call_args

    assert len(args[0]) == 10
    assert kwargs["has_next_page"] is False


def test_failed_future_unlocks_pagination():
    view = make_view()
    future = Future()
    future.set_exception(RuntimeError("Test failure"))

    view._future = future

    view._check_result()

    assert view._future is None
    view.table.set_pagination_loading.assert_called_with(False)
    view.refresh_button.configure.assert_called_with(
        state="normal"
    )


def test_unfinished_future_reschedules_poll():
    view = make_view()
    view._future = Future()

    view._check_result()

    assert view._future is not None
    view.after.assert_called_once_with(
        view.POLL_INTERVAL_MS,
        view._check_result,
    )


def test_empty_first_page_is_valid():
    view = make_view()
    future = Future()
    future.set_result([])

    view._future = future
    view._requested_page = 1

    view._check_result()

    view.table.set_server_page.assert_called_once_with(
        [],
        page=1,
        has_next_page=False,
    )


def test_empty_later_page_does_not_replace_data():
    view = make_view()
    view.current_page = 2
    view._requested_page = 3

    future = Future()
    future.set_result([])
    view._future = future

    view._check_result()

    view.table.set_server_page.assert_not_called()
    assert view.current_page == 2
    # Попередній запит завершився, але fallback
    # уже запустив завантаження попередньої сторінки.
    assert [
        call.args[0]
        for call in view.table.set_pagination_loading.call_args_list
    ] == [False, True]

    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        25,
        26,
    )

    assert view._requested_page == 2


def test_empty_later_page_automatically_loads_previous():
    view = make_view()
    view.current_page = 3
    view._requested_page = 4

    future = Future()
    future.set_result([])
    view._future = future

    view._check_result()

    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        50,
        26,
    )
    assert view._requested_page == 3
    view.table.set_server_page.assert_not_called()


def test_multiple_empty_pages_fallback():
    view = make_view()
    view.current_page = 5
    view._requested_page = 5

    def complete_page(page, users):
        future = Future()
        future.set_result(users)
        view._future = future
        view._requested_page = page
        view._check_result()

    complete_page(5, [])
    assert view._requested_page == 4
    assert view.current_page == 5

    complete_page(4, [])
    assert view._requested_page == 3
    assert view.current_page == 5

    complete_page(3, [])
    assert view._requested_page == 2
    assert view.current_page == 5

    complete_page(2, [make_user(26)])

    assert view.current_page == 2
    assert view.table.set_server_page.call_count == 1

    args, kwargs = view.table.set_server_page.call_args

    assert len(args[0]) == 1
    assert kwargs["page"] == 2
    assert kwargs["has_next_page"] is False

    assert view._executor.submit.call_count == 3

    offsets = [
        call.args[1]
        for call in view._executor.submit.call_args_list
    ]

    assert offsets == [75, 50, 25]


def test_executor_submit_failure_restores_ui():
    view = make_view()

    view._executor.submit.side_effect = RuntimeError(
        "Executor has been shut down"
    )

    view.load_page(2)

    assert view._future is None
    assert view._requested_page == 2
    assert view.current_page == 1

    assert [
        call.args[0]
        for call in view.table.set_pagination_loading.call_args_list
    ] == [True, False]

    view.refresh_button.configure.assert_any_call(
        state="disabled"
    )
    view.refresh_button.configure.assert_any_call(
        state="normal"
    )

    view.status_label.configure.assert_any_call(
        text="Не вдалося запустити завантаження"
    )

    view.after.assert_not_called()
    assert view._poll_job is None


def test_change_page_size_requests_50():
    view = make_view()

    view.change_page_size(50)

    assert view._requested_page_size == 50
    assert view._requested_page == 1
    assert view.table.page_size == 25

    view._executor.submit.assert_called_once_with(
        view.user_service.list_users,
        0,
        51,
    )


def test_change_page_size_applies_successful_result():
    view = make_view()

    view.change_page_size(50)

    future = Future()
    future.set_result([make_user(i) for i in range(1, 52)])

    view._future = future
    view._check_result()

    assert view.current_page == 1
    assert view.table.page_size == 50
    assert view._requested_page_size == 50

    view.table.page_size_selector.set.assert_called_with("50")

    args, kwargs = view.table.set_server_page.call_args

    assert len(args[0]) == 50
    assert kwargs["page"] == 1
    assert kwargs["has_next_page"] is True


def test_change_page_size_failure_restores_previous_size():
    view = make_view()

    view.change_page_size(50)

    future = Future()
    future.set_exception(RuntimeError("Backend unavailable"))

    view._future = future
    view._check_result()

    assert view.table.page_size == 25
    assert view._requested_page_size == 25
    assert view.current_page == 1

    view.table.set_server_page.assert_not_called()

    view.refresh()

    assert view._requested_page_size == 25

    assert view._executor.submit.call_args.args == (
        view.user_service.list_users,
        0,
        26,
    )

def test_lookahead_99_users():
    view = make_view()
    view.user_service.list_users.return_value = [make_user(i) for i in range(99)]
    result = view._fetch_users_with_lookahead(0, 100)
    assert len(result) == 99
    view.user_service.list_users.assert_called_once_with(0, 100)

def test_lookahead_100_users():
    view = make_view()
    view.user_service.list_users.side_effect = [[make_user(i) for i in range(100)], []]
    result = view._fetch_users_with_lookahead(0, 100)
    assert len(result) == 100
    assert view.user_service.list_users.call_count == 2
    assert view.user_service.list_users.call_args_list[1].args == (100, 1)

def test_lookahead_101_users():
    view = make_view()
    view.user_service.list_users.side_effect = [[make_user(i) for i in range(100)], [make_user(100)]]
    result = view._fetch_users_with_lookahead(0, 100)
    assert len(result) == 101
    assert view.user_service.list_users.call_count == 2
    assert view.user_service.list_users.call_args_list[1].args == (100, 1)

def test_lookahead_second_request_failure():
    view = make_view()
    view.user_service.list_users.side_effect = [
        [make_user(i) for i in range(100)],
        RuntimeError("Lookahead failed"),
    ]
    import pytest
    with pytest.raises(RuntimeError, match="Lookahead failed"):
        view._fetch_users_with_lookahead(0, 100)
    assert view.user_service.list_users.call_count == 2

def test_page_size_100_applies_100_rows():
    from concurrent.futures import Future
    view = make_view()
    view._requested_page_size = 100
    future = Future()
    future.set_result([make_user(i) for i in range(101)])
    view._future = future
    view._check_result()
    assert view.table.page_size == 100
    args, kwargs = view.table.set_server_page.call_args
    assert len(args[0]) == 100
    assert kwargs["has_next_page"] is True
