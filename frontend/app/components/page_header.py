import customtkinter as ctk


class PageHeader(ctk.CTkFrame):
    """Універсальний заголовок сторінки."""

    def __init__(
        self,
        master,
        title: str,
        description: str = "",
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(
                size=24,
                weight="bold"
            ),
            anchor="w"
        )
        self.title_label.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.description_label = ctk.CTkLabel(
            self,
            text=description,
            font=ctk.CTkFont(size=13),
            text_color=("gray45", "gray65"),
            anchor="w"
        )

        if description:
            self.description_label.grid(
                row=1,
                column=0,
                sticky="ew",
                pady=(6, 0)
            )

    def set_title(self, title: str):
        """Оновити заголовок сторінки."""
        self.title_label.configure(text=title)

    def set_description(self, description: str):
        """Оновити опис сторінки."""
        self.description_label.configure(
            text=description
        )

        if description:
            self.description_label.grid(
                row=1,
                column=0,
                sticky="ew",
                pady=(6, 0)
            )
        else:
            self.description_label.grid_remove()
