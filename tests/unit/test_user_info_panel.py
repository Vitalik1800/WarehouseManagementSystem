import customtkinter as ctk
import pytest

from frontend.app.components.user_info_panel import UserInfoPanel


@pytest.fixture
def user_panel():
    """Створює ізольовану панель користувача."""

    root = ctk.CTk()
    root.withdraw()

    user = {
        "id": 1,
        "username": "tester",
        "role": "admin"
    }

    panel = UserInfoPanel(root, user=user)
    panel.pack()

    root.update_idletasks()

    yield panel

    panel.destroy()
    root.destroy()


def test_user_panel_initial_username(user_panel):
    assert user_panel.username_label.cget("text") == "tester"


def test_user_panel_initial_role(user_panel):
    assert user_panel.role_label.cget("text") == "Адміністратор"


@pytest.mark.parametrize(
    "role,expected",
    [
        ("admin", "Адміністратор"),
        ("manager", "Менеджер"),
        ("storekeeper", "Комірник"),
        ("user", "Користувач"),
        ("ADMIN", "Адміністратор"),
        ("Manager", "Менеджер")
    ]
)
def test_user_panel_known_roles(user_panel, role, expected):
    user_panel.set_user({
        "username": "tester",
        "role": role
    })

    assert user_panel.role_label.cget("text") == expected


def test_user_panel_unknown_role(user_panel):
    user_panel.set_user({
        "username": "tester",
        "role": "auditor"
    })

    assert user_panel.role_label.cget("text") == "auditor"


def test_user_panel_missing_username(user_panel):
    user_panel.set_user({
        "role": "admin",
    })

    assert (
        user_panel.username_label.cget("text")
        == "Невідомий користувач"
    )


def test_user_panel_empty_username(user_panel):
    user_panel.set_user({
        "username": "   ",
        "role": "admin"
    })

    assert (
        user_panel.username_label.cget("text")
        == "Невідомий користувач"
    )


def test_user_panel_missing_role(user_panel):
    user_panel.set_user({
        "username": "tester",
    })

    assert (
        user_panel.role_label.cget("text")
        == "Невідома роль"
    )


def test_user_panel_empty_role(user_panel):
    user_panel.set_user({
        "username": "tester",
        "role": ""
    })

    assert (
        user_panel.role_label.cget("text")
        == "Невідома роль"
    )


def test_user_panel_non_string_values(user_panel):
    user_panel.set_user({
        "username": 123,
        "role": None
    })

    assert (
        user_panel.username_label.cget("text")
        == "Невідомий користувач"
    )
    assert (
        user_panel.role_label.cget("text")
        == "Невідома роль"
    )


def test_user_panel_trims_whitespace(user_panel):
    user_panel.set_user({
        "username": "  new_user  ",
        "role": "  manager  "
    })

    assert user_panel.username_label.cget("text") == "new_user"
    assert user_panel.role_label.cget("text") == "Менеджер"


def test_user_panel_updates_user(user_panel):
    user_panel.set_user({
        "id": 2,
        "username": "new_user",
        "role": "storekeeper"
    })

    assert user_panel.username_label.cget("text") == "new_user"
    assert user_panel.role_label.cget("text") == "Комірник"
    assert user_panel.user["id"] == 2


def test_user_panel_copies_user_dictionary(user_panel):
    user = {
        "username": "original",
        "role": "admin"
    }

    user_panel.set_user(user)

    user["username"] = "modified"

    assert user_panel.user["username"] == "original"
    assert user_panel.username_label.cget("text") == "original"


@pytest.mark.parametrize(
    "invalid_user",
    [
        None,
        "tester",
        [],
        123
    ]
)
def test_user_panel_rejects_invalid_user(
    user_panel,
    invalid_user
):
    with pytest.raises(
        TypeError,
        match="user must be a dictionary"
    ):
        user_panel.set_user(invalid_user)


def test_user_panel_invalid_update_preserves_state(user_panel):
    original_user = user_panel.user.copy()
    original_username = user_panel.username_label.cget("text")
    original_role = user_panel.role_label.cget("text")

    with pytest.raises(TypeError):
        user_panel.set_user(None)

    assert user_panel.user == original_user
    assert user_panel.username_label.cget("text") == original_username
    assert user_panel.role_label.cget("text") == original_role
