from __future__ import annotations

import asyncio
import os

import aiosqlite

from app.config import settings

_db: aiosqlite.Connection | None = None
_lock = asyncio.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS booking_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_date TEXT NOT NULL,
    target_times TEXT NOT NULL,
    poll_interval REAL DEFAULT 3.0,
    start_at TEXT,
    enabled INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS booking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    field_no TEXT NOT NULL,
    field_name TEXT NOT NULL,
    date TEXT NOT NULL,
    begin_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_created ON booking_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_task ON booking_history(task_id);
"""


async def init_db() -> None:
    global _db
    os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)
    if _db is None:
        _db = await aiosqlite.connect(settings.DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(SCHEMA)
        await _db.commit()


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        async with _lock:
            if _db is None:
                await init_db()
    assert _db is not None
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
