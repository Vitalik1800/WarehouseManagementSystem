"""Read-only stock balances view with search, filters and pagination."""
from concurrent.futures import ThreadPoolExecutor
from typing import Any
import customtkinter as ctk
from frontend.app.api.client import APIClient
from frontend.app.core.gui_errors import format_gui_error
from frontend.app.services.stock_balance_service import StockBalanceService


class StockBalancesView(ctk.CTkFrame):
    PAGE_SIZE = 20
    STATUS_OPTIONS = {'Усі': None, 'У наявності': 'in_stock', 'Немає в наявності': 'out_of_stock'}
    SORT_OPTIONS = {'За ID': 'id', 'Кількість ↑': 'quantity_asc', 'Кількість ↓': 'quantity_desc'}

    def __init__(self, master: Any, api_client: APIClient, user_role: str = 'worker', **kwargs: Any) -> None:
        if user_role not in ('admin', 'worker'):
            raise ValueError('Unsupported role')
        super().__init__(master, **kwargs)
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='stock-balances')
        self._future = None
        self._poll_job = None
        self._offset = 0
        self._has_next = False
        self._service = StockBalanceService(api_client)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        self.search_entry = ctk.CTkEntry(bar, width=210, placeholder_text='Назва або SKU')
        self.search_entry.pack(side='left', padx=4, pady=8)
        self.status_menu = ctk.CTkOptionMenu(bar, values=list(self.STATUS_OPTIONS), width=155)
        self.status_menu.pack(side='left', padx=4)
        self.sort_menu = ctk.CTkOptionMenu(bar, values=list(self.SORT_OPTIONS), width=145)
        self.sort_menu.pack(side='left', padx=4)
        self.refresh_button = ctk.CTkButton(bar, text='Знайти / Оновити', width=135, command=self.reset_search)
        self.refresh_button.pack(side='left', padx=4)
        self.table = ctk.CTkTextbox(self, wrap='none')
        self.table.grid(row=1, column=0, sticky='nsew', padx=8, pady=8)
        self.table.configure(state='disabled')
        foot = ctk.CTkFrame(self, fg_color='transparent')
        foot.grid(row=2, column=0, sticky='ew', padx=8, pady=4)
        self.prev_button = ctk.CTkButton(foot, text='Назад', width=75, command=self.previous_page)
        self.prev_button.pack(side='left', padx=4)
        self.next_button = ctk.CTkButton(foot, text='Далі', width=75, command=self.next_page)
        self.next_button.pack(side='left', padx=4)
        self.status_label = ctk.CTkLabel(foot, text='')
        self.status_label.pack(side='left', padx=8)
        self._set_busy(False)
        self.refresh()

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.configure(state='disabled' if busy else 'normal')
        self.prev_button.configure(state='disabled' if busy or self._offset == 0 else 'normal')
        self.next_button.configure(state='disabled' if busy or not self._has_next else 'normal')

    def reset_search(self) -> None:
        if self._future is not None:
            return
        self._offset = 0
        self.refresh()

    def refresh(self) -> None:
        if self._closed or self._future is not None:
            return
        params = {'offset': self._offset, 'limit': self.PAGE_SIZE,
                  'search': self.search_entry.get().strip() or None,
                  'stock_status': self.STATUS_OPTIONS[self.status_menu.get()],
                  'sort_by': self.SORT_OPTIONS[self.sort_menu.get()]}
        self._set_busy(True)
        self.status_label.configure(text='Завантаження залишків...')
        self._future = self._executor.submit(self._service.list_balances, **params)
        self._poll_job = self.after(50, self._check_result)

    def previous_page(self) -> None:
        if self._future is None and self._offset >= self.PAGE_SIZE:
            self._offset -= self.PAGE_SIZE
            self.refresh()

    def next_page(self) -> None:
        if self._future is None and self._has_next:
            self._offset += self.PAGE_SIZE
            self.refresh()

    def _check_result(self) -> None:
        self._poll_job = None
        if self._closed or self._future is None:
            return
        if not self._future.done():
            self._poll_job = self.after(50, self._check_result)
            return
        future, self._future = self._future, None
        try:
            rows = future.result()
            lines = ['ID    SKU               Назва                         Залишок     Од.', '-' * 88]
            for r in rows:
                lines.append(f"{r['id']:<5} {r['sku'][:17]:<17} {r['name'][:29]:<29} "
                             f"{r['quantity']:<11} {r['unit']}")
            if not rows:
                lines.append('Товарів не знайдено')
            self.table.configure(state='normal')
            self.table.delete('1.0', 'end')
            self.table.insert('1.0', '\n'.join(lines))
            self.table.configure(state='disabled')
            self._has_next = len(rows) == self.PAGE_SIZE
            self.status_label.configure(text=f'Сторінка {self._offset // self.PAGE_SIZE + 1} · записів: {len(rows)}')
        except Exception as exc:
            self._has_next = False
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
        if self._future is not None:
            self._future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
