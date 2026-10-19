"""Read-only activity journal GUI; all Tk calls run on the UI thread."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import json
from typing import Any

import customtkinter as ctk

from frontend.app.api.client import APIClient
from frontend.app.components.data_table import DataTable
from frontend.app.core.gui_errors import format_gui_error
from frontend.app.services.user_activity_log_service import UserActivityLogClientService


def parse_activity_filters(raw: dict[str, str], role: str) -> dict[str, Any]:
    """Validate user-entered filters before any network request."""
    if role not in ("admin", "worker"):
        raise ValueError("Unsupported role")
    result: dict[str, Any] = {}
    for field in ("actor_id", "entity_id"):
        value = raw.get(field, "").strip()
        if value:
            if not value.isdecimal() or int(value) < 1:
                raise ValueError(f"{field}: потрібне додатне ціле число")
            if field == "actor_id" and role == "worker":
                raise ValueError("Працівник не може вибирати іншого користувача")
            result[field] = int(value)
    for field, maximum in (("action", 100), ("entity_type", 50)):
        value = raw.get(field, "").strip()
        if value:
            if len(value) > maximum:
                raise ValueError(f"{field}: максимум {maximum} символів")
            result[field] = value
    for field in ("date_from", "date_to"):
        value = raw.get(field, "").strip()
        if value:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{field}: формат РРРР-ММ-ДД або РРРР-ММ-ДД ГГ:ХХ") from exc
            if parsed.tzinfo is not None:
                raise ValueError(f"{field}: часовий пояс не підтримується")
            if field == "date_to" and len(value) == 10 and value[4] == "-" and value[7] == "-":
                parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            result[field] = parsed
    if result.get("date_from") and result.get("date_to") and result["date_from"] > result["date_to"]:
        raise ValueError("Початок періоду пізніше кінця")
    sort_by = raw.get("sort_by", "newest")
    if sort_by not in ("newest", "oldest"):
        raise ValueError("Невідоме сортування")
    result["sort_by"] = sort_by
    return result


def format_activity_details(details: dict[str, Any] | None) -> str:
    return json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True) if details is not None else "Немає додаткових даних"


class ActivityLogView(ctk.CTkFrame):
    PAGE_SIZE = 25
    POLL_MS = 50
    COLUMNS = ("ID", "Дата й час", "Користувач", "Дія", "Тип об'єкта", "ID об'єкта")

    def __init__(self, master, api_client: APIClient, user_role: str = "worker", **kwargs: Any) -> None:
        if user_role not in ("admin", "worker"):
            raise ValueError("Unsupported role")
        super().__init__(master, **kwargs)
        self.user_role = user_role
        self.service = UserActivityLogClientService(api_client)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="activity-log-gui")
        self._future: Future | None = None
        self._poll_job = None
        self._closed = False
        self._requested_page = 1
        self._requested_size = self.PAGE_SIZE
        self.current_page = 1
        self._has_next = False
        self._items: dict[int, dict[str, Any]] = {}
        self._filters: dict[str, Any] = {"sort_by": "newest"}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        filters = ctk.CTkFrame(self)
        filters.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self.entries: dict[str, ctk.CTkEntry] = {}
        fields = [("action", "Дія"), ("entity_type", "Тип об'єкта"),
                  ("entity_id", "ID об'єкта"), ("date_from", "Від: РРРР-ММ-ДД"),
                  ("date_to", "До: РРРР-ММ-ДД")]
        if user_role == "admin":
            fields.insert(0, ("actor_id", "ID користувача"))
        for index, (key, label) in enumerate(fields):
            entry = ctk.CTkEntry(filters, placeholder_text=label, width=145)
            entry.grid(row=index // 3, column=index % 3, padx=5, pady=5, sticky="ew")
            self.entries[key] = entry
        self.sort_menu = ctk.CTkOptionMenu(filters, values=["newest", "oldest"], width=110)
        self.sort_menu.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.apply_button = ctk.CTkButton(filters, text="Застосувати", width=115, command=self.apply_filters)
        self.apply_button.grid(row=2, column=1, padx=5, pady=5)
        self.reset_button = ctk.CTkButton(filters, text="Очистити", width=105, command=self.reset_filters)
        self.reset_button.grid(row=2, column=2, padx=5, pady=5)

        controls = ctk.CTkFrame(self)
        controls.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        controls.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(controls, text="Завантаження...", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=8)
        self.id_entry = ctk.CTkEntry(controls, placeholder_text="ID події", width=100)
        self.id_entry.grid(row=0, column=1, padx=5)
        self.details_button = ctk.CTkButton(controls, text="Деталі", width=90, command=self.show_details)
        self.details_button.grid(row=0, column=2, padx=5)
        self.refresh_button = ctk.CTkButton(controls, text="Оновити", width=90, command=self.refresh)
        self.refresh_button.grid(row=0, column=3, padx=5)
        self.table = DataTable(self, columns=self.COLUMNS, empty_message="Подій немає",
                               page_size=self.PAGE_SIZE, pagination_mode="server",
                               on_page_change=self.load_page, on_page_size_change=self.change_page_size)
        self.table.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 10))
        self.refresh()

    def _busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.table.set_pagination_loading(busy)
        for button in (self.apply_button, self.reset_button, self.refresh_button, self.details_button):
            button.configure(state=state)

    def _fetch(self, offset: int, size: int, filters: dict[str, Any]):
        # API limit <= 100. One look-ahead record determines whether Next is enabled.
        if size == 100:
            rows = self.service.list_activity_logs(offset=offset, limit=100, **filters)
            if len(rows) == 100:
                rows += self.service.list_activity_logs(offset=offset + 100, limit=1, **filters)
            return rows
        return self.service.list_activity_logs(offset=offset, limit=size + 1, **filters)

    def load_page(self, page: int) -> None:
        if type(page) is not int or page < 1:
            raise ValueError("Invalid page")
        if self._closed or self._future is not None:
            return
        self._requested_page = page
        self._busy(True)
        self.status_label.configure(text="Завантаження подій...")
        try:
            self._future = self._executor.submit(self._fetch, (page - 1) * self._requested_size,
                                                  self._requested_size, dict(self._filters))
        except RuntimeError:
            self._busy(False)
            self.status_label.configure(text="Не вдалося запустити запит")
            return
        self._poll_job = self.after(self.POLL_MS, self._check_result)

    def change_page_size(self, size: int) -> None:
        if type(size) is not int or size not in DataTable.PAGE_SIZE_OPTIONS:
            raise ValueError("Invalid page size")
        if self._closed or self._future is not None or size == self.table.page_size:
            return
        self._requested_size = size
        self.load_page(1)

    def refresh(self) -> None:
        self.load_page(self.current_page)

    def apply_filters(self) -> None:
        if self._closed or self._future is not None:
            return
        raw = {key: entry.get() for key, entry in self.entries.items()}
        raw["sort_by"] = self.sort_menu.get()
        try:
            filters = parse_activity_filters(raw, self.user_role)
        except ValueError as exc:
            self.status_label.configure(text=str(exc))
            return
        self._filters = filters
        self.load_page(1)

    def reset_filters(self) -> None:
        if self._closed or self._future is not None:
            return
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.sort_menu.set("newest")
        self._filters = {"sort_by": "newest"}
        self.load_page(1)

    def _check_result(self) -> None:
        self._poll_job = None
        if self._closed or self._future is None:
            return
        if not self._future.done():
            self._poll_job = self.after(self.POLL_MS, self._check_result)
            return
        future = self._future
        self._future = None
        fallback = None
        try:
            result = future.result()
            page, size = self._requested_page, self._requested_size
            if not result and page > 1:
                fallback = page - 1
            else:
                self.current_page = page
                self._items = {row["id"]: row for row in result[:size]}
                self._has_next = len(result) > size
                self.table.page_size = size
                self.table.page_size_selector.set(str(size))
                rows = [(r["id"], r["created_at"].replace("T", " "),
                         r["actor_id"] if r["actor_id"] is not None else "—",
                         r["action"], r["entity_type"] or "—",
                         r["entity_id"] if r["entity_id"] is not None else "—")
                        for r in self._items.values()]
                self.table.set_server_page(rows, page=page, has_next_page=self._has_next)
                self.status_label.configure(text=f"Сторінка {page}. Подій: {len(rows)}")
        except Exception as exc:
            self.status_label.configure(text=format_gui_error(exc))
            self._requested_size = self.table.page_size
            self.table.page_size_selector.set(str(self.table.page_size))
        finally:
            self._busy(False)
        if fallback is not None:
            self.load_page(fallback)

    def show_details(self) -> None:
        if self._closed or self._future is not None:
            return
        try:
            event_id = int(self.id_entry.get().strip())
            record = self._items[event_id]
        except (ValueError, KeyError):
            self.status_label.configure(text="Вкажіть ID події з поточної сторінки")
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Подія #{event_id}")
        dialog.geometry("650x480")
        dialog.transient(self.winfo_toplevel())
        info = ctk.CTkTextbox(dialog, wrap="word")
        info.pack(fill="both", expand=True, padx=14, pady=14)
        info.insert("1.0", json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
        info.configure(state="disabled")
        ctk.CTkButton(dialog, text="Закрити", command=dialog.destroy).pack(pady=(0, 12))

    def destroy(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except (ValueError, RuntimeError):
                pass
            self._poll_job = None
        if self._future is not None:
            self._future.cancel()
            self._future = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
