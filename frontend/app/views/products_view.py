"""Products management screen (Tk operations on main thread only)."""
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk
from frontend.app.core.gui_errors import format_gui_error

from frontend.app.api.client import APIClient, APIClientError, APIRequestError
from frontend.app.components.data_table import DataTable
from frontend.app.components.page_header import PageHeader
from frontend.app.services.product_service import ProductService, ProductServiceError
from frontend.app.services.category_service import CategoryService
from frontend.app.services.storage_location_service import StorageLocationClientService


class ProductsView(ctk.CTkFrame):
    POLL_INTERVAL_MS = 50
    PAGE_SIZE = 25
    COLUMNS = ("ID", "SKU", "Назва", "Од.", "Кількість", "Категорія", "Локація", "Опис")

    def __init__(self, master, api_client: APIClient, user_role: str = "worker", **kwargs: Any) -> None:
        if user_role not in ("admin", "worker"):
            raise ValueError("Unsupported role")
        super().__init__(master, **kwargs)
        self.service = ProductService(api_client)
        self.category_service = CategoryService(api_client)
        self.location_service = StorageLocationClientService(api_client)
        self.user_role = user_role
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warehouse-products")
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._closed = False
        self._operation = "list"
        self._requested_page = 1
        self._requested_page_size = self.PAGE_SIZE
        self.current_page = 1
        self._products: dict[int, dict[str, Any]] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        header = PageHeader(self, title="Товари", description="Перегляд та управління товарами")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(toolbar, text="Очікування завантаження", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        self.refresh_button = ctk.CTkButton(toolbar, text="Оновити", width=110, command=self.refresh)
        self.refresh_button.grid(row=0, column=1, padx=12, pady=10)
        filters = ctk.CTkFrame(toolbar, fg_color="transparent")
        filters.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
        self.search_entry = ctk.CTkEntry(filters, width=170, placeholder_text="Пошук за назвою")
        self.search_entry.pack(side="left", padx=4)
        self.sku_entry = ctk.CTkEntry(filters, width=140, placeholder_text="SKU")
        self.sku_entry.pack(side="left", padx=4)
        self.category_entry = ctk.CTkEntry(filters, width=110, placeholder_text="ID категорії")
        self.category_entry.pack(side="left", padx=4)
        self.location_entry = ctk.CTkEntry(filters, width=110, placeholder_text="ID локації")
        self.location_entry.pack(side="left", padx=4)
        ctk.CTkButton(filters, text="Знайти", width=80, command=self.apply_filters).pack(side="left", padx=4)
        self._filters = {}
        self.table = DataTable(
            self, columns=self.COLUMNS, empty_message="Товарів не знайдено",
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
            self.create_button = ctk.CTkButton(actions, text="Створити", width=95, command=self.create_product)
            self.create_button.pack(side="left", padx=5)
            self.edit_button = ctk.CTkButton(actions, text="Редагувати", width=100, command=self.edit_product)
            self.edit_button.pack(side="left", padx=5)
            self.delete_button = ctk.CTkButton(actions, text="Видалити", width=95, fg_color="#A83232", command=self.delete_product)
            self.delete_button.pack(side="left", padx=5)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.table.set_pagination_loading(busy)
        self.refresh_button.configure(state=state)
        if self.user_role == "admin":
            for button in (self.create_button, self.edit_button, self.delete_button):
                button.configure(state=state)

    def _submit(self, operation: str, func, *args, **kwargs) -> bool:
        if self._closed or self._future is not None:
            return False
        self._operation = operation
        self._set_busy(True)
        self.status_label.configure(text="Виконується запит...")
        try:
            self._future = self._executor.submit(func, *args, **kwargs)
        except RuntimeError:
            self._future = None
            self._requested_page_size = self.table.page_size
            self.table.page_size_selector.set(str(self.table.page_size))
            self._set_busy(False)
            self.status_label.configure(text="Не вдалося запустити запит")
            return False
        self._poll_job = self.after(self.POLL_INTERVAL_MS, self._check_result)
        return True

    def _fetch_page(self, offset: int, page_size: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        items = self.service.list_products(offset, page_size, **filters)
        if page_size == 100 and len(items) == 100:
            items += self.service.list_products(offset + 100, 1, **filters)
        return items

    def _load(self, page: int) -> None:
        size = self._requested_page_size
        offset = (page - 1) * size
        if size == 100:
            self._submit("list", self._fetch_page, offset, size, self._filters.copy())
        else:
            self._submit("list", self.service.list_products, offset, size + 1, **self._filters)

    def apply_filters(self) -> None:
        if self._closed or self._future is not None:
            return
        filters: dict[str, Any] = {}
        for key, entry in (("search", self.search_entry), ("sku", self.sku_entry)):
            if entry.get().strip():
                filters[key] = entry.get().strip()
        for key, entry in (("category_id", self.category_entry), ("location_id", self.location_entry)):
            value = entry.get().strip()
            if value:
                try:
                    number = int(value)
                    if number < 1:
                        raise ValueError
                except ValueError:
                    self.status_label.configure(text=f"Некоректний {key}: потрібен додатний ID")
                    return
                filters[key] = number
        self._filters = filters
        self._requested_page = 1
        self.load_page(1)

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
                    self._products = {item["id"]: item for item in visible}
                    self.table.page_size = size
                    self.table.page_size_selector.set(str(size))
                    rows = [tuple(str(item[key]) if item[key] is not None else "" for key in ("id", "sku", "name", "unit", "quantity", "category_id", "location_id", "description")) for item in visible]
                    self.table.set_server_page(rows, page=page, has_next_page=len(result) > size)
                    self.current_page = page
                    self.status_label.configure(text=f"Сторінка {page}. Товарів: {len(visible)}")
            else:
                self.status_label.configure(text="Операцію виконано успішно")
                reload_after = True
        except APIRequestError as exc:
            self.status_label.configure(text=format_gui_error(exc))
        except (APIClientError, ProductServiceError, ValueError) as exc:
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
            product_id = int(self.id_entry.get().strip())
            if product_id < 1:
                raise ValueError
        except ValueError:
            self.status_label.configure(text="Вкажіть коректний додатний ID товару")
            return None
        return product_id

    @staticmethod
    def _all_references(service, method_name: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = getattr(service, method_name)(offset=offset, limit=100)
            items.extend(page)
            if len(page) < 100:
                return items
            offset += 100
            if offset > 100000:
                raise ValueError("Забагато довідникових записів")

    def _editor(self, product: dict[str, Any] | None = None) -> None:
        if self._future is not None:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Редагування товару" if product else "Новий товар")
        dialog.geometry("600x660")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        entries: dict[str, Any] = {}
        for key, label in (
            ("sku", "SKU * (до 64 символів)"),
            ("name", "Назва * (до 200 символів)"),
            ("unit", "Одиниця * (до 20 символів)"),
            ("description", "Опис (необов'язковий)"),
        ):
            ctk.CTkLabel(dialog, text=label).pack(pady=(7, 0))
            entry = ctk.CTkEntry(dialog, width=480)
            entry.pack(pady=2)
            initial = product.get(key) if product else ("pcs" if key == "unit" else "")
            if initial is not None:
                entry.insert(0, str(initial))
            entries[key] = entry
        ctk.CTkLabel(dialog, text="Категорія *").pack(pady=(8, 0))
        category_menu = ctk.CTkOptionMenu(dialog, width=480, values=["Завантаження..."])
        category_menu.pack(pady=3)
        ctk.CTkLabel(dialog, text="Місце зберігання *").pack(pady=(8, 0))
        location_menu = ctk.CTkOptionMenu(dialog, width=480, values=["Завантаження..."])
        location_menu.pack(pady=3)
        feedback = ctk.CTkLabel(dialog, text="Завантаження довідників...", wraplength=530)
        feedback.pack(pady=8)
        save_button = ctk.CTkButton(dialog, text="Зберегти", state="disabled")
        save_button.pack(pady=8)
        mappings: dict[str, dict[str, int]] = {"category_id": {}, "location_id": {}}
        ref_future = self._executor.submit(
            lambda: (
                self._all_references(self.category_service, "list_categories"),
                self._all_references(self.location_service, "list_locations"),
            )
        )
        poll_id = None
        def populate() -> None:
            nonlocal poll_id
            poll_id = None
            if self._closed or not dialog.winfo_exists():
                return
            if not ref_future.done():
                poll_id = dialog.after(self.POLL_INTERVAL_MS, populate)
                return
            try:
                categories, locations = ref_future.result()
                for key, rows, menu in (
                    ("category_id", categories, category_menu),
                    ("location_id", locations, location_menu),
                ):
                    names = {}
                    for row in rows:
                        display = f"{row['name']} (ID {row['id']})"
                        names[display] = row['id']
                    mappings[key] = names
                    if names:
                        menu.configure(values=list(names))
                        chosen = next((n for n, i in names.items() if product and i == product.get(key)), None)
                        menu.set(chosen or next(iter(names)))
                    else:
                        menu.configure(values=["Немає записів"])
                        menu.set("Немає записів")
                if not categories or not locations:
                    feedback.configure(text="Спочатку створіть категорію та місце зберігання у відповідних розділах")
                else:
                    feedback.configure(text="")
                    save_button.configure(state="normal")
            except Exception as exc:
                feedback.configure(text=f"Не вдалося завантажити довідники: {exc}")
        def save() -> None:
            values = {key: entry.get().strip() for key, entry in entries.items()}
            try:
                values["category_id"] = mappings["category_id"][category_menu.get()]
                values["location_id"] = mappings["location_id"][location_menu.get()]
                values["description"] = values["description"] or None
                payload = {key: self.service._field(key, value) for key, value in values.items()}
            except (ValueError, KeyError) as exc:
                feedback.configure(text=f"Некоректні дані: {exc}")
                return
            if product:
                func = lambda: self.service.update_product(product["id"], **payload)
            else:
                func = lambda: self.service.create_product(**payload)
            if self._submit("update" if product else "create", func):
                dialog.grab_release()
                dialog.destroy()
        save_button.configure(command=save)
        dialog.after(self.POLL_INTERVAL_MS, populate)
        entries["sku"].focus_set()

    def create_product(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify products")
        self._editor()

    def edit_product(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify products")
        product_id = self._selected_id()
        if product_id is None:
            return
        product = self._products.get(product_id)
        if product is None:
            self.status_label.configure(text="Для редагування вкажіть ID із поточної сторінки")
            return
        self._editor(product)

    def delete_product(self) -> None:
        if self.user_role != "admin":
            raise PermissionError("Only admin can modify products")
        product_id = self._selected_id()
        if product_id is None:
            return
        product = self._products.get(product_id)
        if product is None:
            self.status_label.configure(text="Для видалення вкажіть ID із поточної сторінки")
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Підтвердження видалення")
        dialog.geometry("420x170")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=f"Видалити товар «{product['name']}» (ID {product_id})?", wraplength=380).pack(pady=20)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(pady=8)
        ctk.CTkButton(buttons, text="Скасувати", command=dialog.destroy).pack(side="left", padx=8)

        def confirm() -> None:
            if self._submit("delete", self.service.delete_product, product_id):
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
