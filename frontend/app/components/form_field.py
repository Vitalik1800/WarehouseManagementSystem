import customtkinter as ctk


class FormField(ctk.CTkFrame):
    """Універсальне текстове поле форми."""

    def __init__(
        self,
        master,
        label: str,
        placeholder: str = "",
        required: bool = False,
        show: str | None = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self.required = required

        self.grid_columnconfigure(0, weight=1)

        label_text = f"{label} *" if required else label

        self.label_weight = ctk.CTkLabel(
            self,
            text=label_text,
            anchor="w",
            font=ctk.CTkFont(
                size=13,
                weight="bold"
            )
        )
        self.label_weight.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 6)
        )

        entry_options = {
            "placeholder_text": placeholder,
            "height": 36
        }

        if show is not None:
            entry_options["show"] = show

        self.entry = ctk.CTkEntry(
            self,
            **entry_options
        )
        self.entry.grid(
            row=1,
            column=0,
            sticky="ew"
        )

        self.error_label = ctk.CTkLabel(
            self,
            text="",
            text_color=("#B42318", "#F97066"),
            anchor="w",
            font=ctk.CTkFont(size=12)
        )

    def get_value(self) -> str:
        """Отримати значення поля."""
        return self.entry.get().strip()

    def set_value(self, value: str) -> None:
        """Встановити значення поля."""
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.clear_error()

    def clear(self) -> None:
        """Очистити поле."""
        self.entry.delete(0, "end")
        self.clear_error()

    def show_error(self, message: str) -> None:
        """Показати повідомлення про помилку."""
        self.error_label.configure(text=message)
        self.error_label.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(4, 0)
        )

    def clear_error(self) -> None:
        """Приховати повідомлення про помилку."""
        self.error_label.configure(text="")
        self.error_label.grid_remove()

    def validate(self) -> bool:
        """Перевірити обов'язковість заповнення."""
        self.clear_error()

        if self.required and not self.get_value():
            self.show_error(
                "Це поле є обов'язковим"
            )
            return False

        return True
