from collections.abc import Callable

import customtkinter as ctk

from frontend.app.components.page_header import PageHeader
from frontend.app.components.sidebar import Sidebar
from frontend.app.core.config import get_frontend_settings


class MainLayout(ctk.CTkFrame):
    """Основний каркас графічного інтерфейсу."""

    APPEARANCE_MODES = ("System", "Light", "Dark")

    PAGE_DESCRIPTIONS = {
        "dashboard": "Загальний огляд системи управління складом",
        "products": "Перегляд та управління товарами",
        "categories": "Управління категоріями товарів",
        "warehouses": "Перегляд та управління складами",
        "stock_balances": "Контроль актуальних залишків товарів",
        "stock_movements": "Облік надходжень, переміщень та списань",
        "activity_log": "Історія дій користувачів системи",
        "settings": "Налаштування настільного застосунку",
    }

    def __init__(
        self,
        master,
        on_logout: Callable[[], None] | None = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.settings = get_frontend_settings()
        self.current_page = "dashboard"
        self.on_logout = on_logout

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._create_header()
        self._create_sidebar()
        self._create_content()
        self._create_status_bar()

        self._show_page(self.current_page)

    def _create_header(self):
        self.header = ctk.CTkFrame(
            self,
            height=64,
            corner_radius=0
        )
        self.header.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew"
        )
        self.header.grid_propagate(False)

        self.header_label = ctk.CTkLabel(
            self.header,
            text="Warehouse Management System",
            font=ctk.CTkFont(
                size=20,
                weight="bold"
            )
        )
        self.header_label.pack(
            side="left",
            padx=24,
            pady=14
        )

        self.theme_selector = ctk.CTkOptionMenu(
            self.header,
            values=list(self.APPEARANCE_MODES),
            command=self._change_appearance_mode,
            width=130
        )
        self.theme_selector.pack(
            side="right",
            padx=24,
            pady=14
        )
        self.theme_selector.set(
            self.settings.frontend_appearance_mode
        )

        if self.on_logout is not None:
            self.logout_button = ctk.CTkButton(
                self.header,
                text="Вийти",
                width=100,
                command=self.on_logout
            )
            self.logout_button.pack(
                side="right",
                padx=(0, 12),
                pady=14
            )

    def _change_appearance_mode(self, mode: str):
        """Змінити тему оформлення."""

        if mode not in self.APPEARANCE_MODES:
            raise ValueError(
                f"Unsupported appearance mode: {mode}"
            )

        ctk.set_appearance_mode(mode)

    def _create_sidebar(self):
        self.sidebar = Sidebar(
            self,
            on_navigate=self._show_page
        )
        self.sidebar.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

    def _create_content(self):
        self.content = ctk.CTkFrame(
            self,
            corner_radius=12
        )
        self.content.grid(
            row=1,
            column=1,
            sticky="nsew",
            padx=16,
            pady=16
        )

        self.content.grid_columnconfigure(0, weight=1)

        self.page_header = PageHeader(
            self.content,
            title="",
            description=""
        )
        self.page_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=24,
            pady=24
        )

    def _create_status_bar(self):
        self.status_bar = ctk.CTkFrame(
            self,
            height=36,
            corner_radius=0
        )
        self.status_bar.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew"
        )
        self.status_bar.grid_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Готово до роботи",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(
            side="left",
            padx=16
        )

    def _show_page(self, page_id: str):
        """Відобразити вибраний розділ."""

        pages = dict(Sidebar.NAVIGATION_ITEMS)

        if page_id not in pages:
            raise ValueError(
                f"Unknown page: {page_id}"
            )

        self.current_page = page_id

        self.page_header.set_title(
            pages[page_id]
        )
        self.page_header.set_description(
            self.PAGE_DESCRIPTIONS.get(page_id, "")
        )

        self.sidebar.set_active_page(page_id)

        self.status_label.configure(
            text=f"Поточний розділ: {pages[page_id]}"
        )
