import customtkinter as ctk


class NotificationBanner(ctk.CTkFrame):
    """Багаторазова панель повідомлень."""

    VARIANTS = ("success", "info", "warning", "error")

    COLORS = {
        "success": {
            "background": ("#D1FADF", "#14532D"),
            "text": ("#065F46", "#D1FAE5"),
        },
        "info": {
            "background": ("#DBEAFE", "#1E3A5F"),
            "text": ("#1E40AF", "#DBEAFE"),
        },
        "warning": {
            "background": ("#FEF3C7", "#78350F"),
            "text": ("#92400E", "#FEF3C7"),
        },
        "error": {
            "background": ("#FEE2E2", "#7F1D1D"),
            "text": ("#991B1B", "#FEE2E2"),
        }
    }

    def __init__(
        self,
        master,
        message: str = "",
        variant: str = "info",
        **kwargs
    ):
        if variant not in self.VARIANTS:
            raise ValueError(
                f"Unsupported notification variant: {variant}"
            )

        self.variant = variant

        super().__init__(
            master,
            corner_radius=8,
            fg_color=self.COLORS[variant]["background"],
            **kwargs
        )

        self.grid_columnconfigure(0, weight=1)

        self.message_label = ctk.CTkLabel(
            self,
            text=message,
            anchor="w",
            justify="left",
            wraplength=600,
            text_color=self.COLORS[variant]["text"],
            font=ctk.CTkFont(size=13)
        )
        self.message_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=14,
            pady=10
        )

        self.close_button = ctk.CTkButton(
            self,
            text="x",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=self.COLORS[variant]["text"],
            command=self.hide
        )
        self.close_button.grid(
            row=0,
            column=1,
            padx=(0, 8),
            pady=6
        )

    def show(
        self,
        message: str,
        variant: str = "info"
    ) -> None:
        """Показати або оновити повідомлення."""

        if variant not in self.VARIANTS:
            raise ValueError(
                f"Unsupported notification variant: {variant}"
            )

        self.variant = variant
        self.message_label.configure(
            text=message,
            text_color=self.COLORS[variant]["text"]
        )
        self.close_button.configure(
            text_color=self.COLORS[variant]["text"]
        )
        self.configure(
            fg_color=self.COLORS[variant]["background"]
        )

        self.grid()

    def hide(self) -> None:
        """Приховати повідомлення."""
        self.grid_remove()

    def get_message(self) -> str:
        """Отримати поточний текст повідомлення."""
        return self.message_label.cget("text")
