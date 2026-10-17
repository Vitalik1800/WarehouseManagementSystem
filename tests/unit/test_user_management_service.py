from unittest.mock import Mock

import pytest

from frontend.app.services.user_management_service import (
    UserManagementError,
    UserManagementService,
)


@pytest.fixture
def api_client():
    client = Mock()
    client.is_authenticated = True
    client.get.return_value = []
    return client


@pytest.fixture
def service(api_client):
    return UserManagementService(api_client)


@pytest.fixture
def valid_user():
    return {
        "id": 1,
        "name": "Test Worker",
        "username": "test_worker",
        "role": "worker",
        "is_active": True,
    }


def test_service_stores_api_client(api_client):
    service = UserManagementService(api_client)
    assert service.api_client is api_client


def test_empty_user_list(service, api_client):
    assert service.list_users() == []
    api_client.get.assert_called_once_with(
        "/users",
        params={"offset": 0, "limit": 50},
    )


def test_valid_user_list(service, api_client, valid_user):
    api_client.get.return_value = [valid_user]

    assert service.list_users() == [valid_user]


def test_custom_pagination(service, api_client):
    service.list_users(offset=20, limit=10)

    api_client.get.assert_called_once_with(
        "/users",
        params={"offset": 20, "limit": 10},
    )


@pytest.mark.parametrize("offset", [-1, 1.5, True, "0", None])
def test_invalid_offset(service, api_client, offset):
    with pytest.raises(ValueError):
        service.list_users(offset=offset)

    api_client.get.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 101, 1.5, True, "10", None])
def test_invalid_limit(service, api_client, limit):
    with pytest.raises(ValueError):
        service.list_users(limit=limit)

    api_client.get.assert_not_called()


def test_unauthenticated_request(service, api_client):
    api_client.is_authenticated = False

    with pytest.raises(UserManagementError, match="авторизація"):
        service.list_users()

    api_client.get.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [None, {}, "invalid", 123, True],
)
def test_invalid_list_response(service, api_client, response):
    api_client.get.return_value = response

    with pytest.raises(UserManagementError):
        service.list_users()


def test_response_exceeds_limit(service, api_client, valid_user):
    api_client.get.return_value = [valid_user, valid_user]

    with pytest.raises(UserManagementError, match="більше"):
        service.list_users(limit=1)


def test_duplicate_user_ids(service, api_client, valid_user):
    second_user = {
        **valid_user,
        "username": "another_worker",
    }

    api_client.get.return_value = [valid_user, second_user]

    with pytest.raises(UserManagementError, match="повторювані"):
        service.list_users()


@pytest.mark.parametrize(
    "invalid_id",
    [None, 0, -1, True, "1", 1.5],
)
def test_invalid_user_id(service, api_client, valid_user, invalid_id):
    api_client.get.return_value = [
        {**valid_user, "id": invalid_id}
    ]

    with pytest.raises(UserManagementError):
        service.list_users()


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", ""),
        ("name", "   "),
        ("name", None),
        ("username", ""),
        ("username", "   "),
        ("username", None),
        ("role", "manager"),
        ("role", None),
        ("is_active", None),
        ("is_active", 1),
        ("is_active", "true"),
    ],
)
def test_invalid_user_fields(
    service, api_client, valid_user, field, value
):
    api_client.get.return_value = [
        {**valid_user, field: value}
    ]

    with pytest.raises(UserManagementError):
        service.list_users()


def test_non_dict_user(service, api_client):
    api_client.get.return_value = ["invalid"]

    with pytest.raises(UserManagementError):
        service.list_users()


def test_admin_user(service, api_client, valid_user):
    admin = {
        **valid_user,
        "role": "admin",
        "is_active": False,
    }

    api_client.get.return_value = [admin]

    assert service.list_users() == [admin]


