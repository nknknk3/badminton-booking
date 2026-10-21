"""Configuration.

Priority: environment variable > config.json (next to run.py / the .exe) > default.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from typing import Any

from app.runtime import CONFIG_FILE, COOKIE_FILE, DB_PATH, DATA_DIR, logger


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # ---- venue (upstream site) ----
    VENUE_URL: str = "https://gyytygyy.xidian.edu.cn"
    VENUE_NO: str = "02"
    FIELD_TYPE: str = "021"
    UA: str = (
        "Mozilla/5.0 (Linux; Android 13; SM-S9080) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.43"
    )
    HTTP_TIMEOUT: float = 15.0
    MAX_CONNECTIONS: int = 10

    # ---- server ----
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    OPEN_BROWSER: bool = True
    # When set, every /api request must carry this token (?token= or X-Access-Token)
    ACCESS_TOKEN: str = ""

    # ---- booking behaviour ----
    DEFAULT_POLL_INTERVAL: float = 3.0
    MIN_POLL_INTERVAL: float = 0.5
    MAX_POLL_INTERVAL: float = 60.0
    # Start looking this many minutes before the earliest target slot opens
    BOOKING_OPEN_LEAD_MINUTES: int = 150
    # Give up after this long instead of after N attempts
    MAX_RUNTIME_HOURS: float = 4.0
    # Never book more than this many slots per task run
    MAX_SLOTS_PER_TASK: int = 3

    # ---- notifications ----
    PUSHPLUS_TOKEN: str = ""

    # ---- paths ----
    DB_PATH: str = str(DB_PATH)
    COOKIE_FILE: str = str(COOKIE_FILE)

    # ---- tunnel ----
    ENABLE_TUNNEL: bool = False
    NGROK_AUTH_TOKEN: str = ""

    CORS_ORIGINS: list[str] = field(default_factory=lambda: ["*"])


_JSON_KEYS = {f.name for f in fields(Settings)}


def _load_json_overrides() -> dict[str, Any]:
    if not CONFIG_FILE.is_file():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("config.json 解析失败，已忽略: %s", exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("config.json 顶层必须是对象，已忽略")
        return {}
    return {k: v for k, v in data.items() if k in _JSON_KEYS}


def _build() -> Settings:
    s = Settings()
    for key, value in _load_json_overrides().items():
        setattr(s, key, value)

    # environment wins
    env_map = {
        "PORT": ("PORT", int),
        "HOST": ("HOST", str),
        "ACCESS_TOKEN": ("ACCESS_TOKEN", str),
        "PUSHPLUS_TOKEN": ("PUSHPLUS_TOKEN", str),
        "NGROK_AUTH_TOKEN": ("NGROK_AUTH_TOKEN", str),
        "OPEN_BROWSER": ("OPEN_BROWSER", _as_bool),
        "ENABLE_TUNNEL": ("ENABLE_TUNNEL", _as_bool),
    }
    for key, (env_name, caster) in env_map.items():
        raw = _env(env_name)
        if raw == "":
            continue
        try:
            setattr(s, key, caster(raw))
        except (TypeError, ValueError):
            logger.warning("环境变量 %s=%r 无效，已忽略", env_name, raw)

    # .ngrok_token file fallback
    if not s.NGROK_AUTH_TOKEN:
        token_file = os.path.join(str(CONFIG_FILE.parent), ".ngrok_token")
        if os.path.isfile(token_file):
            try:
                with open(token_file, encoding="utf-8") as f:
                    s.NGROK_AUTH_TOKEN = f.read().strip()
            except OSError:
                pass

    s.PORT = int(s.PORT)
    s.DEFAULT_POLL_INTERVAL = max(
        float(s.DEFAULT_POLL_INTERVAL), float(s.MIN_POLL_INTERVAL)
    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return s


settings = _build()


_RUNTIME_KEYS = {
    "DEFAULT_POLL_INTERVAL",
    "BOOKING_OPEN_LEAD_MINUTES",
    "MAX_RUNTIME_HOURS",
    "MIN_POLL_INTERVAL",
    "MAX_POLL_INTERVAL",
    "PUSHPLUS_TOKEN",
}


def save_overrides(values: dict[str, Any]) -> None:
    """Persist a few runtime knobs to config.json and apply them immediately."""
    clean = {k: v for k, v in values.items() if k in _RUNTIME_KEYS}
    if not clean:
        return
    data: dict[str, Any] = {}
    if CONFIG_FILE.is_file():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取 config.json 失败，将重建: %s", exc)
    data.update(clean)
    try:
        CONFIG_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("写入 config.json 失败: %s", exc)
        return
    for key, value in clean.items():
        setattr(settings, key, value)
    logger.info("运行参数已更新: %s", clean)
