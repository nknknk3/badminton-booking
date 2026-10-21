from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import DatesResponse, FieldsResponse, SlotsResponse
from app.services.venue_service import venue_service
from app.utils import parse_hhmm, parse_mmdd

router = APIRouter(prefix="/api/venues", tags=["venues"])


@router.get("/dates", response_model=DatesResponse)
async def get_dates() -> DatesResponse:
    return await venue_service.dates()


@router.get("/slots", response_model=SlotsResponse)
async def get_slots(
    date: str = Query(..., description="MM-DD"),
    all: bool = Query(default=False, description="包含不可订时段"),
) -> SlotsResponse:
    try:
        parse_mmdd(date)
    except ValueError as exc:
        return SlotsResponse(date=date, error=str(exc))
    return await venue_service.slots(date, include_unavailable=all)


@router.get("/fields", response_model=FieldsResponse)
async def get_fields(
    date: str = Query(..., description="MM-DD"),
    begin_time: str = Query(...),
    end_time: str = Query(...),
) -> FieldsResponse:
    try:
        parse_mmdd(date)
        parse_hhmm(begin_time)
        parse_hhmm(end_time)
    except ValueError as exc:
        return FieldsResponse(error=str(exc))
    return await venue_service.fields(date, begin_time, end_time)