def test_extra_fields_are_excluded(
    service, api_client, valid_user
):
    user = {
        **valid_user,
        "password_hash": "should_not_be_exposed",
    }

    api_client.get.return_value = [user]

    result = service.list_users()

    assert result == [valid_user]
    assert "password_hash" not in result[0]


def test_api_error_propagates(service, api_client):
    api_client.get.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        service.list_users()


def test_get_user_success(service, api_client, valid_user):
    api_client.get.return_value = valid_user

    result = service.get_user(1)

    assert result == valid_user
    api_client.get.assert_called_once_with("/users/1")


@pytest.mark.parametrize("user_id", [0, -1, True, 1.5, "1", None])
def test_get_user_invalid_id(service, api_client, user_id):
    with pytest.raises(ValueError):
        service.get_user(user_id)

    api_client.get.assert_not_called()


def test_get_user_unauthenticated(service, api_client):
    api_client.is_authenticated = False

    with pytest.raises(UserManagementError, match="авторизація"):
        service.get_user(1)

    api_client.get.assert_not_called()


@pytest.mark.parametrize("response", [None, [], "invalid", 123])
def test_get_user_invalid_response(service, api_client, response):
    api_client.get.return_value = response

    with pytest.raises(UserManagementError):
        service.get_user(1)


def test_get_user_wrong_id(service, api_client, valid_user):
    api_client.get.return_value = {
        **valid_user,
        "id": 2,
    }

    with pytest.raises(UserManagementError, match="іншого користувача"):
        service.get_user(1)


def test_get_user_excludes_extra_fields(
    service, api_client, valid_user
):
    api_client.get.return_value = {
        **valid_user,
        "password_hash": "secret",
    }

    result = service.get_user(1)

    assert result == valid_user
    assert "password_hash" not in result


def test_get_user_api_error_propagates(service, api_client):
    api_client.get.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        service.get_user(1)


def test_update_user_name_only(service, api_client, valid_user):
    updated = {**valid_user, "name": "Updated Worker"}
    api_client.patch.return_value = updated

    result = service.update_user(1, name="Updated Worker")

    assert result == updated
    api_client.patch.assert_called_once_with(
        "/users/1",
        json={"name": "Updated Worker"},
    )


def test_update_user_username_only(service, api_client, valid_user):
    updated = {**valid_user, "username": "updated_worker"}
    api_client.patch.return_value = updated

    result = service.update_user(1, username="updated_worker")

    assert result == updated
    api_client.patch.assert_called_once_with(
        "/users/1",
        json={"username": "updated_worker"},
    )


def test_update_user_both_fields(service, api_client, valid_user):
    updated = {
        **valid_user,
        "name": "Updated Worker",
        "username": "updated_worker",
    }
    api_client.patch.return_value = updated

    result = service.update_user(
        1,
        name="Updated Worker",
        username="updated_worker",
    )

    assert result == updated
    api_client.patch.assert_called_once_with(
        "/users/1",
        json={
            "name": "Updated Worker",
            "username": "updated_worker",
        },
    )


def test_update_user_strips_whitespace(service, api_client, valid_user):
    api_client.patch.return_value = valid_user

    service.update_user(
        1,
        name="  Test Worker  ",
        username="  test_worker  ",
    )

    api_client.patch.assert_called_once_with(
        "/users/1",
        json={
            "name": "Test Worker",
            "username": "test_worker",
        },
    )


@pytest.mark.parametrize("user_id", [0, -1, True, 1.5, "1", None])
def test_update_user_invalid_id(service, api_client, user_id):
    with pytest.raises(ValueError):
        service.update_user(user_id, name="Test Worker")

    api_client.patch.assert_not_called()


