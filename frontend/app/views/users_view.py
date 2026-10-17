from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk

from frontend.app.api.client import (
    APIClient,
    APIClientError,
    APIRequestError,
)
from frontend.app.components.data_table import DataTable
from frontend.app.components.page_header import PageHeader
from frontend.app.services.user_management_service import (
    UserManagementError,
    UserManagementService,
)


class UsersView(ctk.CTkFrame):
    """Адміністративний екран перегляду користувачів."""

    POLL_INTERVAL_MS = 50
    PAGE_SIZE = 25

    COLUMNS = (
        "ID",
        "Ім'я",
        "Логін",
        "Роль",
        "Статус",
    )

    def __init__(
        self,
        master,
        api_client: APIClient,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)

        self.api_client = api_client
        self.user_service = UserManagementService(api_client)

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="warehouse-users",
        )
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False
        self.current_page = 1
        self._requested_page = 1
        self._requested_page_size = self.PAGE_SIZE

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        self.header = PageHeader(
            self,
            title="Керування користувачами",
            description="Перегляд облікових записів системи",
        )
        self.header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(20, 10),
        )

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 10),
        )

        toolbar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            toolbar,
            text="Очікування завантаження",
            anchor="w",
        )
        self.status_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=10,
        )

        self.refresh_button = ctk.CTkButton(
            toolbar,
            text="Оновити",
            width=120,
            command=self.refresh,
        )
        self.refresh_button.grid(
            row=0,
            column=1,
            padx=12,
            pady=10,
        )

        self.table = DataTable(
            self,
            columns=self.COLUMNS,
            empty_message="Користувачів не знайдено",
            page_size=self.PAGE_SIZE,
            pagination_mode="server",
            on_page_change=self.load_page,
            on_page_size_change=self.change_page_size,
        )
        self.table.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20),
        )

    def change_page_size(self, page_size: int) -> None:
        """Запитує першу сторінку з новим розміром."""

        if type(page_size) is not int:
            raise ValueError("Page size must be an integer")

        if page_size not in DataTable.PAGE_SIZE_OPTIONS:
            raise ValueError(
                f"Unsupported page size: {page_size}"
            )

        if self._closed or self._future is not None:
            return

        if page_size == self.table.page_size:
            return

        self._requested_page_size = page_size
        self._requested_page = 1
        self._start_loading(1)

    def load_page(self, page: int) -> None:
        """Асинхронно завантажує вибрану сторінку."""

        if type(page) is not int or page < 1:
            raise ValueError("Page must be a positive integer")

        if self._closed or self._future is not None:
            return

        self._requested_page = page
        self._start_loading(page)

    def refresh(self) -> None:
        """Повторно завантажує поточну сторінку."""

        if self._closed or self._future is not None:
            return

        self._requested_page = self.current_page
        self._start_loading(self.current_page)

    def _start_loading(self, page: int) -> None:
        """Запускає серверний запит без блокування GUI."""

        page_size = getattr(
            self,
            "_requested_page_size",
            self.table.page_size,
        )

        offset = (page - 1) * page_size
        limit = min(page_size + 1, 100)

        self.table.set_pagination_loading(True)

        self.status_label.configure(
            text=f"Завантаження сторінки {page}..."
        )
        self.refresh_button.configure(state="disabled")

        try:
            if page_size == 100:
                self._future = self._executor.submit(
                    self._fetch_users_with_lookahead,
                    offset,
                    page_size,
                )
            else:
                self._future = self._executor.submit(
                    self.user_service.list_users,
                    offset,
                    limit,
                )
        except RuntimeError:
            self._future = None
            self._requested_page_size = self.table.page_size
            self.table.page_size_selector.set(
                str(self.table.page_size)
            )
            self.table.set_pagination_loading(False)
            self.refresh_button.configure(state="normal")
            self.status_label.configure(
                text="Не вдалося запустити завантаження"
            )
            return

        self._poll_job = self.after(
            self.POLL_INTERVAL_MS,
            self._check_result,
        )

    def _fetch_users_with_lookahead(
        self,
        offset: int,
        page_size: int,
    ) -> list[dict[str, Any]]:
        """Отримує до 100 користувачів і перевіряє наступну сторінку."""

        users = self.user_service.list_users(offset, page_size)

        if len(users) == page_size:
            lookahead = self.user_service.list_users(
                offset + page_size,
                1,
            )
            return users + lookahead

        return users

    def _check_result(self) -> None:
        """Обробляє завершений запит у потоці Tkinter."""

        self._poll_job = None

        if self._closed:
            return

        future = self._future

        if future is None:
            return

        if not future.done():
            self._poll_job = self.after(
                self.POLL_INTERVAL_MS,
                self._check_result,
            )
            return

        self._future = None
        fallback_page = None

        try:
            users = future.result()
            page = self._requested_page

            if not users and page > 1:
                # Повертаємося на попередню сторінку,
                # якщо запитана сторінка стала порожньою.
                fallback_page = page - 1
                self.status_label.configure(
                    text=(
                        f"Сторінка {page} порожня. "
                        f"Завантаження сторінки {fallback_page}..."
                    )
                )
            else:
                page_size = self._requested_page_size
                has_next_page = len(users) > page_size

                self._apply_users(
                    users[:page_size],
                    page=page,
                    has_next_page=has_next_page,
                )

        except APIRequestError as exc:
            self.status_label.configure(
                text=f"Помилка API ({exc.status_code}): {exc.message}"
            )

        except APIClientError as exc:
            self.status_label.configure(
                text=f"Помилка з'єднання: {exc}"
            )

        except UserManagementError as exc:
            self.status_label.configure(
                text=f"Помилка даних користувачів: {exc}"
            )

        except Exception as exc:
            self.status_label.configure(
                text=f"Помилка завантаження: {exc}"
            )

        finally:
            if fallback_page is None:
                self._requested_page_size = self.table.page_size
                self.table.page_size_selector.set(
                    str(self.table.page_size)
                )

            self.table.set_pagination_loading(False)
            self.refresh_button.configure(state="normal")

        if fallback_page is not None and not self._closed:
            self.load_page(fallback_page)

    def _apply_users(
        self,
        users: list[dict[str, Any]],
        page: int = 1,
        has_next_page: bool = False,
    ) -> None:
        """Відображає сторінку перевірених сервісом даних."""

        rows = []

        for user in users:
            rows.append(
                (
                    user["id"],
                    user["name"],
                    user["username"],
                    "Адміністратор"
                    if user["role"] == "admin"
                    else "Працівник",
                    "Активний"
                    if user["is_active"]
                    else "Неактивний",
                )
            )

        page_size = self._requested_page_size
        self.table.page_size = page_size
        self.table.page_size_selector.set(str(page_size))

        self.table.set_server_page(
            rows,
            page=page,
            has_next_page=has_next_page,
        )

        self.current_page = page

        self.status_label.configure(
            text=(
                f"Сторінка {page}. "
                f"Завантажено користувачів: {len(users)}"
            )
        )

    def destroy(self) -> None:
        """Звільняє ресурси асинхронного завантаження."""

        if self._closed:
            return

        self._closed = True

        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except ValueError:
                pass

            self._poll_job = None

        if self._future is not None:
            self._future.cancel()
            self._future = None

        self._executor.shutdown(
            wait=False,
            cancel_futures=True,
        )

        super().destroy()
