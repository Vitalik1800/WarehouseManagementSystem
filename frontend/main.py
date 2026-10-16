
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk

from frontend.app.api.auth_service import AuthService
from frontend.app.api.client import APIClient, APIClientError
from frontend.app.components.main_layout import MainLayout
from frontend.app.core.config import get_frontend_settings
from frontend.app.core.logging_config import get_frontend_logger
from frontend.app.views.login_view import LoginView


class WarehouseApplication(ctk.CTk):
    """Головне вікно системи управління складом."""

    def __init__(self):
        super().__init__()

        self.settings = get_frontend_settings()
        self.logger = get_frontend_logger("main")

        self.api_client = APIClient(settings=self.settings)
        self.auth_service = AuthService(self.api_client)

        self.current_user: dict[str, Any] | None = None
        self.login_view: LoginView | None = None
        self.main_layout: MainLayout | None = None

        self._closing = False
        self._logging_out = False
        self._logout_future: Future | None = None
        self._logout_poll_job: str | None = None

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="warehouse-logout"
        )

        self.title("Система управління складом")
        self.geometry(
            f"{self.settings.frontend_window_width}x"
            f"{self.settings.frontend_window_height}"
        )
        self.minsize(
            self.settings.frontend_min_window_width,
            self.settings.frontend_min_window_height
        )

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._show_login()

        self.logger.info("Головний інтерфейс ініціалізовано")

    def _show_login(self) -> None:
        """Відображає форму входу."""

        if self._closing:
            return

        if self.main_layout is not None:
            self.main_layout.destroy()
            self.main_layout = None

        if self.login_view is not None:
            self.login_view.destroy()
            self.login_view = None

        self.current_user = None

        self.login_view = LoginView(
            self,
            auth_service=self.auth_service,
            on_login_success=self._on_login_success
        )
        self.login_view.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

    def _on_login_success(
        self,
        user: dict[str, Any]
    ) -> None:
        """Відкриває головний інтерфейс після входу."""

        if self._closing or self._logging_out:
            return

        if not self.auth_service.is_authenticated:
            self.logger.warning(
                "Спроба відкрити MainLayout без авторизації"
            )
            return

        if not isinstance(user, dict):
            self.logger.warning(
                "Отримано некоректні дані користувача"
            )
            return

        self.current_user = user

        if self.login_view is not None:
            self.login_view.destroy()
            self.login_view = None

        self.main_layout = MainLayout(
            self,
            on_logout=self._on_logout,
            current_user=self.current_user
        )
        self.main_layout.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.logger.info(
            "Авторизація успішна, MainLayout відкрито"
        )

    def _on_logout(self) -> None:
        """Запускає logout без блокування GUI."""

        if self._closing or self._logging_out:
            return

        if self.main_layout is None:
            return

        self._logging_out = True

        if hasattr(self.main_layout, "logout_button"):
            self.main_layout.logout_button.configure(
                state="disabled",
                text="Вихід..."
            )

        try:
            self._logout_future = self._executor.submit(
                self._perform_logout
            )
        except RuntimeError:
            self._complete_logout()
            return

        self._logout_poll_job = self.after(
            50,
            self._check_logout_result
        )

    def _perform_logout(self) -> None:
        """Виконує HTTP-запит logout у фоновому потоці."""

        self.auth_service.logout()

    def _check_logout_result(self) -> None:
        """Обробляє завершення logout у потоці Tkinter."""

        self._logout_poll_job = None

        if self._closing:
            return

        future = self._logout_future

        if future is None:
            return

        if not future.done():
            self._logout_poll_job = self.after(
                50,
                self._check_logout_result
            )
            return

        self._logout_future = None

        try:
            future.result()
        except APIClientError as exc:
            self.logger.warning(
                "Не вдалося підтвердити logout на сервері: %s",
                exc
            )
        except Exception as exc:
            self.logger.exception(
                "Непередбачена помилка під час logout",
                exc
            )
        finally:
            self._complete_logout()

    def _complete_logout(self) -> None:
        """Очищає локальну сесію та повертає LoginView."""

        if self._closing:
            return

        self.api_client.clear_access_token()
        self.current_user = None
        self._logout_future = None
        self._logging_out = False

        self._show_login()

        self.logger.info(
            "Локальну сесію завершено"
        )

    def on_close(self) -> None:
        """Безпечно завершує роботу застосунку."""

        if self._closing:
            return

        self._closing = True

        self.logger.info(
            "Завершення роботи WarehouseManagementSystem"
        )

        if self._logout_poll_job is not None:
            try:
                self.after_cancel(self._logout_poll_job)
            except ValueError:
                pass

            self._logout_poll_job = None

        if self.login_view is not None:
            self.login_view.destroy()
            self.login_view = None

        if self.main_layout is not None:
            self.main_layout.destroy()
            self.main_layout = None

        self.current_user = None

        self._executor.shutdown(
            wait=False,
            cancel_futures=True
        )

        self.api_client.clear_access_token()
        self.api_client.close()

        self.destroy()


def main():
    """Точка входу настільного застосунку."""

    settings = get_frontend_settings()

    ctk.set_appearance_mode(
        settings.frontend_appearance_mode
    )
    ctk.set_default_color_theme(
        settings.frontend_color_theme
    )

    logger = get_frontend_logger("startup")
    logger.info("Запуск настільного застосунку")

    app = WarehouseApplication()
    app.mainloop()


if __name__ == "__main__":
    main()
