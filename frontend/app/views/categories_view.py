"""Categories management screen (Tk operations on main thread only)."""
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk
from frontend.app.core.gui_errors import format_gui_error

from frontend.app.api.client import APIClient, APIClientError, APIRequestError
from frontend.app.components.data_table import DataTable
from frontend.app.components.page_header import PageHeader
from frontend.app.services.category_service import CategoryService, CategoryServiceError


class CategoriesView(ctk.CTkFrame):
    POLL_INTERVAL_MS = 50
    PAGE_SIZE = 25
    COLUMNS = ("ID", "Назва", "Опис")

    def __init__(self, master, api_client: APIClient, user_role: str = "worker", **kwargs: Any) -> None:
        if user_role not in ("admin", "worker"):
            raise ValueError("Unsupported role")
        super().__init__(master, **kwargs)
        self.service = CategoryService(api_client)
        self.user_role = user_role
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warehouse-categories")
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False
        self._operation = "list"
        self._requested_page = 1
        self._requested_page_size = self.PAGE_SIZE
        self.current_page = 1
        self._categories: dict[int, dict[str, Any]] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        header = PageHeader(self, title="Категорії товарів", description="Перегляд та управління категоріями")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(toolbar, text="Очікування завантаження", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        self.refresh_button = ctk.CTkButton(toolbar, text="Оновити", width=110, command=self.refresh)
        self.refresh_button.grid(row=0, column=1, padx=12, pady=10)
        self.table = DataTable(
            self, columns=self.COLUMNS, empty_message="Категорій не знайдено",
            page_size=self.PAGE_SIZE, pagination_mode="server",
            on_page_change=self.load_page, on_page_size_change=self.change_page_size,
        )
        self.table.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        if self.user_role == "admin":
            actions = ctk.CTkFrame(self)
            actions.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
            ctk.CTkLabel(actions, text="ID для редагування/видалення:").pack(side="left", padx=8)
            self.id_entry = ctk.CTkEntry(actions, width=85, placeholder_text="ID")
            self.id_entry.pack(side="left", padx=5)
            self.create_button = ctk.CTkButton(actions, text="Створити", width=95, command=self.create_category)
            self.create_button.pack(side="left", padx=5)
            self.edit_button = ctk.CTkButton(actions, text="Редагувати", width=100, command=self.edit_category)
            self.edit_button.pack(side="left", padx=5)
            self.delete_button = ctk.CTkButton(actions, text="Видалити", width=95, fg_color="#A83232", command=self.delete_category)
            self.delete_button.pack(side="left", padx=5)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.table.set_pagination_loading(busy)
        self.refresh_button.configure(state=state)
        if self.user_role == "admin":
            for button in (self.create_button, self.edit_button, self.delete_button):
                button.configure(state=state)

    def _submit(self, operation: str, func, *args) -> bool:
        if self._closed or self._future is not None:
            return False
        self._operation = operation
        self._set_busy(True)
        self.status_label.configure(text="Виконується запит...")
        try:
            self._future = self._executor.submit(func, *args)
        except RuntimeError:
            self._future = None
            self._requested_page_size = self.table.page_size
            self.table.page_size_selector.set(str(self.table.page_size))
            self._set_busy(False)
            self.status_label.configure(text="Не вдалося запустити запит")
            return False
        self._poll_job = self.after(self.POLL_INTERVAL_MS, self._check_result)
        return True

    def _fetch_page(self, offset: int, page_size: int) -> list[dict[str, Any]]:
        items = self.service.list_categories(offset, page_size)
        if page_size == 100 and len(items) == 100:
            items += self.service.list_categories(offset + 100, 1)
        return items

    def _load(self, page: int) -> None:
        size = self._requested_page_size
        offset = (page - 1) * size
        if size == 100:
            self._submit("list", self._fetch_page, offset, size)
        else:
            self._submit("list", self.service.list_categories, offset, size + 1)

    def load_page(self, page: int) -> None:
        if type(page) is not int or page < 1:
            raise ValueError("Page must be positive")
        if self._closed or self._future is not None:
            return
        self._requested_page = page
        self._load(page)

    def change_page_size(self, size: int) -> None:
        if type(size) is not int or size not in DataTable.PAGE_SIZE_OPTIONS:
            raise ValueError("Unsupported page size")
        if self._closed or self._future is not None:
            return
        if size == self.table.page_size:
            return
        self._requested_page_size = size
        self._requested_page = 1
        self._load(1)

    def refresh(self) -> None:
        self.load_page(self.current_page)

    def _check_result(self) -> None:
        self._poll_job = None
        if self._closed or self._future is None:
            return
        if not self._future.done():
            self._poll_job = self.after(self.POLL_INTERVAL_MS, self._check_result)
            return
        future = self._future
        self._future = None
        fallback = None
        reload_after = False
        try:
            result = future.result()
            if self._operation == "list":
                page = self._requested_page
                if not result and page > 1:
                    fallback = page - 1
                else:
                    size = self._requested_page_size
                    visible = result[:size]
                    self._categories = {item["id"]: item for item in visible}
                    self.table.page_size = size
                    self.table.page_size_selector.set(str(size))
                    rows = [(item["id"], item["name"], item["description"] or "") for item in visible]
                    self.table.set_server_page(rows, page=page, has_next_page=len(result) > size)
                    self.current_page = page
                    self.status_label.configure(text=f"Сторінка {page}. Категорій: {len(visible)}")
            else:
                self.status_label.configure(text="Операцію виконано успішно")
                reload_after = True
        except APIRequestError as exc:
            self.status_label.configure(text=format_gui_error(exc))
        except (APIClientError, CategoryServiceError, ValueError) as exc:
            self.status_label.configure(text=format_gui_error(exc))
        except Exception as exc:
            self.status_label.configure(text=format_gui_error(exc))
        finally:
            if fallback is None and self._operation == "list" and self.table.page_size != self._requested_page_size:
                self._requested_page_size = self.table.page_size
                self.table.page_size_selector.set(str(self.table.page_size))
            self._set_busy(False)
        if fallback is not None:
            self.load_page(fallback)
        elif reload_after:
            self.load_page(self.current_page)

    def _selected_id(self) -> int | None:
        try:
            category_id = int(self.id_entry.get().strip())
            if category_id < 1:
                raise ValueError
        except ValueError:
            self.status_label.configure(text="Вкажіть коректний додатний ID категорії")
            return None
        return category_id

    def _editor(self, category: dict[str, Any] | None = None) -> None:
        if self._future is not None:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Редагування категорії" if category else "Нова категорія")
        dialog.geometry("450x290")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Назва (до 100 символів)").pack(pady=(14, 2))
        name_entry = ctk.CTkEntry(dialog, width=380)
        name_entry.pack(pady=4)
        ctk.CTkLabel(dialog, text="Опис (необов'язковий)").pack(pady=(8, 2))
        desc_entry = ctk.CTkEntry(dialog, width=380)
        desc_entry.pack(pady=4)
        if category:
            name_entry.insert(0, category["name"])
            desc_entry.insert(0, category["description"] or "")
        feedback = ctk.CTkLabel(dialog, text="")
        feedback.pack(pady=5)

        def save() -> None:
            name = name_entry.get().strip()
            if not 1 <= len(name) <= 100:
                feedback.configure(text="Назва повинна містити 1–100 символів")
                return
            description = desc_entry.get().strip() or None
            if category:
                success = self._submit("update", self.service.update_category, category["id"], name, description)
            else:
                success = self._submit("create", self.service.create_category, name, description)
            if success:
                dialog.grab_release()
                dialog.destroy()

        ctk.CTkButton(dialog, text="Зберегти", command=save).pack(pady=8)
        name_entry.focus_set()

    def create_category(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify categories")
        self._editor()

    def edit_category(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify categories")
        category_id = self._selected_id()
        if category_id is None:
            return
        category = self._categories.get(category_id)
        if category is None:
            self.status_label.configure(text="Для редагування вкажіть ID із поточної сторінки")
            return
        self._editor(category)

    def delete_category(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify categories")
        category_id = self._selected_id()
        if category_id is None:
            return
        category = self._categories.get(category_id)
        if category is None:
            self.status_label.configure(text="Для видалення вкажіть ID із поточної сторінки")
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Підтвердження видалення")
        dialog.geometry("420x170")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Видалити категорію «{category['name']}» (ID {category_id})?", wraplength=380).pack(pady=20)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(pady=8)
        ctk.CTkButton(buttons, text="Скасувати", command=dialog.destroy).pack(side="left", padx=8)

        def confirm() -> None:
            if self._submit("delete", self.service.delete_category, category_id):
                dialog.grab_release()
                dialog.destroy()

        ctk.CTkButton(buttons, text="Видалити", fg_color="#A83232", command=confirm).pack(side="left", padx=8)

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
