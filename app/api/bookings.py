from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import BookingHistoryItem, MessageResponse, OrderRequest, OrderResponse
from app.services.booking_service import booking_service

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("/order", response_model=OrderResponse)
async def place_order(body: OrderRequest) -> OrderResponse:
    return await booking_service.order(
        date_str=body.date,
        begin_time=body.begin_time,
        end_time=body.end_time,
        field_no=body.field_no,
    )


@router.get("/history", response_model=list[BookingHistoryItem])
async def get_history(limit: int = Query(default=50, ge=1, le=500)) -> list[BookingHistoryItem]:
    return await booking_service.get_history(limit=limit)


@router.delete("/history/{record_id}", response_model=MessageResponse)
async def delete_history_item(record_id: int) -> MessageResponse:
    return await booking_service.delete_record(record_id)


@router.delete("/history", response_model=MessageResponse)
async def clear_history() -> MessageResponse:
    return await booking_service.clear_history()
