"""命令行抢场（不依赖 Web 界面）。

    python tools/cli.py --date 10-25 --time 20:00 --dry-run
    python tools/cli.py --date 10-25 --time 20:00 --time 21:00
    python tools/cli.py --date 10-25 --all
    python tools/cli.py --date 10-25 --time 20:00 --start-at 18:30
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.utils import compute_dateadd, parse_hhmm, resolve_date  # noqa: E402

VENUE = settings.VENUE_URL
VENUE_NO = settings.VENUE_NO
FIELD_TYPE = settings.FIELD_TYPE
COOKIE_FILE = Path(settings.COOKIE_FILE)


def load_cookies() -> dict[str, str]:
    if not COOKIE_FILE.is_file():
        print(f"[错误] 找不到 {COOKIE_FILE}，请先运行 tools/login.py")
        sys.exit(1)
    data = json.loads(COOKIE_FILE.read_text(encoding="utf-8-sig"))
    host = httpx.URL(VENUE).host
    return {
        c["name"]: c["value"]
        for c in data.get("cookies", [])
        if host in str(c.get("domain", ""))
    }


def make_client(cookies: dict[str, str]) -> httpx.Client:
    client = httpx.Client(
        timeout=httpx.Timeout(15.0),
        headers={"User-Agent": settings.UA, "X-Requested-With": "XMLHttpRequest"},
    )
    host = httpx.URL(VENUE).host
    for name, value in cookies.items():
        client.cookies.set(name, value, domain=host)
    return client


def post(client: httpx.Client, path: str, data: dict) -> httpx.Response:
    return client.post(f"{VENUE}{path}", data=data)


def check_login(client: httpx.Client) -> bool:
    try:
        return post(client, "/User/CheckUserStatus", {}).text.strip() == "1"
    except httpx.HTTPError:
        return False


def available_slots(client: httpx.Client, dateadd: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for period in ("0", "1", "2"):
        try:
            resp = post(client, "/Field/GetVenueStateGR", {
                "dateadd": dateadd,
                "TimePeriod": period,
                "VenueNo": VENUE_NO,
                "FieldTypeNo": FIELD_TYPE,
            })
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            continue
        if not isinstance(data, list):
            continue
        for slot in data:
            if not isinstance(slot, dict):
                continue
            if str(slot.get("FieldState")) == "0" and str(slot.get("TimeStatus")) == "1":
                found.setdefault(str(slot.get("BeginTime")), str(slot.get("EndTime")))
    return found


def fields_for(client: httpx.Client, dateadd: str, begin: str, end: str) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for period in ("0", "1", "2"):
        try:
            resp = post(client, "/Field/GetVenueStateNew", {
                "dateadd": dateadd,
                "TimePeriod": period,
                "VenueNo": VENUE_NO,
                "FieldTypeNo": FIELD_TYPE,
            })
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        inner = data.get("resultdata")
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError:
                continue
        if not isinstance(inner, list):
            continue
        for field in inner:
            if not isinstance(field, dict):
                continue
            if (
                str(field.get("BeginTime")) == begin
                and str(field.get("EndTime")) == end
                and str(field.get("FieldState")) == "0"
                and str(field.get("TimeStatus")) == "1"
            ):
                key = str(field.get("FieldNo"))
                if key and key not in seen:
                    seen.add(key)
                    result.append(field)
    result.sort(key=lambda f: str(f.get("FieldName") or ""))
    return result


def order(client: httpx.Client, field: dict, dateadd: str) -> dict:
    checkdata = json.dumps([{
        "FieldNo": field.get("FieldNo"),
        "FieldTypeNo": field.get("FieldTypeNo") or FIELD_TYPE,
        "FieldName": field.get("FieldName", ""),
        "BeginTime": field.get("BeginTime"),
        "Endtime": field.get("EndTime"),
        "Price": field.get("FinalPrice") or "0",
    }], ensure_ascii=False)
    try:
        resp = post(client, "/Field/OrderFieldFree", {
            "checkdata": checkdata,
            "dateadd": dateadd,
            "VenueNo": VENUE_NO,
        })
        data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return {"success": False, "message": str(exc)}
    if not isinstance(data, dict):
        return {"success": False, "message": resp.text[:120]}
    return {
        "success": str(data.get("type")) == "1",
        "message": str(data.get("message") or data.get("msg") or ""),
    }


def wait_until(hhmm: str) -> None:
    try:
        hour, minute = parse_hhmm(hhmm)
    except ValueError as exc:
        print(f"[错误] --start-at {exc}")
        sys.exit(1)
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        print(f"[提示] {hhmm} 已过，立即开始")
        return
    print(f"[定时] 将于 {hhmm} 启动（剩余 {int((target - now).total_seconds() // 60)} 分钟）")
    while (remaining := (target - datetime.now()).total_seconds()) > 0:
        time.sleep(min(remaining, 30))


def main() -> None:
    parser = argparse.ArgumentParser(description="命令行抢场")
    parser.add_argument("--date", required=True, help="目标日期 MM-DD")
    parser.add_argument("--time", action="append", dest="times", help="目标时段 HH:MM，可多次")
    parser.add_argument("--all", action="store_true", help="抢所有可订时段")
    parser.add_argument("--interval", type=float, default=settings.DEFAULT_POLL_INTERVAL)
    parser.add_argument("--start-at", metavar="HH:MM", help="定时启动")
    parser.add_argument("--dry-run", action="store_true", help="只查询不下单")
    args = parser.parse_args()

    try:
        resolve_date(args.date)
        if args.times:
            for item in args.times:
                parse_hhmm(item)
    except ValueError as exc:
        print(f"[错误] {exc}")
        sys.exit(1)

    dateadd = compute_dateadd(args.date)
    targets = sorted(set(args.times or []))
    interval = max(args.interval, settings.MIN_POLL_INTERVAL)

    client = make_client(load_cookies())
    if not check_login(client):
        print("[错误] 登录已过期，请重新运行 tools/login.py")
        sys.exit(1)
    post(client, "/Venue/SetVenue", {"VenueNo": VENUE_NO})

    print(f"\n{'=' * 58}")
    print(f"目标日期 {args.date}（dateadd={dateadd}）｜时段 {targets or '全部可订'}")
    print(f"轮询 {interval}s｜{'仅查询' if args.dry_run else '真实下单'}")
    print(f"{'=' * 58}\n")

    if args.start_at:
        wait_until(args.start_at)

    booked: set[str] = set()
    deadline = datetime.now() + timedelta(hours=settings.MAX_RUNTIME_HOURS)

    while datetime.now() < deadline:
        try:
            slots = available_slots(client, dateadd)
        except httpx.HTTPError as exc:
            print(f"  [重连] {exc}")
            client.close()
            client = make_client(load_cookies())
            post(client, "/Venue/SetVenue", {"VenueNo": VENUE_NO})
            time.sleep(interval)
            continue

        pool = targets or sorted(slots)
        status = "  ".join(
            f"{t}={'已抢' if t in booked else ('可订' if t in slots else '--')}" for t in pool
        )
        print(f"[{datetime.now():%H:%M:%S}] {status}")

        pending = [t for t in pool if t not in booked and t in slots]
        for begin in pending:
            end = slots[begin]
            fields = fields_for(client, dateadd, begin, end)
            if not fields:
                continue
            for field in fields[:2]:
                name = str(field.get("FieldName") or field.get("FieldNo"))
                if args.dry_run:
                    print(f"  [仅查询] 可抢 {name} {begin}-{end}")
                    booked.add(begin)
                    break
                result = order(client, field, dateadd)
                print(f"  下单 {name} {begin}-{end} → {'成功' if result['success'] else result['message'][:50]}")
                if result["success"]:
                    booked.add(begin)
                    break

        if targets and set(targets) <= booked:
            print(f"\n全部完成：{sorted(booked)}")
            break
        if args.all and not pending:
            print(f"\n当前可订时段已全部处理：{sorted(booked)}")
            break

        time.sleep(max(0.3, interval * random.uniform(0.85, 1.25)))

    client.close()


if __name__ == "__main__":
    main()
