from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.user_activity_log import UserActivityLog


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def create_user(db_session, *, role="worker"):
    user = User(
        name="Activity API Test User",
        username=f"activity_api_{uuid4().hex[:16]}",
        password_hash="test_hash",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def auth_headers(user):
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


def create_activity(
    db_session,
    *,
    actor_id,
    action="auth.login",
    entity_type="user",
    entity_id=None,
    created_at=None,
):
    activity = UserActivityLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=None,
    )

    if created_at is not None:
        activity.created_at = created_at

    db_session.add(activity)
    db_session.flush()
    return activity


def test_admin_can_view_all_activities(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    first = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
    )
    second = create_activity(
        db_session,
        actor_id=worker.id,
        entity_id=worker.id,
    )

    response = client.get(
        "/user-activity-logs",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    returned_ids = {item["id"] for item in response.json()}
    assert first.id in returned_ids
    assert second.id in returned_ids


def test_worker_sees_only_own_activities(client, db_session):
    worker = create_user(db_session)
    other_worker = create_user(db_session)

    own_activity = create_activity(
        db_session,
        actor_id=worker.id,
        entity_id=worker.id,
    )
    other_activity = create_activity(
        db_session,
        actor_id=other_worker.id,
        entity_id=other_worker.id,
    )

    response = client.get(
        "/user-activity-logs",
        headers=auth_headers(worker),
    )

    assert response.status_code == 200, response.text

    returned_ids = {item["id"] for item in response.json()}
    assert own_activity.id in returned_ids
    assert other_activity.id not in returned_ids
    assert all(
        item["actor_id"] == worker.id
        for item in response.json()
    )


def test_worker_cannot_filter_another_actor(client, db_session):
    worker = create_user(db_session)
    other_worker = create_user(db_session)

    response = client.get(
        "/user-activity-logs",
        params={"actor_id": other_worker.id},
        headers=auth_headers(worker),
    )

    assert response.status_code == 403


def test_worker_can_filter_own_actor(client, db_session):
    worker = create_user(db_session)

    activity = create_activity(
        db_session,
        actor_id=worker.id,
        entity_id=worker.id,
    )

    response = client.get(
        "/user-activity-logs",
        params={"actor_id": worker.id},
        headers=auth_headers(worker),
    )

    assert response.status_code == 200, response.text
    assert activity.id in {
        item["id"] for item in response.json()
    }


def test_admin_can_filter_by_action_and_actor(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    expected = create_activity(
        db_session,
        actor_id=worker.id,
        action="auth.login",
        entity_id=worker.id,
    )
    excluded = create_activity(
        db_session,
        actor_id=worker.id,
        action="auth.logout",
        entity_id=worker.id,
    )

    response = client.get(
        "/user-activity-logs",
        params={
            "actor_id": worker.id,
            "action": "auth.login",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    returned_ids = {item["id"] for item in response.json()}
    assert expected.id in returned_ids
    assert excluded.id not in returned_ids


def test_admin_can_filter_by_entity(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)
    other_worker = create_user(db_session)

    expected = create_activity(
        db_session,
        actor_id=admin.id,
        action="user.updated",
        entity_id=worker.id,
    )
    excluded = create_activity(
        db_session,
        actor_id=admin.id,
        action="user.updated",
        entity_id=other_worker.id,
    )

    response = client.get(
        "/user-activity-logs",
        params={
            "entity_type": "user",
            "entity_id": worker.id,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    returned_ids = {item["id"] for item in response.json()}
    assert expected.id in returned_ids
    assert excluded.id not in returned_ids


def test_date_range_filter(client, db_session):
    admin = create_user(db_session, role="admin")

    base_time = datetime(2026, 10, 10, 12, 0, 0)

    older = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
        created_at=base_time - timedelta(days=2),
    )
    expected = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
        created_at=base_time,
    )
    newer = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
        created_at=base_time + timedelta(days=2),
    )

    response = client.get(
        "/user-activity-logs",
        params={
            "actor_id": admin.id,
            "date_from": "2026-10-10T00:00:00",
            "date_to": "2026-10-10T23:59:59",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    returned_ids = {item["id"] for item in response.json()}
    assert expected.id in returned_ids
    assert older.id not in returned_ids
    assert newer.id not in returned_ids


@pytest.mark.parametrize("sort_by", ["newest", "oldest"])
def test_sorting(client, db_session, sort_by):
    admin = create_user(db_session, role="admin")

    base_time = datetime(2026, 10, 10, 12, 0, 0)

    first = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
        created_at=base_time,
    )
    second = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
        created_at=base_time + timedelta(hours=1),
    )

    response = client.get(
        "/user-activity-logs",
        params={
            "actor_id": admin.id,
            "sort_by": sort_by,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    returned_ids = [
        item["id"] for item in response.json()
        if item["id"] in {first.id, second.id}
    ]

    expected = (
        [second.id, first.id]
        if sort_by == "newest"
        else [first.id, second.id]
    )

    assert returned_ids == expected


def test_pagination(client, db_session):
    admin = create_user(db_session, role="admin")

    base_time = datetime(2026, 10, 10, 12, 0, 0)

    for index in range(3):
        create_activity(
            db_session,
            actor_id=admin.id,
            entity_id=admin.id,
            created_at=base_time + timedelta(minutes=index),
        )

    response = client.get(
        "/user-activity-logs",
        params={
            "actor_id": admin.id,
            "offset": 1,
            "limit": 1,
            "sort_by": "oldest",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
        {"actor_id": 0},
        {"entity_id": 0},
        {"action": ""},
        {"entity_type": ""},
        {"sort_by": "invalid"},
        {"date_from": "invalid"},
        {"date_from": "2026-10-10T12:00:00+03:00"},
        {"date_to": "2026-10-10T12:00:00+03:00"},
        {
            "date_from": "2026-10-11T00:00:00",
            "date_to": "2026-10-10T00:00:00",
        },
    ],
)
def test_invalid_query_parameters_return_422(
    client,
    db_session,
    params,
):
    admin = create_user(db_session, role="admin")

    response = client.get(
        "/user-activity-logs",
        params=params,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422, response.text


def test_missing_token_returns_401(client):
    response = client.get("/user-activity-logs")
    assert response.status_code == 401


def test_response_contains_expected_fields(client, db_session):
    admin = create_user(db_session, role="admin")

    activity = create_activity(
        db_session,
        actor_id=admin.id,
        entity_id=admin.id,
    )

    response = client.get(
        "/user-activity-logs",
        params={"actor_id": admin.id},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text

    item = next(
        entry for entry in response.json()
        if entry["id"] == activity.id
    )

    assert set(item) == {
        "id",
        "actor_id",
        "action",
        "entity_type",
        "entity_id",
        "details",
        "created_at",
    }


@pytest.mark.parametrize("sort_by", ["newest", "oldest"])
def test_stable_sorting_and_pagination_with_same_timestamp(
    client,
    db_session,
    sort_by
):
    admin = create_user(db_session, role="admin")

    same_time = datetime(2026, 10, 10, 12, 0, 0)

    activities = [
        create_activity(
            db_session,
            actor_id=admin.id,
            entity_id=admin.id,
            created_at=same_time,
        )
        for _ in range(5)
    ]

    created_ids = [activity.id for activity in activities]

    expected_ids = (
        list(reversed(created_ids))
        if sort_by == "newest"
        else created_ids
    )

    returned_ids = []

    for offset in (0, 2, 4):
        response = client.get(
            "/user-activity-logs",
            params={
                "actor_id": admin.id,
                "sort_by": sort_by,
                "offset": offset,
                "limit": 2,
            },
            headers=auth_headers(admin),
        )

        assert response.status_code == 200, response.text

        page_ids = [
            item["id"]
            for item in response.json()
        ]

        assert page_ids == expected_ids[offset:offset + 2]

        returned_ids.extend(page_ids)

    assert returned_ids == expected_ids
    assert len(returned_ids) == len(set(returned_ids))
