from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from frontend.app.services.user_activity_log_service import (
    UserActivityLogClientService,
    UserActivityLogClientServiceError,
)


def client(authenticated=True):
    api = Mock()
    api.is_authenticated = authenticated
    return UserActivityLogClientService(api), api


def event(event_id=1):
    return {"id": event_id, "actor_id": 2, "action": "login", "entity_type": "user", "entity_id": 2, "details": {"changed_fields": []}, "created_at": "2026-10-18T12:30:00"}


def test_list_default_parameters():
    service, api = client()
    api.get.return_value = [event()]
    assert service.list_activity_logs() == [event()]
    api.get.assert_called_once_with("/user-activity-logs", params={"offset": 0, "limit": 50, "sort_by": "newest"})


def test_all_filters_are_forwarded():
    service, api = client()
    api.get.return_value = []
    service.list_activity_logs(offset=25, limit=25, actor_id=2, action=" login ", entity_type=" user ", entity_id=4, date_from=datetime(2026, 10, 1), date_to=datetime(2026, 10, 18), sort_by="oldest")
    assert api.get.call_args.kwargs["params"] == {"offset": 25, "limit": 25, "sort_by": "oldest", "actor_id": 2, "action": "login", "entity_type": "user", "entity_id": 4, "date_from": "2026-10-01T00:00:00", "date_to": "2026-10-18T00:00:00"}


@pytest.mark.parametrize("kwargs", [
    {"offset": -1}, {"offset": True}, {"limit": 0}, {"limit": 101},
    {"limit": True}, {"actor_id": 0}, {"actor_id": True},
    {"entity_id": -2}, {"action": " "}, {"entity_type": "x" * 51},
    {"sort_by": "random"}, {"date_from": datetime.now(timezone.utc)},
    {"date_from": datetime(2026, 10, 18), "date_to": datetime(2026, 10, 1)},
])
def test_reject_invalid_filters_before_request(kwargs):
    service, api = client()
    with pytest.raises(ValueError):
        service.list_activity_logs(**kwargs)
    api.get.assert_not_called()


def test_authentication_required():
    service, api = client(False)
    with pytest.raises(UserActivityLogClientServiceError, match="Authentication"):
        service.list_activity_logs()
    api.get.assert_not_called()


@pytest.mark.parametrize("response", [None, {}, [event(), event()], [event(), "bad"], [event(1), event(1)]])
def test_reject_malformed_api_response(response):
    service, api = client()
    api.get.return_value = response
    with pytest.raises(UserActivityLogClientServiceError):
        service.list_activity_logs()


@pytest.mark.parametrize("change", [
    {"id": True}, {"actor_id": 0}, {"action": ""},
    {"entity_type": 4}, {"entity_id": False},
    {"details": []}, {"created_at": "not-a-date"},
    {"created_at": "2026-10-18T12:30:00Z"},
])
def test_reject_invalid_record_fields(change):
    service, api = client()
    api.get.return_value = [{**event(), **change}]
    with pytest.raises(UserActivityLogClientServiceError):
        service.list_activity_logs()


def test_nullable_fields_accepted():
    service, api = client()
    row = {**event(), "actor_id": None, "entity_type": None, "entity_id": None, "details": None}
    api.get.return_value = [row]
    assert service.list_activity_logs() == [row]
