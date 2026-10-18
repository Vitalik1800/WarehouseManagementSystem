"""Local non-secret appearance preferences."""
import json
import os
from pathlib import Path
import tempfile

APPEARANCE_MODES = ("System", "Light", "Dark")


class AppearanceSettingsStore:
    def __init__(self, path: Path | None = None):
        if path is None:
            appdata = os.environ.get("APPDATA")
            if not appdata:
                raise RuntimeError("APPDATA environment variable is unavailable")
            path = Path(appdata) / "WarehouseManagementSystem" / "settings.json"
        self.path = Path(path)

    def load(self, default: str = "System") -> str:
        if default not in APPEARANCE_MODES:
            raise ValueError("Invalid default appearance mode")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            return default
        if not isinstance(data, dict):
            return default
        mode = data.get("appearance_mode")
        return mode if isinstance(mode, str) and mode in APPEARANCE_MODES else default

    def save(self, mode: str) -> None:
        if mode not in APPEARANCE_MODES:
            raise ValueError("Invalid appearance mode")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".settings-", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump({"appearance_mode": mode}, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
