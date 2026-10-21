"""Shared date / time helpers.

All paths that accept a user supplied date go through these, so a malformed
value raises ValueError instead of crashing deep inside the scheduler.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_MMDD = re.compile(r"^(\d{1,2})-(\d{1,2})$")
_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_mmdd(value: str) -> tuple[int, int]:
    m = _MMDD.match((value or "").strip())
    if not m:
        raise ValueError(f"日期格式应为 MM-DD，收到 {value!r}")
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError(f"日期不合法: {value!r}")
    return month, day


def resolve_date(mmdd: str, today: date | None = None) -> date:
    """Turn MM-DD into the next real date on/after today."""
    today = today or date.today()
    month, day = parse_mmdd(mmdd)
    try:
        candidate = date(today.year, month, day)
    except ValueError as exc:  # e.g. 02-30
        raise ValueError(f"日期不合法: {mmdd!r}") from exc
    if candidate < today:
        try:
            candidate = date(today.year + 1, month, day)
        except ValueError as exc:
            raise ValueError(f"日期不合法: {mmdd!r}") from exc
    return candidate


def compute_dateadd(mmdd: str, today: date | None = None) -> str:
    """Days from today, as the upstream API expects."""
    today = today or date.today()
    return str((resolve_date(mmdd, today) - today).days)


def next_days(count: int = 7, today: date | None = None) -> list[str]:
    today = today or date.today()
    return [(today + timedelta(days=i)).strftime("%m-%d") for i in range(max(1, count))]


def parse_hhmm(value: str) -> tuple[int, int]:
    m = _HHMM.match((value or "").strip())
    if not m:
        raise ValueError(f"时间格式应为 HH:MM，收到 {value!r}")
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"时间不合法: {value!r}")
    return hour, minute


def parse_start_at(value: str | None) -> datetime | None:
    """Accepts 'YYYY-MM-DDTHH:MM', 'YYYY-MM-DD HH:MM' or 'HH:MM' (today)."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    hour, minute = parse_hhmm(text)
    now = datetime.now()
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
