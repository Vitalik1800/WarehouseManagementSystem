"""HTTP integration checks; db_session fixture rolls back warehouse_test_db writes."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.security import decode_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user_session import UserSession
from tests.helpers.users import create_test_user


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


@pytest.fixture
def logged_in(client, db_session):
    username = f'api_refresh_{uuid4().hex[:12]}'
    password = 'SecurePassword123!'
    user = create_test_user(db_session, name='Refresh API test',
                            username=username, password=password)
    response = client.post('/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200, response.text
    return user, response.json()


def test_login_returns_refresh_and_persists_hash_only(logged_in, db_session):
    user, tokens = logged_in
    assert tokens['token_type'] == 'bearer'
    assert isinstance(tokens['refresh_token'], str) and len(tokens['refresh_token']) >= 40
    assert decode_access_token(tokens['access_token'])['sub'] == str(user.id)
    digest = sha256(tokens['refresh_token'].encode()).hexdigest()
    saved = db_session.scalar(select(UserSession).where(UserSession.refresh_token_hash == digest))
    assert saved is not None and saved.user_id == user.id
    assert saved.refresh_token_hash != tokens['refresh_token']


def test_refresh_rotates_and_new_access_works(client, logged_in):
    user, initial = logged_in
    response = client.post('/auth/refresh', json={'refresh_token': initial['refresh_token']})
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated['refresh_token'] != initial['refresh_token']
    assert updated['access_token']
    assert decode_access_token(updated['access_token'])['sub'] == str(user.id)
    me = client.get('/auth/me', headers={'Authorization': f"Bearer {updated['access_token']}"})
    assert me.status_code == 200
    assert me.json()['id'] == user.id


def test_old_refresh_token_replay_rejected(client, logged_in):
    _, initial = logged_in
    first = client.post('/auth/refresh', json={'refresh_token': initial['refresh_token']})
    assert first.status_code == 200
    replay = client.post('/auth/refresh', json={'refresh_token': initial['refresh_token']})
    assert replay.status_code == 401
    next_response = client.post('/auth/refresh', json={'refresh_token': first.json()['refresh_token']})
    assert next_response.status_code == 200


def test_logout_revokes_both_tokens(client, logged_in):
    _, tokens = logged_in
    response = client.post('/auth/logout',
        headers={'Authorization': f"Bearer {tokens['access_token']}"},
        json={'refresh_token': tokens['refresh_token']})
    assert response.status_code == 204, response.text
    assert client.get('/auth/me', headers={'Authorization': f"Bearer {tokens['access_token']}"}).status_code == 401
    assert client.post('/auth/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 401


def test_logout_rejects_other_users_refresh_token(client, db_session, logged_in):
    first_user, first = logged_in
    username = f'api_other_{uuid4().hex[:12]}'
    create_test_user(db_session, name='Other user', username=username, password='SecurePassword123!')
    other = client.post('/auth/login', json={'username': username, 'password': 'SecurePassword123!'})
    assert other.status_code == 200
    other_refresh = other.json()['refresh_token']
    attempt = client.post('/auth/logout',
        headers={'Authorization': f"Bearer {first['access_token']}"},
        json={'refresh_token': other_refresh})
    assert attempt.status_code == 401
    assert client.post('/auth/refresh', json={'refresh_token': other_refresh}).status_code == 200
    assert client.get('/auth/me', headers={'Authorization': f"Bearer {first['access_token']}"}).status_code == 200


def test_expired_refresh_token_rejected(client, db_session, logged_in):
    _, tokens = logged_in
    digest = sha256(tokens['refresh_token'].encode()).hexdigest()
    session = db_session.scalar(select(UserSession).where(UserSession.refresh_token_hash == digest))
    assert session is not None
    session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.flush()
    assert client.post('/auth/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 401


@pytest.mark.parametrize('payload,expected', [
    ({}, 422),
    ({'refresh_token': ''}, 422),
    ({'refresh_token': 'invalid-token'}, 401),
    ({'refresh_token': 'x' * 513}, 422),
])
def test_invalid_refresh_requests(client, payload, expected):
    response = client.post('/auth/refresh', json=payload)
    assert response.status_code == expected, response.text
