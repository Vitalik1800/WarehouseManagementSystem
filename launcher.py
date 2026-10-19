import logging
import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

import httpx
import uvicorn


def configure_environment():
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    env_path = base / ".env"
    if not env_path.is_file():
        raise RuntimeError("Missing .env next to application: " + str(env_path))
    os.environ["WAREHOUSE_ENV_FILE"] = str(env_path)



def configure_uvicorn_logging():
    from logging.handlers import RotatingFileHandler
    from backend.app.core.logging_config import LOG_DIRECTORY
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_DIRECTORY / "uvicorn.log", maxBytes=5242880, backupCount=3, encoding="utf-8")
    handler.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def ensure_port_available(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError("Backend port is already occupied")


def main():
    configure_environment()
    from backend.app.core.config import get_settings
    from frontend.app.core.config import get_frontend_settings
    from backend.app.main import app
    from frontend.main import main as frontend_main

    settings = get_settings()
    frontend_settings = get_frontend_settings()
    host = "127.0.0.1"
    port = settings.api_port
    expected_url = "http://127.0.0.1:" + str(port)
    if frontend_settings.frontend_api_base_url.rstrip("/") != expected_url:
        raise RuntimeError("Frontend API URL does not match local Backend")
    ensure_port_available(host, port)

    configure_uvicorn_logging()
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info", lifespan="on", log_config=None))
    thread = threading.Thread(target=server.run, name="warehouse-backend", daemon=True)
    thread.start()

    ready = False
    try:
        with httpx.Client(timeout=1.0, trust_env=False) as client:
            for _ in range(100):
                if not thread.is_alive():
                    break
                try:
                    response = client.get(expected_url + "/health")
                    if response.status_code == 200 and response.json().get("service") == "backend":
                        ready = True
                        break
                except (httpx.RequestError, ValueError):
                    pass
                time.sleep(0.1)
        if not ready:
            raise RuntimeError("Backend failed to start")
        frontend_main()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def report_startup_error(exc):
    message = str(exc) or type(exc).__name__
    try:
        import ctypes
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "WarehouseManagementSystem" / "logs"
        root.mkdir(parents=True, exist_ok=True)
        with (root / "launcher.log").open("a", encoding="utf-8") as log_file:
            log_file.write(traceback.format_exc() + "\n")
        if getattr(sys, "frozen", False):
            ctypes.windll.user32.MessageBoxW(None, message + "\n\nDetails: " + str(root / "launcher.log"), "WarehouseManagementSystem - Startup Error", 0x10)
    except Exception:
        if sys.stderr is not None:
            traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        report_startup_error(exc)
        raise SystemExit(1)
