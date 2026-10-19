from datetime import datetime
import pytest
from frontend.app.views.activity_log_view import parse_activity_filters, format_activity_details, ActivityLogView


def test_empty_filters():
    assert parse_activity_filters({}, "worker") == {"sort_by": "newest"}


def test_admin_filters():
    value = parse_activity_filters({"actor_id": "12", "entity_id": "3", "action": " login ", "entity_type": "user", "date_from": "2026-10-01", "date_to": "2026-10-18 12:00", "sort_by": "oldest"}, "admin")
    assert value["actor_id"] == 12
    assert value["entity_id"] == 3
    assert value["action"] == "login"
    assert value["date_from"] == datetime(2026, 10, 1)
    assert value["sort_by"] == "oldest"


@pytest.mark.parametrize("field,value", [("actor_id", "0"), ("entity_id", "-1"), ("actor_id", "1.5"), ("action", "a" * 101), ("entity_type", "a" * 51), ("date_from", "no-date"), ("date_from", "2026-10-18T10:00+03:00"), ("sort_by", "invalid")])
def test_invalid_filters(field, value):
    with pytest.raises(ValueError):
        parse_activity_filters({field: value}, "admin")


def test_worker_actor_filter_rejected():
    with pytest.raises(ValueError):
        parse_activity_filters({"actor_id": "2"}, "worker")


def test_invalid_role():
    with pytest.raises(ValueError):
        parse_activity_filters({}, "guest")


def test_reverse_dates():
    with pytest.raises(ValueError):
        parse_activity_filters({"date_from": "2026-10-19", "date_to": "2026-10-18"}, "admin")


def test_details_unicode():
    assert "Зміна" in format_activity_details({"action": "Зміна"})
    assert "Немає" in format_activity_details(None)


def test_view_is_read_only():
    assert not hasattr(ActivityLogView, "delete_activity")
    assert not hasattr(ActivityLogView, "create_activity")


def test_date_to_includes_entire_calendar_day():
    filters = parse_activity_filters({"date_from": "2026-10-19", "date_to": "2026-10-19"}, "admin")
    assert filters["date_from"] == datetime(2026, 10, 19)
    assert filters["date_to"] == datetime(2026, 10, 19, 23, 59, 59, 999999)


def test_date_to_preserves_explicit_time():
    filters = parse_activity_filters({"date_to": "2026-10-19 12:00"}, "admin")
    assert filters["date_to"] == datetime(2026, 10, 19, 12, 0)


def test_date_to_does_not_include_next_day():
    filters = parse_activity_filters({"date_to": "2026-10-19"}, "admin")
    assert filters["date_to"] < datetime(2026, 10, 20)
