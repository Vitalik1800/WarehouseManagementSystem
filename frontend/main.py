import customtkinter as ctk

from frontend.app.core.config import (
    get_frontend_settings
)
from frontend.app.core.logging_config import (
    get_frontend_logger
)


class WarehouseApplication(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = get_frontend_settings()
        self.logger = get_frontend_logger("main")

        self.title("Система управління складом")

        self.geometry("1100x700")
        self.minsize(800,500)

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        self.logger.info(
            "Інтерфейс системи управління складом ініціалізовано"
        )

    def on_close(self):
        self.logger.info(
            "Закриття інтерфейсу системи управління складом"
        )
        self.destroy()


def main():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    logger = get_frontend_logger("startup")
    logger.info("Запуск настільного застосунку")

    app = WarehouseApplication()
    app.mainloop()


if __name__ == "__main__":
    main()