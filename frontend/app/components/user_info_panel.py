from typing import Any

import customtkinter as ctk


class UserInfoPanel(ctk.CTkFrame):
    """Панель інформації про авторизованого користувача."""

    ROLE_LABELS = {
        "admin": "Адміністратор",
        "manager": "Менеджер",
        "worker": "Працівник",
        "storekeeper": "Комірник",
        "user": "Користувач"
    }

    def __init__(
        self,
        master,
        user: dict[str, Any],
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.user: dict[str, Any] = {}

        self.username_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(
                size=13,
                weight="bold"
            ),
            anchor="e"
        )
        self.username_label.pack(
            anchor="e"
        )

        self.role_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray70"),
            anchor="e"
        )
        self.role_label.pack(
            anchor="e"
        )

        self.set_user(user)

    @staticmethod
    def _safe_text(
        value: Any,
        fallback: str
    ) -> str:
        """Повертає непорожнє текстове значення."""

        if not isinstance(value, str):
            return fallback

        value = value.strip()
        return value or fallback

    @classmethod
    def _format_role(cls, role: Any) -> str:
        """Перетворює системну роль на зрозумілу назву."""

        role_text = cls._safe_text(
            role,
            "Невідома роль"
        )

        return cls.ROLE_LABELS.get(
            role_text.lower(),
            role_text
        )

    def set_user(
        self,
        user: dict[str, Any]
    ) -> None:
        """Оновлює відображувані дані користувача."""

        if not isinstance(user, dict):
            raise TypeError(
                "user must be a dictionary"
            )

        self.user = user.copy()

        username = self._safe_text(
            self.user.get("username"),
            "Невідомий користувач"
        )

        role = self._format_role(
            self.user.get("role")
        )

        self.username_label.configure(
            text=username
        )
        self.role_label.configure(
            text=role
        )
