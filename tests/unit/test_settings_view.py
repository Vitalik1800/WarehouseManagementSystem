"""Stage 11.9.3: SettingsView behavior without a Tk display."""
import pytest

from frontend.app.views.settings_view import SettingsView, validate_appearance_mode


@pytest.mark.parametrize("mode", ["System", "Light", "Dark"])
def test_valid_modes(mode):
    assert validate_appearance_mode(mode) == mode


@pytest.mark.parametrize("mode", ["Blue", "", "dark", None])
def test_invalid_modes(mode):
    with pytest.raises(ValueError):
        validate_appearance_mode(mode)


class FakeSelector:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


def bare_view(callback=lambda mode: None):
    view = object.__new__(SettingsView)
    view.appearance_mode = "System"
    view.on_appearance_change = callback
    view.theme_selector = FakeSelector()
    return view


def test_change_calls_parent_once():
    calls = []
    view = bare_view(calls.append)
    view._on_theme_selected("Dark")
    assert calls == ["Dark"]
    assert view.appearance_mode == "Dark"


def test_failed_save_rolls_back_selection():
    def fail(_mode):
        raise OSError("disk full")
    view = bare_view(fail)
    with pytest.raises(OSError):
        view._on_theme_selected("Dark")
    assert view.appearance_mode == "System"
    assert view.theme_selector.value == "System"


def test_sync_does_not_invoke_callback():
    calls = []
    view = bare_view(calls.append)
    view.set_appearance_mode("Light")
    assert view.theme_selector.value == "Light"
    assert calls == []


def test_invalid_selection_does_not_call_callback():
    calls = []
    view = bare_view(calls.append)
    with pytest.raises(ValueError):
        view._on_theme_selected("Invalid")
    assert calls == []
