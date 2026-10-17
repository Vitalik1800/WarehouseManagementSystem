from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk

from frontend.app.api.client import (
    APIClientError,
    APIConnectionError,
    APIRequestError,
)
from frontend.app.components.action_button import ActionButton
from frontend.app.components.form_field import FormField
from frontend.app.components.notification_banner import NotificationBanner
from frontend.app.services.user_registration_service import (
    UserRegistrationService,
)


class RegisterView(ctk.CTkFrame):
    """Форма створення користувачів адміністратором."""

    def __init__(
        self,
        master,
        registration_service: UserRegistrationService,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.registration_service = registration_service
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="warehouse-register",
        )
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_widgets()

    def _create_widgets(self) -> None:
        self.card = ctk.CTkScrollableFrame(
            self,
            width=460,
            corner_radius=12,
        )
        self.card.grid(row=0, column=0, padx=24, pady=16, sticky="n")
        self.card.grid_columnconfigure(0, weight=1)

        self.name_field = FormField(
            self.card,
            label="Ім'я користувача",
            placeholder="Введіть ім'я",
            required=True,
        )
        self.name_field.grid(
            row=0, column=0, sticky="ew", padx=20, pady=(20, 12)
        )

        self.username_field = FormField(
            self.card,
            label="Логін",
            placeholder="Латинські літери, цифри та _",
            required=True,
        )
        self.username_field.grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 12)
        )

        self.password_field = FormField(
            self.card,
            label="Пароль",
            placeholder="Від 8 до 128 символів",
            required=True,
            show="*",
        )
        self.password_field.grid(
            row=2, column=0, sticky="ew", padx=20, pady=(0, 12)
        )

        self.confirm_password_field = FormField(
            self.card,
            label="Підтвердження пароля",
            placeholder="Повторіть пароль",
            required=True,
            show="*",
        )
        self.confirm_password_field.grid(
            row=3, column=0, sticky="ew", padx=20, pady=(0, 12)
        )

        self.role_label = ctk.CTkLabel(
            self.card,
            text="Роль користувача",
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.role_label.grid(
            row=4, column=0, sticky="ew", padx=20, pady=(0, 6)
        )

        self.role_selector = ctk.CTkOptionMenu(
            self.card,
            values=["worker", "admin"],
        )
        self.role_selector.grid(
            row=5, column=0, sticky="ew", padx=20, pady=(0, 16)
        )
        self.role_selector.set("worker")

        self.notification = NotificationBanner(
            self.card,
            variant="info",
        )
        self.notification.grid(
            row=6, column=0, sticky="ew", padx=20, pady=(0, 12)
        )
        self.notification.hide()

        self.register_button = ActionButton(
            self.card,
            text="Створити користувача",
            command=self.register,
            variant="primary",
        )
        self.register_button.grid(
            row=7, column=0, sticky="ew", padx=20, pady=(0, 20)
        )

    def _validate_fields(self) -> bool:
        """Перевіряє введені дані до надсилання API-запиту."""

        fields = (
            self.name_field,
            self.username_field,
            self.password_field,
            self.confirm_password_field,
        )

        valid = True

        for field in fields:
            if not field.validate():
                valid = False

        if not valid:
            return False

        name = self.name_field.get_value()
        username = self.username_field.get_value()
        password = self.password_field.entry.get()
        confirmation = self.confirm_password_field.entry.get()

        if not 2 <= len(name) <= 150:
            self.name_field.show_error(
                "Ім'я повинно містити від 2 до 150 символів"
            )
            valid = False

        if not 3 <= len(username) <= 50:
            self.username_field.show_error(
                "Логін повинен містити від 3 до 50 символів"
            )
            valid = False
        elif not all(
            character in (
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789_"
            )
            for character in username
        ):
            self.username_field.show_error(
                "Дозволені лише латинські літери, цифри та _"
            )
            valid = False

        if not 8 <= len(password) <= 128:
            self.password_field.show_error(
                "Пароль повинен містити від 8 до 128 символів"
            )
            valid = False

        if password != confirmation:
            self.confirm_password_field.show_error(
                "Паролі не збігаються"
            )
            valid = False

        return valid

    def register(self) -> None:
        """Запускає створення користувача у фоновому потоці."""

        if self._closed or self.register_button.is_busy():
            return

        self.notification.hide()

        if not self._validate_fields():
            return

        name = self.name_field.get_value()
        username = self.username_field.get_value()
        password = self.password_field.entry.get()
        role = self.role_selector.get()

        self.register_button.set_busy(True)

        try:
            self._future = self._executor.submit(
                self.registration_service.register_user,
                name=name,
                username=username,
                password=password,
                role=role,
            )
        except RuntimeError:
            self.register_button.set_busy(False)
            self.notification.show(
                "Не вдалося запустити створення користувача.",
                variant="error",
            )
            return

        self._poll_job = self.after(50, self._check_result)

    def _check_result(self) -> None:
        self._poll_job = None

        if self._closed:
            return

        future = self._future

        if future is None:
            return

        if not future.done():
            self._poll_job = self.after(50, self._check_result)
            return

        self._future = None
        self.register_button.set_busy(False)

        try:
            user: dict[str, Any] = future.result()
        except APIConnectionError:
            message = "Немає з'єднання із сервером."
        except APIRequestError as exc:
            messages = {
                401: "Сесію завершено. Увійдіть повторно.",
                403: "Створювати користувачів може лише адміністратор.",
                409: "Користувач із таким логіном уже існує.",
                422: "Сервер відхилив введені дані.",
            }
            message = messages.get(
                exc.status_code,
                f"Помилка сервера: HTTP {exc.status_code}.",
            )
        except (APIClientError, ValueError):
            message = "Не вдалося створити користувача."
        except Exception:
            message = "Виникла непередбачена помилка."
        else:
            self.password_field.clear()
            self.confirm_password_field.clear()
            self.notification.show(
                f"Користувача {user['username']} успішно створено.",
                variant="success",
            )
            return

        self.notification.show(message, variant="error")

    def destroy(self) -> None:
        self._closed = True

        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except ValueError:
                pass
            self._poll_job = None

        self._executor.shutdown(
            wait=False,
            cancel_futures=True,
        )

        super().destroy()
