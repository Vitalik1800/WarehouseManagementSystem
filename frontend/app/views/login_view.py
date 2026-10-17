
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk

from frontend.app.services.auth_service import (
    AuthService,
    AuthenticationError
)
from frontend.app.api.client import (
    APIClientError,
    APIConnectionError,
    APIRequestError
)
from frontend.app.components.action_button import ActionButton
from frontend.app.components.form_field import FormField
from frontend.app.components.notification_banner import NotificationBanner


class LoginView(ctk.CTkFrame):
    """Графічна форма авторизації користувача."""

    def __init__(
        self,
        master,
        auth_service: AuthService,
        on_login_success: Callable[[dict[str, Any]], None],
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.auth_service = auth_service
        self.on_login_success = on_login_success

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="warehouse-login"
        )
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Створює графічні компоненти форми."""

        self.card = ctk.CTkFrame(
            self,
            width=420,
            corner_radius=16
        )
        self.card.grid(
            row=0,
            column=0,
            padx=24,
            pady=24
        )
        self.card.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.card,
            text="Warehouse Management System",
            font=ctk.CTkFont(
                size=22,
                weight="bold"
            )
        )
        self.title_label.grid(
            row=0,
            column=0,
            padx=30,
            pady=(30, 8)
        )

        self.subtitle_label = ctk.CTkLabel(
            self.card,
            text="Увійдіть до свого облікового запису",
            font=ctk.CTkFont(size=14)
        )
        self.subtitle_label.grid(
            row=1,
            column=0,
            padx=30,
            pady=(0, 24)
        )

        self.username_field = FormField(
            self.card,
            label="Логін",
            placeholder="Введіть логін",
            required=True
        )
        self.username_field.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=30,
            pady=(0, 16)
        )

        self.password_field = FormField(
            self.card,
            label="Пароль",
            placeholder="Введіть пароль",
            required=True,
            show="*"
        )
        self.password_field.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=30,
            pady=(0, 16)
        )

        self.notification = NotificationBanner(
            self.card,
            variant="error"
        )
        self.notification.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=30,
            pady=(0, 16)
        )
        self.notification.hide()

        self.login_button = ActionButton(
            self.card,
            text="Увійти",
            command=self.login,
            variant="primary"
        )
        self.login_button.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=30,
            pady=(0, 30)
        )

        self.username_field.entry.bind(
            "<Return>",
            self._on_enter
        )
        self.password_field.entry.bind(
            "<Return>",
            self._on_enter
        )

    def _on_enter(self, _event=None) -> None:
        """Запускає авторизацію натисканням Enter."""
        self.login()

    def _validate_fields(self) -> bool:
        """Перевіряє обов'язкові поля."""

        username_valid = self.username_field.validate()
        password_valid = self.password_field.validate()

        return username_valid and password_valid

    def login(self) -> None:
        """Запускає авторизацію без блокування GUI."""

        if self._closed or self.login_button.is_busy():
            return

        self.notification.hide()

        if not self._validate_fields():
            return

        username = self.username_field.get_value()

        # Пароль не повинен автоматично обрізатися.
        password = self.password_field.entry.get()

        self.login_button.set_busy(True)

        try:
            self._future = self._executor.submit(
                self._authenticate,
                username,
                password
            )
        except RuntimeError:
            self.login_button.set_busy(False)
            self.notification.show(
                "Не вдалося запустити авторизацію.",
                variant="error"
            )
            return

        self._poll_job = self.after(
            50,
            self._check_login_result
        )

    def _authenticate(
        self,
        username: str,
        password: str
    ) -> dict[str, Any]:
        """Виконує авторизацію та отримує профіль користувача."""

        self.auth_service.login(
            username=username,
            password=password
        )

        try:
            return self.auth_service.get_current_user()
        except Exception:
            self.auth_service.api_client.clear_access_token()
            raise

    def _check_login_result(self) -> None:
        """Обробляє результат у головному потоці Tkinter."""

        self._poll_job = None

        if self._closed:
            return

        future = self._future

        if future is None:
            return

        if not future.done():
            self._poll_job = self.after(
                50,
                self._check_login_result
            )
            return

        self._future = None
        self.login_button.set_busy(False)

        try:
            user = future.result()

        except APIConnectionError:
            self.notification.show(
                "Немає з'єднання із сервером. "
                "Перевірте, чи запущено Backend.",
                variant="error"
            )
            return

        except APIRequestError as exc:
            if exc.status_code == 401:
                message = "Неправильний логін або пароль."
            elif exc.status_code == 403:
                message = "Доступ до системи заборонено."
            else:
                message = (
                    f"Помилка сервера: HTTP {exc.status_code}."
                )

            self.notification.show(
                message,
                variant="error"
            )
            return

        except (AuthenticationError, APIClientError, ValueError):
            self.notification.show(
                "Не вдалося виконати авторизацію.",
                variant="error"
            )
            return

        self.password_field.clear()
        self.on_login_success(user)

    def destroy(self) -> None:
        """Звільняє ресурси форми."""

        self._closed = True

        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except ValueError:
                pass

            self._poll_job = None

        self._executor.shutdown(
            wait=False,
            cancel_futures=True
        )

        super().destroy()
