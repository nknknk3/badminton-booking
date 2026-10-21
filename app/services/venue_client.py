"""Async client for the venue upstream.

Single shared instance for the whole process: when a new cookie file is
uploaded, `reload_cookies()` swaps the underlying httpx client, so the venue
browser, manual booking and the scheduler all pick it up immediately.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Iterable

import httpx

from app.config import settings
from app.runtime import logger


class VenueError(Exception):
    """Upstream problem (network / HTTP / malformed payload)."""


class VenueAuthError(VenueError):
    """Not logged in or session expired."""


def _filter_venue_cookies(payload: Any) -> dict[str, str]:
    host = client_host()
    cookies: dict[str, str] = {}
    if isinstance(payload, dict):
        raw = payload.get("cookies")
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                domain = str(item.get("domain", ""))
                name = item.get("name")
                value = item.get("value")
                if not name or value is None:
                    continue
                domain = domain.lstrip(".").lower()
                if domain == host or (domain and host.endswith("." + domain)):
                    cookies[str(name)] = str(value)
        elif isinstance(payload.get("_cookies"), list):
            for item in payload["_cookies"]:
                if isinstance(item, dict) and item.get("name"):
                    cookies[str(item["name"])] = str(item.get("value", ""))
    return cookies


def client_host() -> str:
    return httpx.URL(settings.VENUE_URL).host


def read_cookie_file(path: str | None = None) -> tuple[dict[str, str], str | None]:
    """Returns (cookies, captured_at). Raises ValueError on a bad file."""
    path = path or settings.COOKIE_FILE
    if not os.path.isfile(path):
        return {}, None
    try:
        with open(path, encoding="utf-8-sig") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"session 文件无法解析: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("session 文件顶层必须是 JSON 对象")
    cookies = _filter_venue_cookies(payload)
    captured = payload.get("captured_at")
    return cookies, str(captured) if captured else None


class VenueClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cookies: dict[str, str] = {}
        self._captured_at: str | None = None
        self._venue_selected = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ setup
    async def start(self) -> None:
        await self.reload_cookies()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def reload_cookies(self) -> int:
        """Rebuild the HTTP client from the cookie file. Returns cookie count."""
        try:
            cookies, captured = read_cookie_file()
        except ValueError as exc:
            logger.warning("cookie 文件无效，按未登录处理: %s", exc)
            cookies, captured = {}, None

        new_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.HTTP_TIMEOUT),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=settings.MAX_CONNECTIONS,
                max_keepalive_connections=settings.MAX_CONNECTIONS,
            ),
            headers={
                "User-Agent": settings.UA,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )
        host = client_host()
        for name, value in cookies.items():
            new_client.cookies.set(name, value, domain=host)

        old = self._client
        self._client = new_client
        self._cookies = cookies
        self._captured_at = captured
        self._venue_selected = False
        if old is not None:
            await old.aclose()
        logger.info("cookie 已重新加载: %d 条", len(cookies))
        return len(cookies)

    @property
    def cookie_count(self) -> int:
        return len(self._cookies)

    @property
    def captured_at(self) -> str | None:
        return self._captured_at

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise VenueError("HTTP 客户端尚未初始化")
        return self._client

    # ------------------------------------------------------------------- core
    async def _post(self, path: str, data: dict | None = None) -> httpx.Response:
        url = f"{settings.VENUE_URL}{path}"
        try:
            resp = await self._http().post(url, data=data)
        except httpx.TimeoutException as exc:
            raise VenueError("场馆服务器响应超时") from exc
        except httpx.HTTPError as exc:
            raise VenueError(f"无法连接场馆服务器: {exc}") from exc
        if resp.status_code >= 400:
            raise VenueError(f"场馆服务器返回 HTTP {resp.status_code}")
        return resp

    @staticmethod
    def _json(resp: httpx.Response) -> Any:
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            snippet = (resp.text or "")[:120].replace("\n", " ")
            raise VenueError(f"场馆返回了非 JSON 数据: {snippet}") from exc

    async def check_login(self, cookies: list[dict] | None = None) -> bool:
        if cookies is not None:
            # Verify a candidate session separately, keeping the active session
            # intact until the redirect chain has actually completed.
            jar = httpx.Cookies()
            for item in cookies:
                jar.set(item["name"], item["value"], domain=item["domain"], path=item.get("path", "/"))
            async with httpx.AsyncClient(
                cookies=jar, timeout=5, follow_redirects=True, trust_env=False,
                headers={"User-Agent": settings.UA, "X-Requested-With": "XMLHttpRequest"},
            ) as client:
                resp = await client.post(f"{settings.VENUE_URL}/User/CheckUserStatus")
                resp.raise_for_status()
                return resp.text.lstrip("\ufeff").strip() == "1"
        if not self._cookies:
            return False
        resp = await self._post("/User/CheckUserStatus")
        return (resp.text or "").lstrip("\ufeff").strip() == "1"

    async def ensure_login(self) -> None:
        if not await self.check_login():
            raise VenueAuthError("登录已过期，请重新导入 session 文件")

    async def set_venue(self, venue_no: str | None = None) -> None:
        if self._venue_selected:
            return
        try:
            await self._post(
                "/Venue/SetVenue", {"VenueNo": venue_no or settings.VENUE_NO}
            )
            self._venue_selected = True
        except VenueError as exc:
            logger.debug("SetVenue 失败（继续尝试）: %s", exc)

    # ---------------------------------------------------------------- queries
    async def _slots_for_period(self, dateadd: str, period: str) -> list[dict]:
        resp = await self._post(
            "/Field/GetVenueStateGR",
            {
                "dateadd": dateadd,
                "TimePeriod": period,
                "VenueNo": settings.VENUE_NO,
                "FieldTypeNo": settings.FIELD_TYPE,
            },
        )
        data = self._json(resp)
        return [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []

    async def get_slots(self, dateadd: str, only_available: bool = True) -> list[dict]:
        """Merge the three time-period responses into one slot per BeginTime.

        When a slot is reported both full and available, the available
        record wins (the upstream paginates by period and can be inconsistent).
        """
        await self.set_venue()
        results = await asyncio.gather(
            *(self._slots_for_period(dateadd, p) for p in ("0", "1", "2")),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, Exception)]
        if len(errors) == len(results):
            raise VenueError(f"获取时段失败: {errors[0]}")

        merged: dict[str, dict] = {}
        for batch in results:
            if isinstance(batch, Exception):
                continue
            for slot in batch:
                begin = str(slot.get("BeginTime") or "")
                if not begin:
                    continue
                state = str(slot.get("FieldState"))
                status = str(slot.get("TimeStatus"))
                is_free = state == "0" and status == "1"
                existing = merged.get(begin)
                if existing is None:
                    merged[begin] = slot
                else:
                    existing_free = (
                        str(existing.get("FieldState")) == "0"
                        and str(existing.get("TimeStatus")) == "1"
                    )
                    if is_free and not existing_free:
                        merged[begin] = slot
        slots = sorted(merged.values(), key=lambda s: str(s.get("BeginTime")))
        if only_available:
            slots = [
                s
                for s in slots
                if str(s.get("FieldState")) == "0" and str(s.get("TimeStatus")) == "1"
            ]
        return slots

    async def _fields_for_period(self, dateadd: str, period: str) -> list[dict]:
        resp = await self._post(
            "/Field/GetVenueStateNew",
            {
                "dateadd": dateadd,
                "TimePeriod": period,
                "VenueNo": settings.VENUE_NO,
                "FieldTypeNo": settings.FIELD_TYPE,
            },
        )
        data = self._json(resp)
        if not isinstance(data, dict):
            return []
        inner = data.get("resultdata")
        if isinstance(inner, str):
            if not inner.strip():
                return []
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError as exc:
                raise VenueError("场地列表解析失败") from exc
        if not isinstance(inner, list):
            return []
        return [f for f in inner if isinstance(f, dict)]

    async def get_fields(
        self, dateadd: str, begin_time: str, end_time: str, only_available: bool = True
    ) -> list[dict]:
        """Real field records for one slot — never guessed."""
        await self.set_venue()
        results = await asyncio.gather(
            *(self._fields_for_period(dateadd, p) for p in ("0", "1", "2")),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, Exception)]
        if len(errors) == len(results):
            raise VenueError(f"获取场地失败: {errors[0]}")

        seen: set[str] = set()
        fields: list[dict] = []
        for batch in results:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                if str(item.get("BeginTime") or "") != begin_time:
                    continue
                if str(item.get("EndTime") or "") != end_time:
                    continue
                if only_available and not (
                    str(item.get("FieldState")) == "0"
                    and str(item.get("TimeStatus")) == "1"
                ):
                    continue
                key = str(item.get("FieldNo") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                fields.append(item)
        fields.sort(key=lambda f: str(f.get("FieldName") or f.get("FieldNo")))
        return fields

    async def get_week_dates(self) -> list[str]:
        await self.set_venue()
        resp = await self._post(
            "/Field/GetWeek",
            {"VenueNo": settings.VENUE_NO, "FieldTypeNo": settings.FIELD_TYPE},
        )
        data = self._json(resp)
        items: Iterable[Any]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            inner = None
            for key in ("resultdata", "data", "list"):
                if key in data:
                    inner = data[key]
                    break
            if isinstance(inner, str) and inner.strip():
                try:
                    inner = json.loads(inner)
                except json.JSONDecodeError:
                    inner = None
            items = inner if isinstance(inner, list) else []
        else:
            items = []

        dates: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("Date") or "").strip()
            if not raw:
                continue
            # normalise "2026-11-02" -> "11-02"
            if len(raw) >= 10 and raw[4] == "-":
                raw = raw[5:]
            if len(raw) == 5 and raw[2] == "-":
                dates.append(raw)
        return dates

    # ---------------------------------------------------------------- ordering
    async def order_free(self, field: dict, dateadd: str) -> dict:
        field_no = str(field.get("FieldNo") or "")
        if not field_no:
            return {"success": False, "message": "场地编号缺失"}

        checkdata = json.dumps(
            [
                {
                    "FieldNo": field_no,
                    "FieldTypeNo": field.get("FieldTypeNo") or settings.FIELD_TYPE,
                    "FieldName": field.get("FieldName", ""),
                    "BeginTime": field.get("BeginTime", ""),
                    "Endtime": field.get("EndTime", ""),
                    "Price": field.get("FinalPrice") or field.get("Price") or "0",
                }
            ],
            ensure_ascii=False,
        )
        try:
            resp = await self._post(
                "/Field/OrderFieldFree",
                {
                    "checkdata": checkdata,
                    "dateadd": dateadd,
                    "VenueNo": settings.VENUE_NO,
                },
            )
        except VenueError as exc:
            return {"success": False, "message": str(exc)}

        text = resp.text or ""
        try:
            result = resp.json()
        except (json.JSONDecodeError, ValueError):
            return {"success": False, "message": text[:200] or "空响应"}
        if not isinstance(result, dict):
            return {"success": False, "message": text[:200]}
        message = str(result.get("message") or result.get("msg") or text[:200])
        success = str(result.get("type")) == "1" or result.get("success") is True
        return {"success": success, "message": message}


venue_client = VenueClient()
