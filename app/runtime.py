"""Runtime path resolution.

Works both from source (python run.py) and from a PyInstaller one-file exe.
In frozen mode:
  - read-only bundled resources (frontend/dist) live in sys._MEIPASS
  - user data (db / cookies / logs / config.json) live next to the .exe
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Directory of run.py / the .exe — where user-writable data belongs."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    """Directory of bundled read-only resources."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


APP_ROOT = app_root()
BUNDLE_ROOT = bundle_root()

DATA_DIR = APP_ROOT / "data"
LOG_DIR = APP_ROOT / "logs"
COOKIE_FILE = APP_ROOT / "venue_session.json"
CONFIG_FILE = APP_ROOT / "config.json"
DB_PATH = DATA_DIR / "booking.db"
FRONTEND_DIR = BUNDLE_ROOT / "frontend" / "dist"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("badminton")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    stream = None
    if sys.stdout is not None:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(fmt)
        logger.addHandler(stream)

    try:
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, "app.log"),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        pass

    logger.propagate = False
    return logger


logger = setup_logging()
