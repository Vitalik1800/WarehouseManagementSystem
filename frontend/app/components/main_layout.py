from collections.abc import Callable

import customtkinter as ctk

from frontend.app.components.page_header import PageHeader
from frontend.app.components.sidebar import Sidebar
from frontend.app.core.config import get_frontend_settings
from frontend.app.core.appearance_settings_store import AppearanceSettingsStore

from typing import Any

from frontend.app.components.user_info_panel import UserInfoPanel

from frontend.app.api.client import APIClient
from frontend.app.views.dashboard_view import DashboardView
from frontend.app.views.register_view import RegisterView
from frontend.app.views.users_view import UsersView
from frontend.app.views.categories_view import CategoriesView
from frontend.app.views.suppliers_view import SuppliersView
from frontend.app.views.products_view import ProductsView
from frontend.app.views.storage_locations_view import StorageLocationsView
from frontend.app.views.warehouses_view import WarehousesView
from frontend.app.views.activity_log_view import ActivityLogView
from frontend.app.views.settings_view import SettingsView
from frontend.app.views.stock_movements_view import StockMovementsView
from frontend.app.views.stock_balances_view import StockBalancesView
from frontend.app.services.user_registration_service import (
    UserRegistrationService,
)


class MainLayout(ctk.CTkFrame):
    """Основний каркас графічного інтерфейсу."""

    APPEARANCE_MODES = ("System", "Light", "Dark")

    PAGE_DESCRIPTIONS = {
        "dashboard": "Загальний огляд системи управління складом",
        "products": "Перегляд та управління товарами",
        "categories": "Управління категоріями товарів",
        "warehouses": "Перегляд та управління складами",
        "storage_locations": "Управління місцями зберігання",
        "stock_balances": "Контроль актуальних залишків товарів",
        "stock_movements": "Облік надходжень, переміщень та списань",
        "activity_log": "Історія дій користувачів системи",
        "settings": "Налаштування настільного застосунку",
        "register": "Створення облікових записів адміністратором",
        "users": "Перегляд та керування користувачами системи",
    }

    def __init__(
        self,
        master,
        on_logout: Callable[[], None] | None = None,
        current_user: dict[str, Any] | None = None,
        api_client: APIClient | None = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.settings = get_frontend_settings()
        self.appearance_store = AppearanceSettingsStore()
        self.current_page = "dashboard"
        self.on_logout = on_logout
        self.api_client = api_client
        self.active_view: DashboardView | RegisterView | UsersView | None = None

        self.current_user = (
            current_user.copy()
            if current_user is not None
            else None
        )

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
            self.appearance_store.load(self.settings.frontend_appearance_mode)
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

        if self.current_user is not None:
            self.user_info_panel = UserInfoPanel(
                self.header,
                user=self.current_user
            )
            self.user_info_panel.pack(
                side="right",
                padx=(0, 12),
                pady=8
            )

    def _change_appearance_mode(self, mode: str):
        """Змінити тему оформлення."""

        if mode not in self.APPEARANCE_MODES:
            raise ValueError(
                f"Unsupported appearance mode: {mode}"
            )

        self.appearance_store.save(mode)
        ctk.set_appearance_mode(mode)
        if self.active_view is not None and isinstance(self.active_view, SettingsView):
            self.active_view.set_appearance_mode(mode)

    def _create_sidebar(self):
        self.sidebar = Sidebar(
            self,
            on_navigate=self._show_page,
            user_role=(
                self.current_user.get("role", "worker")
                if self.current_user is not None
                else "worker"
            ),
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

        self.content.grid_rowconfigure(1, weight=1)

        self.page_container = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )
        self.page_container.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=18,
            pady=(0, 18),
        )

        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)

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

        if self.active_view is not None:
            self.active_view.destroy()
            self.active_view = None

    def _show_page(self, page_id: str):
        """Відобразити вибраний розділ."""

        pages = dict(Sidebar.NAVIGATION_ITEMS)

        if page_id not in pages:
            raise ValueError(
                f"Unknown page: {page_id}"
            )

        if page_id in ("register", "users"):
            if (
                self.current_user is None
                or self.current_user.get("role") != "admin"
            ):
                raise PermissionError(
                    "Лише адміністратор може відкривати цей розділ"
                )

            if self.api_client is None:
                raise RuntimeError(
                    "Для адміністративного розділу потрібне підключення до API"
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

        # Видаляємо попередню сторінку.
        if self.active_view is not None:
            self.active_view.destroy()
            self.active_view = None

        # Відображаємо Dashboard.
        if page_id == "dashboard" and self.api_client is not None:
            self.active_view = DashboardView(
                self.page_container,
                api_client=self.api_client,
            )

            self.active_view.grid(
                row=0,
                column=0,
                sticky="nsew",
            )

        elif page_id == "products":
            if self.api_client is None:
                raise RuntimeError("Для товарів потрібне підключення до API")
            self.active_view = ProductsView(
                self.page_container,
                api_client=self.api_client,
                user_role=(
                    self.current_user.get("role", "worker")
                    if self.current_user is not None else "worker"
                ),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "suppliers":
            if self.api_client is None:
                raise RuntimeError("Для постачальників потрібне підключення до API")
            self.active_view = SuppliersView(
                self.page_container,
                api_client=self.api_client,
                user_role=(
                    self.current_user.get("role", "worker")
                    if self.current_user is not None else "worker"
                ),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "warehouses":
            if self.api_client is None:
                raise RuntimeError("Для складів потрібне підключення до API")
            self.active_view = WarehousesView(
                self.page_container,
                api_client=self.api_client,
                user_role=(self.current_user.get("role", "worker") if self.current_user else "worker"),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "storage_locations":
            if self.api_client is None:
                raise RuntimeError("Для місць зберігання потрібне підключення до API")
            self.active_view = StorageLocationsView(
                self.page_container,
                api_client=self.api_client,
                user_role=(self.current_user.get("role", "worker") if self.current_user else "worker"),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "categories":
            if self.api_client is None:
                raise RuntimeError("Для категорій потрібне підключення до API")
            self.active_view = CategoriesView(
                self.page_container,
                api_client=self.api_client,
                user_role=(
                    self.current_user.get("role", "worker")
                    if self.current_user is not None else "worker"
                ),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "stock_movements":
            if self.api_client is None:
                raise RuntimeError("Для складських операцій потрібне підключення до API")
            self.active_view = StockMovementsView(
                self.page_container, api_client=self.api_client,
                user_role=(self.current_user.get("role", "worker") if self.current_user else "worker"),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "stock_balances":
            if self.api_client is None:
                raise RuntimeError("Для залишків потрібне підключення до API")
            self.active_view = StockBalancesView(
                self.page_container, api_client=self.api_client,
                user_role=(self.current_user.get("role", "worker") if self.current_user else "worker"),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "activity_log":
            if self.api_client is None:
                raise RuntimeError("Для журналу активності потрібне підключення до API")
            self.active_view = ActivityLogView(
                self.page_container,
                api_client=self.api_client,
                user_role=(
                    self.current_user.get("role", "worker")
                    if self.current_user is not None else "worker"
                ),
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "settings":
            self.active_view = SettingsView(
                self.page_container,
                appearance_mode=self.appearance_store.load(
                    self.settings.frontend_appearance_mode
                ),
                on_appearance_change=self._change_appearance_mode,
                api_base_url=self.settings.frontend_api_base_url,
                request_timeout=self.settings.frontend_request_timeout,
            )
            self.active_view.grid(row=0, column=0, sticky="nsew")

        elif page_id == "users":
            self.active_view = UsersView(
                self.page_container,
                api_client=self.api_client,
            )

            self.active_view.grid(
                row=0,
                column=0,
                sticky="nsew",
            )

        elif page_id == "register":
            registration_service = UserRegistrationService(
                self.api_client
            )

            self.active_view = RegisterView(
                self.page_container,
                registration_service=registration_service,
            )

            self.active_view.grid(
                row=0,
                column=0,
                sticky="nsew",
            )
