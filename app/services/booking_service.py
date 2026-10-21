from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import HTTPException

from app.models.database import get_db
from app.models.schemas import BookingHistoryItem, MessageResponse, OrderResponse
from app.runtime import logger
from app.services.venue_client import VenueAuthError, VenueError, venue_client
from app.utils import compute_dateadd, parse_hhmm, parse_mmdd


class BookingService:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def order(
        self, date_str: str, begin_time: str, end_time: str, field_no: str
    ) -> OrderResponse:
        try:
            parse_mmdd(date_str)
            begin_h, begin_m = parse_hhmm(begin_time)
            end_h, end_m = parse_hhmm(end_time)
            if (end_h, end_m) <= (begin_h, begin_m):
                return OrderResponse(success=False, message="结束时间必须晚于开始时间")
            dateadd = compute_dateadd(date_str)
        except ValueError as exc:
            return OrderResponse(success=False, message=str(exc))

        key = f"{date_str}|{begin_time}|{field_no}"
        async with self._lock_for(key):
            if await self._recently_booked(date_str, begin_time, field_no):
                return OrderResponse(
                    success=True, message="该场地刚刚已预约成功，无需重复提交"
                )
            try:
                await venue_client.ensure_login()
                fields = await venue_client.get_fields(dateadd, begin_time, end_time)
            except VenueAuthError as exc:
                return OrderResponse(success=False, message=str(exc))
            except VenueError as exc:
                await self._save(None, field_no, field_no, date_str, begin_time, end_time,
                                 "failed", str(exc))
                return OrderResponse(success=False, message=str(exc))

            target = next((f for f in fields if str(f.get("FieldNo")) == field_no), None)
            if target is None:
                message = "该场地已不可预订（可能刚被占）"
                await self._save(None, field_no, field_no, date_str, begin_time, end_time,
                                 "failed", message)
                return OrderResponse(success=False, message=message)

            result = await venue_client.order_free(target, dateadd)
            field_name = str(target.get("FieldName") or field_no)
            await self._save(
                None,
                field_no,
                field_name,
                date_str,
                begin_time,
                end_time,
                "success" if result["success"] else "failed",
                result["message"],
            )
            logger.info(
                "手动预约 %s %s-%s %s -> %s",
                date_str, begin_time, end_time, field_name,
                "成功" if result["success"] else "失败",
            )
            return OrderResponse(success=result["success"], message=result["message"])

    async def _recently_booked(
        self, date_str: str, begin_time: str, field_no: str
    ) -> bool:
        """Guard against double-submit / double booking within the same minute."""
        db = await get_db()
        cursor = await db.execute(
            "SELECT COUNT(*) FROM booking_history "
            "WHERE date = ? AND begin_time = ? AND field_no = ? AND status = 'success' "
            "AND created_at >= datetime('now', 'localtime', '-60 seconds')",
            (date_str, begin_time, field_no),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return bool(row and row[0])

    async def get_history(self, limit: int = 50) -> list[BookingHistoryItem]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM booking_history ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            BookingHistoryItem(
                id=row["id"],
                task_id=row["task_id"],
                field_no=row["field_no"],
                field_name=row["field_name"],
                date=row["date"],
                begin_time=row["begin_time"],
                end_time=row["end_time"],
                status=row["status"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def _save(
        self,
        task_id: int | None,
        field_no: str,
        field_name: str,
        date_str: str,
        begin_time: str,
        end_time: str,
        status: str,
        message: str,
    ) -> None:
        db = await get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "INSERT INTO booking_history "
            "(task_id, field_no, field_name, date, begin_time, end_time, status, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, field_no, field_name, date_str, begin_time, end_time, status, message, now),
        )
        await db.commit()

    save_booking_record = _save

    async def delete_record(self, record_id: int) -> MessageResponse:
        db = await get_db()
        cursor = await db.execute("DELETE FROM booking_history WHERE id = ?", (record_id,))
        await db.commit()
        deleted = cursor.rowcount
        await cursor.close()
        if not deleted:
            raise HTTPException(status_code=404, detail="记录不存在")
        return MessageResponse(success=True, message=f"记录 #{record_id} 已删除")

    async def clear_history(self) -> MessageResponse:
        db = await get_db()
        await db.execute("DELETE FROM booking_history")
        await db.commit()
        return MessageResponse(success=True, message="预约记录已清空")


booking_service = BookingService()
