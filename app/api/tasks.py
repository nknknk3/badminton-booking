from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.database import get_db
from app.models.schemas import MessageResponse, TaskCreate, TaskResponse, TaskUpdate
from app.services.scheduler import task_scheduler
from app.utils import parse_hhmm, parse_mmdd, parse_start_at

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

TS_FMT = "%Y-%m-%d %H:%M:%S"
TERMINAL = {"completed", "failed", "stopped", "expired", "exhausted"}


def _row_to_task(row) -> TaskResponse:
    try:
        times = json.loads(row["target_times"])
    except (TypeError, json.JSONDecodeError):
        times = []
    return TaskResponse(
        id=row["id"],
        name=row["name"],
        target_date=row["target_date"],
        target_times=times if isinstance(times, list) else [],
        poll_interval=float(row["poll_interval"] or settings.DEFAULT_POLL_INTERVAL),
        start_at=row["start_at"],
        enabled=bool(row["enabled"]),
        status=row["status"],
        next_run_at=task_scheduler.next_run_at(row["id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _clean_times(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        parse_hhmm(value)
        if value not in cleaned:
            cleaned.append(value)
    if not cleaned:
        raise HTTPException(status_code=400, detail="请至少选择一个时段")
    if len(cleaned) > 12:
        raise HTTPException(status_code=400, detail="单个任务最多 12 个时段")
    return sorted(cleaned)


def _clean_interval(value: float) -> float:
    value = float(value)
    if value < settings.MIN_POLL_INTERVAL or value > settings.MAX_POLL_INTERVAL:
        raise HTTPException(
            status_code=400,
            detail=f"轮询间隔需在 {settings.MIN_POLL_INTERVAL}–{settings.MAX_POLL_INTERVAL} 秒之间",
        )
    return round(value, 2)


async def _fetch(task_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM booking_tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return row


@router.get("", response_model=list[TaskResponse])
async def list_tasks() -> list[TaskResponse]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM booking_tasks ORDER BY id DESC")
    rows = await cursor.fetchall()
    await cursor.close()
    return [_row_to_task(row) for row in rows]


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(body: TaskCreate) -> TaskResponse:
    try:
        parse_mmdd(body.target_date)
        parse_start_at(body.start_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    times = _clean_times(body.target_times)
    interval = _clean_interval(body.poll_interval)

    db = await get_db()
    # Reject obvious duplicate tasks that could double-book the same slot.
    cursor = await db.execute(
        "SELECT * FROM booking_tasks WHERE enabled = 1 AND status IN ('pending', 'running')"
    )
    for row in await cursor.fetchall():
        if row["target_date"] != body.target_date:
            continue
        try:
            existing = set(json.loads(row["target_times"]))
        except (TypeError, json.JSONDecodeError):
            continue
        overlap = existing & set(times)
        if overlap:
            await cursor.close()
            raise HTTPException(
                status_code=409,
                detail=f"已存在任务 #{row['id']} 占用时段 {', '.join(sorted(overlap))}，请勿重复创建",
            )
    await cursor.close()

    now = datetime.now().strftime(TS_FMT)
    cursor = await db.execute(
        "INSERT INTO booking_tasks "
        "(name, target_date, target_times, poll_interval, start_at, enabled, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 1, 'pending', ?, ?)",
        (
            body.name.strip(),
            body.target_date,
            json.dumps(times, ensure_ascii=False),
            interval,
            body.start_at,
            now,
            now,
        ),
    )
    await db.commit()
    task_id = cursor.lastrowid
    await cursor.close()

    task_scheduler.add_task(
        task_id, body.target_date, times, interval, body.start_at
    )
    return _row_to_task(await _fetch(task_id))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int) -> TaskResponse:
    return _row_to_task(await _fetch(task_id))


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, body: TaskUpdate) -> TaskResponse:
    row = await _fetch(task_id)

    fields_set = body.model_fields_set
    name = (body.name or row["name"]).strip() or row["name"]
    if body.target_times is not None:
        times = _clean_times(body.target_times)
    else:
        try:
            times = json.loads(row["target_times"])
            if not isinstance(times, list) or not times:
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="任务时段数据已损坏，请重建任务")
    interval = (
        _clean_interval(body.poll_interval)
        if body.poll_interval is not None
        else float(row["poll_interval"] or settings.DEFAULT_POLL_INTERVAL)
    )
    start_at = body.start_at if "start_at" in fields_set else row["start_at"]
    if start_at:
        try:
            parse_start_at(start_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    enabled = bool(body.enabled) if body.enabled is not None else bool(row["enabled"])
    status = row["status"]
    if enabled and status in TERMINAL:
        status = "pending"

    now = datetime.now().strftime(TS_FMT)
    db = await get_db()
    await db.execute(
        "UPDATE booking_tasks SET name = ?, target_times = ?, poll_interval = ?, "
        "start_at = ?, enabled = ?, status = ?, updated_at = ? WHERE id = ?",
        (
            name,
            json.dumps(times, ensure_ascii=False),
            interval,
            start_at,
            int(enabled),
            status,
            now,
            task_id,
        ),
    )
    await db.commit()

    if enabled:
        task_scheduler.remove_task(task_id)
        task_scheduler.add_task(task_id, row["target_date"], times, interval, start_at)
    else:
        task_scheduler.remove_task(task_id)

    return _row_to_task(await _fetch(task_id))


@router.delete("/{task_id}", response_model=MessageResponse)
async def delete_task(task_id: int) -> MessageResponse:
    await _fetch(task_id)
    task_scheduler.remove_task(task_id)
    db = await get_db()
    await db.execute("DELETE FROM booking_tasks WHERE id = ?", (task_id,))
    await db.commit()
    return MessageResponse(success=True, message=f"任务 #{task_id} 已删除")
