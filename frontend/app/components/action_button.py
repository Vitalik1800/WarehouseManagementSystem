from collections.abc import Callable

import customtkinter as ctk


class ActionButton(ctk.CTkButton):
    """Багаторазова кнопка дії."""

    VARIANTS = ("primary", "secondary", "danger")

    def __init__(
        self,
        master,
        text: str,
        command: Callable[[], None] | None = None,
        variant: str = "primary",
        **kwargs
    ):
        if variant not in self.VARIANTS:
            raise ValueError(
                f"Unsupported button variant: {variant}"
            )

        self.variant = variant
        self._default_text = text
        self._busy = False

        styles = {
            "primary": {
                "fg_color": ("#1F6AA5", "#144870"),
                "hover_color": ("#185580", "#1A5A8C"),
                "text_color": "white",
            },
            "secondary": {
                "fg_color": ("gray80", "gray30"),
                "hover_color": ("gray70", "gray25"),
                "text_color": ("gray10", "gray95"),
            },
            "danger": {
                "fg_color": ("#B42318", "#912018"),
                "hover_color": ("#912018", "#751810"),
                "text_color": "white",
            }
        }

        options = {
            "height": 38,
            "corner_radius": 8,
            **styles[variant],
            **kwargs
        }

        super().__init__(
            master,
            text=text,
            command=command,
            **options
        )

    def set_busy(self, busy: bool) -> None:
        """Увімкнути або вимкнути стан виконання."""

        self._busy = busy

        if busy:
            self.configure(
                state="disabled",
                text="Зачекайте..."
            )
        else:
            self.configure(
                state="normal",
                text=self._default_text
            )

    def is_busy(self) -> bool:
        """Повернути поточний стан виконання."""
        return self._busy

    def set_text(self, text: str) -> None:
        """Змінити основний текст кнопки."""

        self._default_text = text

        if not self._busy:
            self.configure(text=text)
