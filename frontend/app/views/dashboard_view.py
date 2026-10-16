from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk

from frontend.app.api.client import (
    APIClient,
    APIClientError,
    APIRequestError
)


class DashboardView(ctk.CTkFrame):
    """Головна панель статистики складу."""

    SUMMARY_ENDPOINT = "/dashboard/summary"
    POLL_INTERVAL_MS = 50

    STATISTICS = (
        ("total_products", "Усього товарів"),
        ("total_categories", "Категорії"),
        ("total_suppliers", "Постачальники"),
        ("total_locations", "Складські локації"),
        ("in_stock_products", "Є в наявності"),
        ("out_of_stock_products", "Немає в наявності")
    )

    def __init__(
        self,
        master,
        api_client: APIClient,
        **kwargs: Any
    ) -> None:
        super().__init__(master, **kwargs)

        self.api_client = api_client

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="warehouse-dashboard"
        )

        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False

        self.value_labels: dict[str, ctk.CTkLabel] = {}

        self.grid_columnconfigure(0, weight=1)

        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        self.toolbar = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        self.toolbar.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(12, 8)
        )

        self.toolbar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.toolbar,
            text="Очікування завантаження",
            anchor="w"
        )
        self.status_label.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.refresh_button = ctk.CTkButton(
            self.toolbar,
            text="Оновити",
            width=110,
            command=self.refresh
        )
        self.refresh_button.grid(
            row=0,
            column=1,
            padx=(12, 0)
        )

        self.cards_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        self.cards_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=12,
            pady=12
        )

        for column in range(3):
            self.cards_frame.grid_columnconfigure(
                column,
                weight=1,
                uniform="dashboard_cards"
            )

        for index, (key, title) in enumerate(self.STATISTICS):
            row = index // 3
            column = index % 3

            card = ctk.CTkFrame(
                self.cards_frame,
                corner_radius=12
            )
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=6,
                pady=6
            )

            title_label = ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=14)
            )
            title_label.pack(
                padx=16,
                pady=(18, 6)
            )

            value_label = ctk.CTkLabel(
                card,
                text="—",
                font=ctk.CTkFont(
                    size=30,
                    weight="bold"
                )
            )
            value_label.pack(
                padx=16,
                pady=(0, 18)
            )

            self.value_labels[key] = value_label

    def refresh(self) -> None:
        """Асинхронно завантажує статистику."""

        if self._closed:
            return

        if self._future is not None:
            return

        self.status_label.configure(
            text="Завантаження статистики..."
        )
        self.refresh_button.configure(
            state="disabled"
        )

        try:
            self._future = self._executor.submit(
                self.api_client.get,
                self.SUMMARY_ENDPOINT
            )
        except RuntimeError:
            self.refresh_button.configure(
                state="normal"
            )
            self.status_label.configure(
                text="Не вдалося запустити завантаження"
            )
            return

        self._poll_job = self.after(
            self.POLL_INTERVAL_MS,
            self._check_result
        )

    def _check_result(self) -> None:
        """Перевіряє результат у головному потоці Tkinter."""

        self._poll_job = None

        if self._closed:
            return

        future = self._future

        if future is None:
            return

        if not future.done():
            self._poll_job = self.after(
                self.POLL_INTERVAL_MS,
                self._check_result
            )
            return

        self._future = None

        try:
            payload = future.result()
            self._apply_summary(payload)

        except APIRequestError as exc:
            self.status_label.configure(
                text=f"Помилка API ({exc.status_code}): {exc.message}"
            )

        except APIClientError as exc:
            self.status_label.configure(
                text=f"Помилка з'єднання: {exc}"
            )

        except (TypeError, ValueError, KeyError) as exc:
            self.status_label.configure(
                text=f"Некоректні дані Dashboard: {exc}"
            )

        except Exception as exc:
            self.status_label.configure(
                text=f"Непередбачена помилка завантаження: {exc}"
            )

        finally:
            self.refresh_button.configure(
                state="normal"
            )

    def _apply_summary(self, payload: Any) -> None:
        """Перевіряє та відображає відповідь Backend."""

        if not isinstance(payload, dict):
            raise TypeError("Очікується JSON-об'єкт")

        values = {}

        for key, _ in self.STATISTICS:
            value = payload[key]

            if type(value) is not int or value < 0:
                raise ValueError(
                    f"Некоректне значення поля {key}"
                )

            values[key] = value

        for key, value in values.items():
            self.value_labels[key].configure(
                text=str(value)
            )

        self.status_label.configure(
            text="Статистику успішно оновлено"
        )

    def destroy(self) -> None:
        """Скасовує опитування та звільняє ресурси."""

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
            cancel_futures=True
        )

        super().destroy()
