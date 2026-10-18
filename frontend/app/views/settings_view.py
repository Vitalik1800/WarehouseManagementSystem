"""Read-only application information and appearance controls."""
from collections.abc import Callable

import customtkinter as ctk

from frontend.app.core.appearance_settings_store import APPEARANCE_MODES


def validate_appearance_mode(mode: str) -> str:
    if mode not in APPEARANCE_MODES:
        raise ValueError(f"Unsupported appearance mode: {mode}")
    return mode


class SettingsView(ctk.CTkFrame):
    """Local presentation preferences; persistence belongs to MainLayout."""

    def __init__(
        self,
        master,
        *,
        appearance_mode: str,
        on_appearance_change: Callable[[str], None],
        api_base_url: str,
        request_timeout: float,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_appearance_change = on_appearance_change
        self.appearance_mode = validate_appearance_mode(appearance_mode)
        self.grid_columnconfigure(0, weight=1)

        heading = ctk.CTkLabel(self, text="Оформлення", font=ctk.CTkFont(size=18, weight="bold"))
        heading.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))
        description = ctk.CTkLabel(self, text="Оберіть тему інтерфейсу. Зміни зберігаються автоматично.", anchor="w")
        description.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        self.theme_selector = ctk.CTkOptionMenu(
            self, values=list(APPEARANCE_MODES), command=self._on_theme_selected, width=180
        )
        self.theme_selector.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 20))
        self.theme_selector.set(self.appearance_mode)

        info_heading = ctk.CTkLabel(self, text="Підключення (лише перегляд)", font=ctk.CTkFont(size=18, weight="bold"))
        info_heading.grid(row=3, column=0, sticky="w", padx=18, pady=(8, 8))
        self.api_label = ctk.CTkLabel(self, text=f"Адреса API: {api_base_url}", anchor="w", wraplength=640)
        self.api_label.grid(row=4, column=0, sticky="ew", padx=18, pady=4)
        self.timeout_label = ctk.CTkLabel(self, text=f"Тайм-аут запиту: {request_timeout:g} с", anchor="w")
        self.timeout_label.grid(row=5, column=0, sticky="ew", padx=18, pady=4)

    def _on_theme_selected(self, mode: str) -> None:
        validate_appearance_mode(mode)
        previous = self.appearance_mode
        try:
            self.on_appearance_change(mode)
        except Exception:
            self.theme_selector.set(previous)
            raise
        self.appearance_mode = mode

    def set_appearance_mode(self, mode: str) -> None:
        """Sync with header selector without invoking persistence callback."""
        self.appearance_mode = validate_appearance_mode(mode)
        self.theme_selector.set(mode)
