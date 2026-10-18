"""Stock receipts screen. All Tk operations run on the main thread."""
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import customtkinter as ctk

from frontend.app.api.client import APIClient
from frontend.app.core.gui_errors import format_gui_error
from frontend.app.services.product_service import ProductService
from frontend.app.services.supplier_service import SupplierService
from frontend.app.services.stock_movement_service import StockMovementService


class StockReceiptsView(ctk.CTkFrame):
    POLL_INTERVAL_MS = 50

    def __init__(self, master: Any, api_client: APIClient,
                 user_role: str = "worker", **kwargs: Any) -> None:
        if user_role not in ("admin", "worker"):
            raise ValueError("Unsupported role")
        super().__init__(master, **kwargs)
        self.product_service = ProductService(api_client)
        self.supplier_service = SupplierService(api_client)
        self.movement_service = StockMovementService(api_client)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warehouse-receipts")
        self._future: Future | None = None
        self._poll_job: str | None = None
        self._operation = "references"
        self._closed = False
        self._product_ids: dict[str, int] = {}
        self._supplier_ids: dict[str, int | None] = {"Без постачальника": None}
        self._build()
        self.load_references()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        panel = ctk.CTkFrame(self)
        panel.grid(row=0, column=0, sticky="new", padx=20, pady=20)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Надходження товару", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=(16, 8))
        ctk.CTkLabel(panel, text="Товар *").grid(row=1, column=0, pady=(6, 2))
        self.product_menu = ctk.CTkOptionMenu(panel, width=440, values=["Завантаження..."])
        self.product_menu.grid(row=2, column=0, pady=3)
        ctk.CTkLabel(panel, text="Кількість * (до 3 знаків після крапки)").grid(row=3, column=0, pady=(8, 2))
        self.quantity_entry = ctk.CTkEntry(panel, width=440, placeholder_text="Наприклад: 12.500")
        self.quantity_entry.grid(row=4, column=0, pady=3)
        ctk.CTkLabel(panel, text="Постачальник (необов'язково)").grid(row=5, column=0, pady=(8, 2))
        self.supplier_menu = ctk.CTkOptionMenu(panel, width=440, values=["Без постачальника"])
        self.supplier_menu.grid(row=6, column=0, pady=3)
        ctk.CTkLabel(panel, text="Примітка (необов'язково)").grid(row=7, column=0, pady=(8, 2))
        self.note_entry = ctk.CTkEntry(panel, width=440)
        self.note_entry.grid(row=8, column=0, pady=3)
        self.status_label = ctk.CTkLabel(panel, text="Завантаження довідників...", wraplength=440)
        self.status_label.grid(row=9, column=0, pady=(12, 4))
        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=10, column=0, pady=(6, 16))
        self.save_button = ctk.CTkButton(actions, text="Підтвердити надходження", state="disabled", command=self.create_receipt)
        self.save_button.pack(side="left", padx=5)
        self.refresh_button = ctk.CTkButton(actions, text="Оновити довідники", command=self.load_references)
        self.refresh_button.pack(side="left", padx=5)

    @staticmethod
    def _all_records(service: Any, method: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = getattr(service, method)(offset=offset, limit=100)
            result.extend(page)
            if len(page) < 100:
                return result
            offset += 100
            if offset > 100000:
                raise ValueError("Забагато записів у довіднику")

    def _set_busy(self, busy: bool) -> None:
        self.save_button.configure(state="disabled" if busy or not self._product_ids else "normal")
        self.refresh_button.configure(state="disabled" if busy else "normal")

    def _submit(self, operation: str, func: Any, *args: Any, **kwargs: Any) -> bool:
        if self._closed or self._future is not None:
            return False
        self._operation = operation
        self._set_busy(True)
        try:
            self._future = self._executor.submit(func, *args, **kwargs)
        except RuntimeError:
            self._set_busy(False)
            self.status_label.configure(text="Не вдалося запустити запит")
            return False
        self._poll_job = self.after(self.POLL_INTERVAL_MS, self._check_result)
        return True

    def load_references(self) -> None:
        if self._submit("references", lambda: (
            self._all_records(self.product_service, "list_products"),
            self._all_records(self.supplier_service, "list_suppliers"),
        )):
            self.status_label.configure(text="Завантаження товарів і постачальників...")

    @staticmethod
    def _build_payload(product_id: int, quantity: str, supplier_id: int | None,
                       note: str) -> dict[str, Any]:
        if type(product_id) is not int or product_id < 1:
            raise ValueError("Оберіть товар")
        if supplier_id is not None and (type(supplier_id) is not int or supplier_id < 1):
            raise ValueError("Некоректний постачальник")
        if not isinstance(quantity, str) or not quantity.strip():
            raise ValueError("Вкажіть кількість")
        return {"product_id": product_id, "quantity": quantity.strip(),
                "supplier_id": supplier_id, "note": note.strip() or None}

    def create_receipt(self) -> None:
        if self._closed or self._future is not None:
            return
        try:
            payload = self._build_payload(
                self._product_ids[self.product_menu.get()], self.quantity_entry.get(),
                self._supplier_ids[self.supplier_menu.get()], self.note_entry.get())
        except (ValueError, KeyError) as exc:
            self.status_label.configure(text=f"Перевірте дані: {exc}")
            return
        if self._submit("receipt", self.movement_service.create_receipt, **payload):
            self.status_label.configure(text="Збереження надходження...")

    def _check_result(self) -> None:
        self._poll_job = None
        if self._closed or self._future is None:
            return
        if not self._future.done():
            self._poll_job = self.after(self.POLL_INTERVAL_MS, self._check_result)
            return
        future = self._future
        self._future = None
        try:
            result = future.result()
            if self._operation == "references":
                products, suppliers = result
                self._product_ids = {f"{p['name']} ({p['sku']}, ID {p['id']})": p["id"] for p in products}
                self._supplier_ids = {"Без постачальника": None}
                self._supplier_ids.update({f"{s['name']} (ID {s['id']})": s["id"] for s in suppliers})
                product_names = list(self._product_ids)
                self.product_menu.configure(values=product_names or ["Немає товарів"])
                self.product_menu.set(product_names[0] if product_names else "Немає товарів")
                self.supplier_menu.configure(values=list(self._supplier_ids))
                self.supplier_menu.set("Без постачальника")
                self.status_label.configure(text="Готово до надходження" if products else "Спочатку створіть товар")
            else:
                self.status_label.configure(text=f"Надходження №{result['id']} успішно створено")
                self.quantity_entry.delete(0, "end")
                self.note_entry.delete(0, "end")
        except Exception as exc:
            self.status_label.configure(text=format_gui_error(exc))
        finally:
            self._set_busy(False)

    def destroy(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except (RuntimeError, ValueError):
                pass
            self._poll_job = None
        if self._future is not None:
            self._future.cancel()
            self._future = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
