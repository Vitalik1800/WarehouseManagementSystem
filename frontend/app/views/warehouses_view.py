"""Warehouse management GUI. All Tk operations stay on the main thread."""
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any
import customtkinter as ctk
from frontend.app.api.client import APIClient
from frontend.app.components.data_table import DataTable
from frontend.app.core.gui_errors import format_gui_error
from frontend.app.services.warehouse_service import WarehouseClientService

class WarehousesView(ctk.CTkFrame):
    PAGE_SIZE = 25
    POLL_MS = 50
    COLUMNS = ("ID", "Назва", "Код", "Статус", "Опис")

    def __init__(self, master, api_client: APIClient, user_role: str = "worker", **kwargs: Any) -> None:
        if user_role not in ("admin", "worker"):
            raise ValueError("Unsupported role")
        super().__init__(master, **kwargs)
        self.user_role = user_role
        self.service = WarehouseClientService(api_client)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warehouse-gui")
        self._future: Future | None = None
        self._poll_job = None
        self._closed = False
        self._operation = "list"
        self._requested_page = 1
        self._requested_size = self.PAGE_SIZE
        self.current_page = 1
        self._items: dict[int, dict[str, Any]] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        bar.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(bar, text="Завантаження...", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=8)
        self.search_entry = ctk.CTkEntry(bar, placeholder_text="Пошук на сторінці", width=190)
        self.search_entry.grid(row=0, column=1, padx=5)
        self.search_entry.bind("<KeyRelease>", self._filter)
        self.refresh_button = ctk.CTkButton(bar, text="Оновити", width=95, command=self.refresh)
        self.refresh_button.grid(row=0, column=2, padx=8)
        self.table = DataTable(self, columns=self.COLUMNS, empty_message="Складів немає", page_size=self.PAGE_SIZE, pagination_mode="server", on_page_change=self.load_page, on_page_size_change=self.change_page_size)
        self.table.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        if user_role == "admin":
            actions = ctk.CTkFrame(self)
            actions.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
            self.id_entry = ctk.CTkEntry(actions, width=90, placeholder_text="ID")
            self.id_entry.pack(side="left", padx=8)
            self.create_button = ctk.CTkButton(actions, text="Створити", command=self.create_warehouse, width=100)
            self.create_button.pack(side="left", padx=5)
            self.edit_button = ctk.CTkButton(actions, text="Редагувати", command=self.edit_warehouse, width=110)
            self.edit_button.pack(side="left", padx=5)
            self.delete_button = ctk.CTkButton(actions, text="Видалити", command=self.delete_warehouse, width=100, fg_color="#A83232")
            self.delete_button.pack(side="left", padx=5)
        self.refresh()

    def _busy(self, busy: bool) -> None:
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
        self._busy(True)
        self.status_label.configure(text="Виконується запит...")
        try:
            self._future = self._executor.submit(func, *args)
        except RuntimeError:
            self._future = None
            self._busy(False)
            self.status_label.configure(text="Не вдалося запустити запит")
            return False
        self._poll_job = self.after(self.POLL_MS, self._check_result)
        return True

    def _fetch(self, offset: int, size: int):
        if size == 100:
            rows = self.service.list_warehouses(offset, 100)
            if len(rows) == 100:
                rows += self.service.list_warehouses(offset + 100, 1)
            return rows
        return self.service.list_warehouses(offset, size + 1)

    def load_page(self, page: int) -> None:
        if type(page) is not int or page < 1:
            raise ValueError("Invalid page")
        if self._closed or self._future is not None:
            return
        self._requested_page = page
        self._submit("list", self._fetch, (page - 1) * self._requested_size, self._requested_size)

    def change_page_size(self, size: int) -> None:
        if type(size) is not int or size not in DataTable.PAGE_SIZE_OPTIONS:
            raise ValueError("Invalid page size")
        if self._closed or self._future is not None or size == self.table.page_size:
            return
        self._requested_size = size
        self.load_page(1)

    def refresh(self) -> None:
        self.load_page(self.current_page)

    def _display(self) -> None:
        term = self.search_entry.get().strip().casefold()
        rows = [row for row in self._items.values() if term in row['name'].casefold() or term in row['code'].casefold() or term in (row['description'] or '').casefold()]
        table_rows = [(r['id'], r['name'], r['code'], "Активний" if r['is_active'] else "Неактивний", r['description'] or "") for r in rows]
        self.table.set_server_page(table_rows, page=self.current_page, has_next_page=self._has_next)

    def _filter(self, _event=None) -> None:
        if hasattr(self, '_has_next'):
            self._display()

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
        reload = False
        try:
            result = future.result()
            if self._operation == "list":
                page, size = self._requested_page, self._requested_size
                if not result and page > 1:
                    fallback = page - 1
                else:
                    self.current_page = page
                    self._items = {r['id']: r for r in result[:size]}
                    self._has_next = len(result) > size
                    self.table.page_size = size
                    self.table.page_size_selector.set(str(size))
                    self._display()
                    self.status_label.configure(text=f"Сторінка {page}. Складів: {len(self._items)}")
            else:
                self.status_label.configure(text="Операцію виконано")
                reload = True
        except Exception as exc:
            self.status_label.configure(text=format_gui_error(exc))
            if self._operation == "list":
                self._requested_size = self.table.page_size
                self.table.page_size_selector.set(str(self.table.page_size))
        finally:
            self._busy(False)
        if fallback is not None:
            self.load_page(fallback)
        elif reload:
            self.refresh()

    def _selected(self):
        try:
            value = int(self.id_entry.get().strip())
            if value < 1:
                raise ValueError
            return self._items[value]
        except (ValueError, KeyError):
            self.status_label.configure(text="Укажіть ID складу з поточної сторінки")
            return None

    def _editor(self, warehouse=None) -> None:
        if self._future is not None:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Редагування складу" if warehouse else "Новий склад")
        dialog.geometry("460x420")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        entries = {}
        for field, label, length in (("name", "Назва", 100), ("code", "Код", 30), ("description", "Опис", 500)):
            ctk.CTkLabel(dialog, text=label).pack(pady=(9, 1))
            entry = ctk.CTkEntry(dialog, width=390)
            entry.pack(pady=3)
            if warehouse:
                entry.insert(0, warehouse[field] or "")
            entries[field] = entry
        active_var = ctk.BooleanVar(value=warehouse['is_active'] if warehouse else True)
        ctk.CTkCheckBox(dialog, text="Активний", variable=active_var).pack(pady=12)
        feedback = ctk.CTkLabel(dialog, text="")
        feedback.pack()
        def save():
            name, code = entries['name'].get().strip(), entries['code'].get().strip()
            if not 1 <= len(name) <= 100 or not 1 <= len(code) <= 30:
                feedback.configure(text="Перевірте назву (1–100) та код (1–30)")
                return
            description = entries['description'].get().strip() or None
            args = (name, code, description, active_var.get())
            if warehouse:
                ok = self._submit("update", self.service.update_warehouse, warehouse['id'], *args)
            else:
                ok = self._submit("create", self.service.create_warehouse, *args)
            if ok:
                dialog.grab_release()
                dialog.destroy()
        ctk.CTkButton(dialog, text="Зберегти", command=save).pack(pady=12)
        entries['name'].focus_set()

    def create_warehouse(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify warehouses")
        self._editor()

    def edit_warehouse(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify warehouses")
        warehouse = self._selected()
        if warehouse:
            self._editor(warehouse)

    def delete_warehouse(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify warehouses")
        warehouse = self._selected()
        if not warehouse:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Підтвердження видалення")
        dialog.geometry("430x170")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Видалити склад «{warehouse['name']}» (ID {warehouse['id']})?", wraplength=390).pack(pady=20)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(pady=8)
        ctk.CTkButton(buttons, text="Скасувати", command=dialog.destroy).pack(side="left", padx=8)
        def confirm():
            if self._submit("delete", self.service.delete_warehouse, warehouse['id']):
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
