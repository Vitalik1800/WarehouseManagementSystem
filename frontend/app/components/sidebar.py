from collections.abc import Callable

import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    """Бічна панель навігації застосунку."""

    NAVIGATION_ITEMS = (
        ("dashboard", "Головна"),
        ("products", "Товари"),
        ("categories", "Категорії"),
        ("suppliers", "Постачальники"),
        ("storage_locations", "Місця зберігання"),
        ("warehouses", "Склади"),
        ("stock_balances", "Залишки"),
        ("stock_movements", "Складські операції"),
        ("activity_log", "Журнал активності"),
        ("settings", "Налаштування"),
        ("register", "Реєстрація користувача"),
        ("users", "Користувачі")
    )

    def __init__(
            self,
            master,
            on_navigate: Callable[[str], None],
        user_role: str = "worker",
            **kwargs
    ):
        super().__init__(
            master,
            width=220,
            corner_radius=0,
            **kwargs
        )

        self.on_navigate = on_navigate
        self.user_role = user_role
        self.active_page = "dashboard"
        self.buttons: dict[str, ctk.CTkButton] = {}

        self.grid_propagate(False)

        self._create_widgets()
        self.set_active_page(self.active_page)

    def _create_widgets(self):
        title = ctk.CTkLabel(
            self,
            text="Навігація",
            font=ctk.CTkFont(
                size=16,
                weight="bold"
            )
        )
        title.pack(
            anchor="w",
            padx=20,
            pady=(24, 16)
        )

        for page_id, label in self.NAVIGATION_ITEMS:
            if page_id in ("register", "users") and self.user_role != "admin":
                continue
            button = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                height=38,
                corner_radius=8,
                command=lambda page=page_id: (
                    self.navigate(page)
                )
            )
            button.pack(
                fill="x",
                padx=12,
                pady=4
            )

            self.buttons[page_id] = button

    def navigate(self, page_id: str):
        """Передати вибір сторінки головному інтерфейсу."""

        if page_id not in self.buttons:
            raise ValueError(
                f"Unknown navigation page: {page_id}"
            )

        self.on_navigate(page_id)
        self.set_active_page(page_id)

    def set_active_page(self, page_id: str):
        """Позначити активний пункт меню."""

        if page_id not in self.buttons:
            raise ValueError(
                f"Unknown navigation page: {page_id}"
            )

        self.active_page = page_id

        for button_id, button in self.buttons.items():
            if button_id == page_id:
                button.configure(
                    fg_color=(
                        "#1F6AA5",
                        "#144870"
                    ),
                    hover_color=(
                        "#1A5A8C",
                        "#1A5A8C"
                    )
                )
            else:
                button.configure(
                    fg_color="transparent",
                    hover_color=(
                        "gray80",
                        "gray25"
                    )
                )