def test_update_user_no_fields(service, api_client):
    with pytest.raises(ValueError, match="хоча б одне поле"):
        service.update_user(1)

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "name",
    ["", " ", "A", "A" * 151, 123, True, [], {}],
)
def test_update_user_invalid_name(service, api_client, name):
    with pytest.raises(ValueError):
        service.update_user(1, name=name)

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "username",
    [
        "",
        " ",
        "ab",
        "a" * 51,
        "user-name",
        "user name",
        "user.name",
        "користувач",
        123,
        True,
        [],
        {},
    ],
)
def test_update_user_invalid_username(
    service, api_client, username
):
    with pytest.raises(ValueError):
        service.update_user(1, username=username)

    api_client.patch.assert_not_called()


def test_update_user_unauthenticated(service, api_client):
    api_client.is_authenticated = False

    with pytest.raises(UserManagementError, match="авторизація"):
        service.update_user(1, name="Updated Worker")

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [None, [], "invalid", 123, {}],
)
def test_update_user_invalid_response(
    service, api_client, response
):
    api_client.patch.return_value = response

    with pytest.raises(UserManagementError):
        service.update_user(1, name="Updated Worker")


def test_update_user_wrong_response_id(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "id": 2,
    }

    with pytest.raises(UserManagementError, match="іншого користувача"):
        service.update_user(1, name="Updated Worker")


def test_update_user_excludes_extra_fields(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "password_hash": "secret",
    }

    result = service.update_user(1, name="Test Worker")

    assert result == valid_user
    assert "password_hash" not in result


def test_update_user_api_error_propagates(service, api_client):
    api_client.patch.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        service.update_user(1, name="Updated Worker")


def test_change_role_worker_to_admin(
    service, api_client, valid_user
):
    updated = {**valid_user, "role": "admin"}
    api_client.patch.return_value = updated

    result = service.change_user_role(1, "admin")

    assert result == updated
    api_client.patch.assert_called_once_with(
        "/users/1/role",
        json={"role": "admin"},
    )


def test_change_role_admin_to_worker(
    service, api_client, valid_user
):
    updated = {**valid_user, "role": "worker"}
    api_client.patch.return_value = updated

    result = service.change_user_role(1, "worker")

    assert result == updated
    api_client.patch.assert_called_once_with(
        "/users/1/role",
        json={"role": "worker"},
    )


@pytest.mark.parametrize("user_id", [0, -1, True, 1.5, "1", None])
def test_change_role_invalid_id(
    service, api_client, user_id
):
    with pytest.raises(ValueError):
        service.change_user_role(user_id, "admin")

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "role",
    ["", "manager", "ADMIN", "Worker", " admin ", None, 123, True, [], {}],
)
def test_change_role_invalid_role(
    service, api_client, role
):
    with pytest.raises(ValueError):
        service.change_user_role(1, role)

    api_client.patch.assert_not_called()


def test_change_role_unauthenticated(service, api_client):
    api_client.is_authenticated = False

    with pytest.raises(UserManagementError, match="авторизація"):
        service.change_user_role(1, "admin")

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [None, [], "invalid", 123, {}],
)
def test_change_role_invalid_response(
    service, api_client, response
):
    api_client.patch.return_value = response

    with pytest.raises(UserManagementError):
        service.change_user_role(1, "admin")


def test_change_role_wrong_user_id(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "id": 2,
        "role": "admin",
    }

    with pytest.raises(
        UserManagementError,
        match="іншого користувача",
    ):
        service.change_user_role(1, "admin")


def test_change_role_wrong_returned_role(
    service, api_client, valid_user
):
    api_client.patch.return_value = valid_user

    with pytest.raises(
        UserManagementError,
        match="не відповідає запиту",
    ):
        service.change_user_role(1, "admin")


def test_change_role_excludes_extra_fields(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "role": "admin",
        "password_hash": "secret",
    }

    result = service.change_user_role(1, "admin")

    assert result["role"] == "admin"
    assert "password_hash" not in result


def test_change_role_api_error_propagates(
    service, api_client
):
    api_client.patch.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        service.change_user_role(1, "admin")


