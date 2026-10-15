from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.app.services.user_activity_log_service import (
    UserActivityLogService,
)


@pytest.fixture
def service():
    db = MagicMock()
    audit_service = UserActivityLogService(db)
    audit_service.activities = MagicMock()
    return audit_service


def test_record_without_details(service):
    expected = object()
    service.activities.create.return_value = expected

    result = service.record(
        action="login",
        actor_id=7,
    )

    assert result is expected
    service.activities.create.assert_called_once_with(
        action="login",
        actor_id=7,
        entity_type=None,
        entity_id=None,
        details=None,
    )


def test_record_with_allowed_details(service):
    details = {
        "changed_fields": ["role"],
        "old_role": "worker",
        "new_role": "admin",
        "old_is_active": True,
        "new_is_active": False,
    }

    service.record(
        action="user_updated",
        actor_id=1,
        entity_type="user",
        entity_id=7,
        details=details,
    )

    kwargs = service.activities.create.call_args.kwargs

    assert kwargs["details"] == details
    assert kwargs["details"] is not details
    assert kwargs["entity_type"] == "user"
    assert kwargs["entity_id"] == 7


@pytest.mark.parametrize(
    "field",
    ["password", "access_token", "email"],
)
def test_record_rejects_unsupported_details(service, field):
    with pytest.raises(
        ValueError,
        match="Unsupported audit detail fields",
    ):
        service.record(
            action="user_updated",
            details={field: "sensitive"},
        )

    service.activities.create.assert_not_called()


def test_record_rejects_multiple_unknown_fields_sorted(service):
    with pytest.raises(ValueError) as exc_info:
        service.record(
            action="user_updated",
            details={"z_field": 1, "a_field": 2},
        )

    assert str(exc_info.value) == (
        "Unsupported audit detail fields: a_field, z_field"
    )
    service.activities.create.assert_not_called()


def test_admin_can_view_all_activities(service):
    expected = [object()]
    service.activities.get_all.return_value = expected

    result = service.get_all(
        current_user_id=1,
        current_user_role="admin",
    )

    assert result is expected
    assert service.activities.get_all.call_args.kwargs[
        "actor_id"
    ] is None


def test_admin_can_filter_by_actor(service):
    service.get_all(
        current_user_id=1,
        current_user_role="admin",
        actor_id=12,
    )

    assert service.activities.get_all.call_args.kwargs[
        "actor_id"
    ] == 12


def test_worker_sees_only_own_activities(service):
    service.get_all(
        current_user_id=5,
        current_user_role="worker",
    )

    assert service.activities.get_all.call_args.kwargs[
        "actor_id"
    ] == 5


def test_worker_can_explicitly_filter_by_own_id(service):
    service.get_all(
        current_user_id=5,
        current_user_role="worker",
        actor_id=5,
    )

    assert service.activities.get_all.call_args.kwargs[
        "actor_id"
    ] == 5


def test_worker_cannot_view_another_users_activities(service):
    with pytest.raises(
        PermissionError,
        match="Cannot view another user's activity",
    ):
        service.get_all(
            current_user_id=5,
            current_user_role="worker",
            actor_id=6,
        )

    service.activities.get_all.assert_not_called()


@pytest.mark.parametrize(
    "role",
    ["guest", "manager", "", "ADMIN"],
)
def test_unsupported_roles_are_rejected(service, role):
    with pytest.raises(
        PermissionError,
        match="Unsupported user role",
    ):
        service.get_all(
            current_user_id=1,
            current_user_role=role,
        )

    service.activities.get_all.assert_not_called()


def test_get_all_forwards_filters_and_sorting(service):
    date_from = datetime(2026, 1, 1)
    date_to = datetime(2026, 12, 31)

    service.get_all(
        current_user_id=1,
        current_user_role="admin",
        offset=20,
        limit=10,
        actor_id=7,
        action="login",
        entity_type="user",
        entity_id=8,
        date_from=date_from,
        date_to=date_to,
        sort_by="oldest",
    )

    service.activities.get_all.assert_called_once_with(
        offset=20,
        limit=10,
        actor_id=7,
        action="login",
        entity_type="user",
        entity_id=8,
        date_from=date_from,
        date_to=date_to,
        sort_by="oldest",
    )
