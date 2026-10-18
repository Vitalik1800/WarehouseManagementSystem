import json
import pytest
from frontend.app.core.appearance_settings_store import AppearanceSettingsStore


@pytest.mark.parametrize("mode", ["System", "Light", "Dark"])
def test_round_trip(tmp_path, mode):
    store = AppearanceSettingsStore(tmp_path / "preferences" / "settings.json")
    store.save(mode)
    assert store.load() == mode
    assert json.loads(store.path.read_text(encoding="utf-8")) == {"appearance_mode": mode}


def test_missing_file_falls_back(tmp_path):
    assert AppearanceSettingsStore(tmp_path / "none.json").load("Dark") == "Dark"


@pytest.mark.parametrize("contents", ["not-json", "[]", '{"appearance_mode":"invalid"}', '{"appearance_mode":42}'])
def test_bad_file_falls_back(tmp_path, contents):
    path = tmp_path / "settings.json"
    path.write_text(contents, encoding="utf-8")
    assert AppearanceSettingsStore(path).load("Light") == "Light"


def test_invalid_mode_cannot_overwrite(tmp_path):
    store = AppearanceSettingsStore(tmp_path / "settings.json")
    store.save("Dark")
    with pytest.raises(ValueError):
        store.save("Blue")
    assert store.load() == "Dark"


def test_invalid_default(tmp_path):
    with pytest.raises(ValueError):
        AppearanceSettingsStore(tmp_path / "settings.json").load("Blue")


def test_appdata_path(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = AppearanceSettingsStore()
    assert store.path == tmp_path / "WarehouseManagementSystem" / "settings.json"


def test_missing_appdata(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    with pytest.raises(RuntimeError):
        AppearanceSettingsStore()