def test_activate_user_success(service, api_client, valid_user):
    api_client.patch.return_value = valid_user

    result = service.activate_user(1)

    assert result == valid_user
    assert result["is_active"] is True
    api_client.patch.assert_called_once_with(
        "/users/1/activate"
    )


def test_activate_user_from_inactive(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "is_active": True,
    }

    result = service.activate_user(1)

    assert result["is_active"] is True


@pytest.mark.parametrize(
    "user_id",
    [0, -1, True, 1.5, "1", None],
)
def test_activate_user_invalid_id(
    service, api_client, user_id
):
    with pytest.raises(ValueError):
        service.activate_user(user_id)

    api_client.patch.assert_not_called()


def test_activate_user_unauthenticated(service, api_client):
    api_client.is_authenticated = False

    with pytest.raises(
        UserManagementError,
        match="авторизація",
    ):
        service.activate_user(1)

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [None, [], "invalid", 123, {}],
)
def test_activate_user_invalid_response(
    service, api_client, response
):
    api_client.patch.return_value = response

    with pytest.raises(UserManagementError):
        service.activate_user(1)


def test_activate_user_wrong_id(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "id": 2,
    }

    with pytest.raises(
        UserManagementError,
        match="іншого користувача",
    ):
        service.activate_user(1)


def test_activate_user_not_confirmed(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "is_active": False,
    }

    with pytest.raises(
        UserManagementError,
        match="не підтвердив активацію",
    ):
        service.activate_user(1)


def test_activate_user_excludes_extra_fields(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "password_hash": "secret",
    }

    result = service.activate_user(1)

    assert result == valid_user
    assert "password_hash" not in result


def test_activate_user_api_error_propagates(
    service, api_client
):
    api_client.patch.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        service.activate_user(1)


def test_deactivate_user_success(
    service, api_client, valid_user
):
    updated = {
        **valid_user,
        "is_active": False,
    }
    api_client.patch.return_value = updated

    result = service.deactivate_user(1)

    assert result == updated
    assert result["is_active"] is False
    api_client.patch.assert_called_once_with(
        "/users/1/deactivate"
    )


@pytest.mark.parametrize(
    "user_id",
    [0, -1, True, 1.5, "1", None],
)
def test_deactivate_user_invalid_id(
    service, api_client, user_id
):
    with pytest.raises(ValueError):
        service.deactivate_user(user_id)

    api_client.patch.assert_not_called()


def test_deactivate_user_unauthenticated(
    service, api_client
):
    api_client.is_authenticated = False

    with pytest.raises(
        UserManagementError,
        match="авторизація",
    ):
        service.deactivate_user(1)

    api_client.patch.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [None, [], "invalid", 123, {}],
)
def test_deactivate_user_invalid_response(
    service, api_client, response
):
    api_client.patch.return_value = response

    with pytest.raises(UserManagementError):
        service.deactivate_user(1)


def test_deactivate_user_wrong_id(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "id": 2,
        "is_active": False,
    }

    with pytest.raises(
        UserManagementError,
        match="іншого користувача",
    ):
        service.deactivate_user(1)


def test_deactivate_user_not_confirmed(
    service, api_client, valid_user
):
    api_client.patch.return_value = valid_user

    with pytest.raises(
        UserManagementError,
        match="не підтвердив деактивацію",
    ):
        service.deactivate_user(1)


def test_deactivate_user_excludes_extra_fields(
    service, api_client, valid_user
):
    api_client.patch.return_value = {
        **valid_user,
        "is_active": False,
        "password_hash": "secret",
    }

    result = service.deactivate_user(1)

    assert result["is_active"] is False
    assert "password_hash" not in result


def test_deactivate_user_api_error_propagates(
    service, api_client
):
    api_client.patch.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        service.deactivate_user(1)


def test_deactivate_user_conflict_propagates(
    service, api_client
):
    api_client.patch.side_effect = RuntimeError(
        "409 Conflict"
    )

    with pytest.raises(RuntimeError, match="409 Conflict"):
        service.deactivate_user(1)
