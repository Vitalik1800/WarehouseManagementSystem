import customtkinter as ctk

from frontend.app.components.main_layout import MainLayout
from frontend.app.core.config import get_frontend_settings
from frontend.app.core.logging_config import get_frontend_logger


class WarehouseApplication(ctk.CTk):
    """Головне вікно системи управління складом."""

    def __init__(self):
        super().__init__()

        self.settings = get_frontend_settings()
        self.logger = get_frontend_logger("main")

        self.title("Система управління складом")

        self.geometry(
            f"{self.settings.frontend_window_width}x"
            f"{self.settings.frontend_window_height}"
        )

        self.minsize(
            self.settings.frontend_min_window_width,
            self.settings.frontend_min_window_height
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        self._configure_layout()

        self.logger.info(
            "Інтерфейс системи управління складом ініціалізовано"
        )

    def _configure_layout(self):
        """Налаштування головної сітки та інтерфейсу."""

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.main_layout = MainLayout(self)
        self.main_layout.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

    def on_close(self):
        """Коректне завершення роботи застосунку."""

        self.logger.info(
            "Закриття інтерфейсу системи управління складом"
        )
        self.destroy()


def main():
    """Точка входу настільного застосунку."""

    settings = get_frontend_settings()

    ctk.set_appearance_mode(
        settings.frontend_appearance_mode
    )
    ctk.set_default_color_theme(
        settings.frontend_color_theme
    )

    logger = get_frontend_logger("startup")
    logger.info("Запуск настільного застосунку")

    app = WarehouseApplication()
    app.mainloop()


if __name__ == "__main__":
    main()
