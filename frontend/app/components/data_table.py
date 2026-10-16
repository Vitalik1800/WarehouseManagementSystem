from collections.abc import Sequence
from math import ceil

import customtkinter as ctk


class DataTable(ctk.CTkFrame):
    """Універсальна таблиця з клієнтською пагінацією."""

    PAGE_SIZE_OPTIONS = (25, 50, 100)

    def __init__(
        self,
        master,
        columns: Sequence[str],
        rows: Sequence[Sequence[object]] | None = None,
        empty_message: str = "Немає даних",
        page_size: int = 25,
        **kwargs
    ):
        if not columns:
            raise ValueError(
                "DataTable requires at least one column"
            )

        if page_size not in self.PAGE_SIZE_OPTIONS:
            raise ValueError(
                f"Unsupported page size: {page_size}"
            )

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.columns = tuple(columns)
        self.empty_message = empty_message
        self.rows: list[tuple[object, ...]] = []
        self.page_size = page_size
        self.current_page = 1

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._create_table()
        self._create_pagination()

        self.set_rows(
            rows if rows is not None else []
        )

    def _create_table(self) -> None:
        self.table_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent"
        )
        self.table_frame.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        for index in range(len(self.columns)):
            self.table_frame.grid_columnconfigure(
                index,
                weight=1,
                uniform="table_columns"
            )

        self._render_header()

    def _render_header(self) -> None:
        for index, column in enumerate(self.columns):
            label = ctk.CTkLabel(
                self.table_frame,
                text=column,
                font=ctk.CTkFont(
                    size=13,
                    weight="bold"
                ),
                anchor="w",
                fg_color=("gray85", "gray25"),
                corner_radius=4
            )
            label.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=2,
                pady=(0, 6),
                ipadx=8,
                ipady=6
            )

    def _create_pagination(self) -> None:
        self.pagination_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        self.pagination_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(10, 0)
        )

        self.pagination_frame.grid_columnconfigure(
            1,
            weight=1
        )

        self.previous_button = ctk.CTkButton(
            self.pagination_frame,
            text="Назад",
            width=90,
            command=self.previous_page
        )
        self.previous_button.grid(
            row=0,
            column=0,
            padx=(0, 10)
        )

        self.page_label = ctk.CTkLabel(
            self.pagination_frame,
            text="Сторінка 1 із 1"
        )
        self.page_label.grid(
            row=0,
            column=1
        )

        self.next_button = ctk.CTkButton(
            self.pagination_frame,
            text="Далі",
            width=90,
            command=self.next_page
        )
        self.next_button.grid(
            row=0,
            column=2,
            padx=(10, 0)
        )

        self.page_size_selector = ctk.CTkOptionMenu(
            self.pagination_frame,
            values=[
                str(value)
                for value in self.PAGE_SIZE_OPTIONS
            ],
            command=self._on_page_size_change,
            width=80
        )
        self.page_size_selector.grid(
            row=0,
            column=3,
            padx=(16, 0)
        )
        self.page_size_selector.set(
            str(self.page_size)
        )

    def _clear_data(self) -> None:
        for widget in self.table_frame.winfo_children():
            grid_info = widget.grid_info()

            if int(grid_info.get("row", -1)) > 0:
                widget.destroy()

    def get_total_pages(self) -> int:
        """Повернути загальну кількість сторінок."""
        return max(
            1,
            ceil(len(self.rows) / self.page_size)
        )

    def get_visible_rows(self) -> list[tuple[object, ...]]:
        """Повернути дані поточної сторінки."""
        start = (
            self.current_page - 1
        ) * self.page_size

        end = start + self.page_size

        return list(self.rows[start:end])

    def _render_page(self) -> None:
        self._clear_data()

        visible_rows = self.get_visible_rows()

        if not visible_rows:
            empty_label = ctk.CTkLabel(
                self.table_frame,
                text=self.empty_message,
                font=ctk.CTkFont(size=13),
                text_color=("gray45", "gray65")
            )
            empty_label.grid(
                row=1,
                column=0,
                columnspan=len(self.columns),
                sticky="ew",
                pady=24
            )
        else:
            for row_index, row in enumerate(
                visible_rows,
                start=1
            ):
                for column_index, value in enumerate(row):
                    cell = ctk.CTkLabel(
                        self.table_frame,
                        text=str(value),
                        anchor="w",
                        font=ctk.CTkFont(size=12)
                    )
                    cell.grid(
                        row=row_index,
                        column=column_index,
                        sticky="ew",
                        padx=8,
                        pady=6
                    )

        self.page_label.configure(
            text=(
                f"Сторінка {self.current_page} "
                f"із {self.get_total_pages()}"
            )
        )

        self.previous_button.configure(
            state=(
                "normal"
                if self.current_page > 1
                else "disabled"
            )
        )

        self.next_button.configure(
            state=(
                "normal"
                if self.current_page < self.get_total_pages()
                else "disabled"
            )
        )

    def set_rows(
        self,
        rows: Sequence[Sequence[object]]
    ) -> None:
        """Замінити всі дані та перейти на першу сторінку."""

        normalized_rows = []

        for row in rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    "Row length does not match column count"
                )

            normalized_rows.append(tuple(row))

        self.rows = normalized_rows
        self.current_page = 1

        self._render_page()

    def get_rows(self) -> list[tuple[object, ...]]:
        """Повернути копію всіх даних."""
        return list(self.rows)

    def go_to_page(self, page: int) -> None:
        """Перейти на сторінку за номером."""

        if not 1 <= page <= self.get_total_pages():
            raise ValueError(
                f"Invalid page number: {page}"
            )

        self.current_page = page
        self._render_page()

    def next_page(self) -> None:
        """Перейти на наступну сторінку."""

        if self.current_page < self.get_total_pages():
            self.go_to_page(self.current_page + 1)

    def previous_page(self) -> None:
        """Перейти на попередню сторінку."""

        if self.current_page > 1:
            self.go_to_page(self.current_page - 1)

    def _on_page_size_change(self, value: str) -> None:
        """Змінити кількість рядків на сторінці."""

        page_size = int(value)

        if page_size not in self.PAGE_SIZE_OPTIONS:
            raise ValueError(
                f"Unsupported page size: {page_size}"
            )

        self.page_size = page_size
        self.current_page = 1

        self._render_page()

    def clear(self) -> None:
        """Очистити всі дані таблиці."""
        self.set_rows([])
