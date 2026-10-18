"""Tabbed stock movements: receipt, issue, writeoff and read-only history."""
from concurrent.futures import ThreadPoolExecutor
from typing import Any
import customtkinter as ctk
from frontend.app.api.client import APIClient
from frontend.app.core.gui_errors import format_gui_error
from frontend.app.services.stock_movement_service import StockMovementService
from frontend.app.views.stock_receipts_view import StockReceiptsView
from frontend.app.views.stock_issues_view import StockIssuesView
from frontend.app.views.stock_writeoffs_view import StockWriteoffsView


class StockMovementsView(ctk.CTkFrame):
    def __init__(self, master: Any, api_client: APIClient, user_role: str = 'worker', **kwargs: Any) -> None:
        if user_role not in ('admin', 'worker'):
            raise ValueError('Unsupported role')
        super().__init__(master, **kwargs)
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='stock-history')
        self._future = None
        self._poll_job = None
        self._offset = 0
        self._limit = 20
        self._service = StockMovementService(api_client)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=0, column=0, sticky='nsew')
        for label in ('Надходження', 'Видача', 'Списання', 'Історія'):
            self.tabs.add(label)
        for label, cls in (('Надходження', StockReceiptsView), ('Видача', StockIssuesView),
                           ('Списання', StockWriteoffsView)):
            tab = self.tabs.tab(label)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            view = cls(tab, api_client, user_role=user_role)
            view.grid(row=0, column=0, sticky='nsew')
        history = self.tabs.tab('Історія')
        history.grid_columnconfigure(0, weight=1)
        history.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(history, fg_color='transparent')
        toolbar.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        self.refresh_button = ctk.CTkButton(toolbar, text='Оновити історію', command=self.refresh_history)
        self.refresh_button.pack(side='left', padx=4)
        self.prev_button = ctk.CTkButton(toolbar, text='Назад', width=70, command=self.previous_page)
        self.prev_button.pack(side='left', padx=4)
        self.next_button = ctk.CTkButton(toolbar, text='Далі', width=70, command=self.next_page)
        self.next_button.pack(side='left', padx=4)
        self.page_label = ctk.CTkLabel(toolbar, text='')
        self.page_label.pack(side='left', padx=8)
        self.history_text = ctk.CTkTextbox(history, wrap='none')
        self.history_text.grid(row=1, column=0, sticky='nsew', padx=8, pady=8)
        self.history_text.configure(state='disabled')
        self.status_label = ctk.CTkLabel(history, text='Натисніть «Оновити історію»')
        self.status_label.grid(row=2, column=0, sticky='ew', padx=8)
        self._set_buttons(False, False)

    def _set_buttons(self, busy: bool, has_next: bool) -> None:
        self.refresh_button.configure(state='disabled' if busy else 'normal')
        self.prev_button.configure(state='disabled' if busy or self._offset == 0 else 'normal')
        self.next_button.configure(state='disabled' if busy or not has_next else 'normal')
        self.page_label.configure(text=f'Сторінка {self._offset // self._limit + 1}')

    def refresh_history(self) -> None:
        if self._closed or self._future is not None:
            return
        self._set_buttons(True, False)
        self.status_label.configure(text='Завантаження історії...')
        self._future = self._executor.submit(self._service.list_movements,
                                             offset=self._offset, limit=self._limit)
        self._poll_job = self.after(50, self._check_result)

    def previous_page(self) -> None:
        if self._future is None and self._offset >= self._limit:
            self._offset -= self._limit
            self.refresh_history()

    def next_page(self) -> None:
        if self._future is None and self.next_button.cget('state') == 'normal':
            self._offset += self._limit
            self.refresh_history()

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
            lines = ['ID   Дата                  Тип         Товар   Кількість   Примітка', '-' * 90]
            for r in rows:
                lines.append(f"{r['id']:<4} {r['created_at'][:19]:<19}  {r['movement_type']:<10}  "
                             f"{r['product_id']:<6}  {r['quantity']:<10}  {r.get('note') or ''}")
            if not rows:
                lines.append('Операцій не знайдено')
            self.history_text.configure(state='normal')
            self.history_text.delete('1.0', 'end')
            self.history_text.insert('1.0', '\n'.join(lines))
            self.history_text.configure(state='disabled')
            self.status_label.configure(text=f'Записів на сторінці: {len(rows)}')
            self._set_buttons(False, len(rows) == self._limit)
        except Exception as exc:
            self.status_label.configure(text=format_gui_error(exc))
            self._set_buttons(False, False)

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
