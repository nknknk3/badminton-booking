from __future__ import annotations

from datetime import date, timedelta

from app.runtime import logger
from app.services.venue_client import VenueError, venue_client
from app.utils import compute_dateadd, next_days, resolve_date
from app.models.schemas import DatesResponse, FieldInfo, FieldsResponse, SlotInfo, SlotsResponse

# Booking window shown in the UI (days including today).
VISIBLE_DAYS = 7


def _to_int(value, default: int = -1) -> int:
    """0 must survive — never use `value or default` here."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _slot_info(slot: dict) -> SlotInfo:
    return SlotInfo(
        begin_time=str(slot.get("BeginTime") or ""),
        end_time=str(slot.get("EndTime") or ""),
        field_state=_to_int(slot.get("FieldState")),
        time_status=_to_int(slot.get("TimeStatus")),
    )


class VenueService:
    async def dates(self) -> DatesResponse:
        today = date.today()
        limit = today + timedelta(days=VISIBLE_DAYS - 1)
        candidates = list(next_days(VISIBLE_DAYS, today))
        error: str | None = None
        try:
            candidates += await venue_client.get_week_dates()
        except VenueError as exc:
            logger.warning("获取场馆日期失败: %s", exc)
            error = str(exc)

        resolved: dict[str, date] = {}
        for mmdd in candidates:
            try:
                day = resolve_date(mmdd, today)
            except ValueError:
                continue
            if today <= day <= limit:
                resolved.setdefault(mmdd, day)
        ordered = sorted(resolved.items(), key=lambda kv: kv[1])
        return DatesResponse(dates=[mmdd for mmdd, _ in ordered], error=error)

    async def slots(self, mmdd: str, include_unavailable: bool = False) -> SlotsResponse:
        try:
            dateadd = compute_dateadd(mmdd)
        except ValueError as exc:
            return SlotsResponse(date=mmdd, error=str(exc))
        try:
            raw = await venue_client.get_slots(dateadd, only_available=not include_unavailable)
        except VenueError as exc:
            return SlotsResponse(date=mmdd, error=str(exc))
        return SlotsResponse(date=mmdd, slots=[_slot_info(s) for s in raw])

    async def fields(self, mmdd: str, begin_time: str, end_time: str) -> FieldsResponse:
        try:
            dateadd = compute_dateadd(mmdd)
        except ValueError as exc:
            return FieldsResponse(error=str(exc))
        try:
            raw = await venue_client.get_fields(dateadd, begin_time, end_time)
        except VenueError as exc:
            return FieldsResponse(error=str(exc))
        return FieldsResponse(
            fields=[
                FieldInfo(
                    field_no=str(f.get("FieldNo") or ""),
                    field_name=str(f.get("FieldName") or ""),
                    field_type_no=str(f.get("FieldTypeNo") or ""),
                    begin_time=str(f.get("BeginTime") or ""),
                    end_time=str(f.get("EndTime") or ""),
                    price=str(f.get("FinalPrice") or f.get("Price") or ""),
                    field_state=_to_int(f.get("FieldState")),
                    time_status=_to_int(f.get("TimeStatus")),
                )
                for f in raw
                if f.get("FieldNo")
            ]
        )


venue_service = VenueService()
