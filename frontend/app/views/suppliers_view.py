"""Suppliers management screen (Tk operations on main thread only)."""
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk
from frontend.app.core.gui_errors import format_gui_error

from frontend.app.api.client import APIClient, APIClientError, APIRequestError
from frontend.app.components.data_table import DataTable
from frontend.app.components.page_header import PageHeader
from frontend.app.services.supplier_service import SupplierService, SupplierServiceError


class SuppliersView(ctk.CTkFrame):
    POLL_INTERVAL_MS = 50
    PAGE_SIZE = 25
    COLUMNS = ("ID", "Назва", "Контактна особа", "Телефон", "Email", "Адреса")

    def __init__(self, master, api_client: APIClient, user_role: str = "worker", **kwargs: Any) -> None:
        if user_role not in ("admin", "worker"):
            raise ValueError("Unsupported role")
        super().__init__(master, **kwargs)
        self.service = SupplierService(api_client)
        self.user_role = user_role
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warehouse-suppliers")
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False
        self._operation = "list"
        self._requested_page = 1
        self._requested_page_size = self.PAGE_SIZE
        self.current_page = 1
        self._suppliers: dict[int, dict[str, Any]] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        header = PageHeader(self, title="Постачальники", description="Перегляд та управління постачальниками")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(toolbar, text="Очікування завантаження", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        self.refresh_button = ctk.CTkButton(toolbar, text="Оновити", width=110, command=self.refresh)
        self.refresh_button.grid(row=0, column=1, padx=12, pady=10)
        self.table = DataTable(
            self, columns=self.COLUMNS, empty_message="Постачальників не знайдено",
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
            self.create_button = ctk.CTkButton(actions, text="Створити", width=95, command=self.create_supplier)
            self.create_button.pack(side="left", padx=5)
            self.edit_button = ctk.CTkButton(actions, text="Редагувати", width=100, command=self.edit_supplier)
            self.edit_button.pack(side="left", padx=5)
            self.delete_button = ctk.CTkButton(actions, text="Видалити", width=95, fg_color="#A83232", command=self.delete_supplier)
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
        items = self.service.list_suppliers(offset, page_size)
        if page_size == 100 and len(items) == 100:
            items += self.service.list_suppliers(offset + 100, 1)
        return items

    def _load(self, page: int) -> None:
        size = self._requested_page_size
        offset = (page - 1) * size
        if size == 100:
            self._submit("list", self._fetch_page, offset, size)
        else:
            self._submit("list", self.service.list_suppliers, offset, size + 1)

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
                    self._suppliers = {item["id"]: item for item in visible}
                    self.table.page_size = size
                    self.table.page_size_selector.set(str(size))
                    rows = [tuple(item[key] or "" for key in ("id", "name", "contact_person", "phone", "email", "address")) for item in visible]
                    self.table.set_server_page(rows, page=page, has_next_page=len(result) > size)
                    self.current_page = page
                    self.status_label.configure(text=f"Сторінка {page}. Постачальників: {len(visible)}")
            else:
                self.status_label.configure(text="Операцію виконано успішно")
                reload_after = True
        except APIRequestError as exc:
            self.status_label.configure(text=format_gui_error(exc))
        except (APIClientError, SupplierServiceError, ValueError) as exc:
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
            supplier_id = int(self.id_entry.get().strip())
            if supplier_id < 1:
                raise ValueError
        except ValueError:
            self.status_label.configure(text="Вкажіть коректний додатний ID постачальника")
            return None
        return supplier_id

    def _editor(self, supplier: dict[str, Any] | None = None) -> None:
        if self._future is not None:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Редагування постачальника" if supplier else "Новий постачальник")
        dialog.geometry("540x520")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        labels = (
            ("name", "Назва * (до 150 символів)"),
            ("contact_person", "Контактна особа (до 150 символів)"),
            ("phone", "Телефон (до 30 символів)"),
            ("email", "Email"),
            ("address", "Адреса"),
        )
        entries = {}
        for key, label in labels:
            ctk.CTkLabel(dialog, text=label).pack(pady=(9, 0))
            entry = ctk.CTkEntry(dialog, width=450)
            entry.pack(pady=2)
            if supplier and supplier.get(key):
                entry.insert(0, supplier[key])
            entries[key] = entry
        feedback = ctk.CTkLabel(dialog, text="")
        feedback.pack(pady=5)

        def save() -> None:
            values = {key: entry.get().strip() or None for key, entry in entries.items()}
            try:
                payload = {key: self.service._field(key, value) for key, value in values.items()}
            except ValueError as exc:
                feedback.configure(text=str(exc))
                return
            if supplier:
                # Explicit None clears optional fields in PATCH.
                func = lambda: self.service.update_supplier(supplier["id"], **payload)
            else:
                func = lambda: self.service.create_supplier(**payload)
            if self._submit("update" if supplier else "create", func):
                dialog.grab_release()
                dialog.destroy()

        ctk.CTkButton(dialog, text="Зберегти", command=save).pack(pady=8)
        entries["name"].focus_set()

    def create_supplier(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify suppliers")
        self._editor()

    def edit_supplier(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify suppliers")
        supplier_id = self._selected_id()
        if supplier_id is None:
            return
        supplier = self._suppliers.get(supplier_id)
        if supplier is None:
            self.status_label.configure(text="Для редагування вкажіть ID із поточної сторінки")
            return
        self._editor(supplier)

    def delete_supplier(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify suppliers")
        supplier_id = self._selected_id()
        if supplier_id is None:
            return
        supplier = self._suppliers.get(supplier_id)
        if supplier is None:
            self.status_label.configure(text="Для видалення вкажіть ID із поточної сторінки")
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Підтвердження видалення")
        dialog.geometry("420x170")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Видалити постачальника «{supplier['name']}» (ID {supplier_id})?", wraplength=380).pack(pady=20)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(pady=8)
        ctk.CTkButton(buttons, text="Скасувати", command=dialog.destroy).pack(side="left", padx=8)

        def confirm() -> None:
            if self._submit("delete", self.service.delete_supplier, supplier_id):
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
