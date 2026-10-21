from __future__ import annotations

import asyncio
import json
import random
from datetime import date, datetime, timedelta

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.models.database import get_db
from app.runtime import logger
from app.services.notification import send_notification
from app.services.venue_client import VenueAuthError, VenueError, venue_client
from app.utils import compute_dateadd, parse_hhmm, parse_start_at, resolve_date

TS_FMT = "%Y-%m-%d %H:%M:%S"


def _now() -> datetime:
    return datetime.now()


class TaskScheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._cancelled: set[int] = set()
        self._active: set[int] = set()

    # ------------------------------------------------------------------ infra
    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._scheduler

    def start(self) -> None:
        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("调度器已启动")

    def shutdown(self) -> None:
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False

    def compute_run_time(
        self, target_date: str, target_times: list[str], start_at: str | None
    ) -> datetime:
        """Explicit start_at wins; otherwise wake up before the earliest slot opens."""
        now = _now()
        explicit = parse_start_at(start_at)
        if explicit is not None:
            return explicit if explicit > now else now + timedelta(seconds=2)

        try:
            day = resolve_date(target_date)
            times = sorted(parse_hhmm(t) for t in target_times)
        except ValueError:
            return now + timedelta(seconds=2)
        if not times:
            return now + timedelta(seconds=2)

        hour, minute = times[0]
        first_slot = datetime(day.year, day.month, day.day, hour, minute)
        run_at = first_slot - timedelta(minutes=settings.BOOKING_OPEN_LEAD_MINUTES)
        return run_at if run_at > now else now + timedelta(seconds=2)

    def add_task(
        self,
        task_id: int,
        target_date: str,
        target_times: list[str],
        poll_interval: float = 3.0,
        start_at: str | None = None,
    ) -> datetime:
        self._cancelled.discard(task_id)
        job_id = f"booking_task_{task_id}"
        run_time = self.compute_run_time(target_date, target_times, start_at)
        self._scheduler.add_job(
            self._run,
            trigger="date",
            run_date=run_time,
            id=job_id,
            args=[task_id, target_date, target_times, poll_interval],
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
        )
        logger.info("任务 #%s 计划于 %s 启动", task_id, run_time.strftime(TS_FMT))
        return run_time

    def remove_task(self, task_id: int) -> None:
        self._cancelled.add(task_id)
        try:
            self._scheduler.remove_job(f"booking_task_{task_id}")
        except JobLookupError:
            pass

    def next_run_at(self, task_id: int) -> str | None:
        job = self._scheduler.get_job(f"booking_task_{task_id}")
        if job is None or job.next_run_time is None:
            return None
        return job.next_run_time.replace(tzinfo=None).strftime(TS_FMT)

    async def restore_tasks(self) -> None:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM booking_tasks WHERE enabled = 1 AND status IN ('pending', 'running')"
        )
        rows = await cursor.fetchall()
        await cursor.close()
        restored = 0
        for row in rows:
            try:
                times = json.loads(row["target_times"])
                if not isinstance(times, list) or not times:
                    raise ValueError("target_times 为空")
                target_day = resolve_date(row["target_date"])
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                logger.warning("任务 #%s 数据损坏，标记为失效: %s", row["id"], exc)
                await self._set_status(row["id"], "failed")
                continue
            if target_day < date.today():
                await self._set_status(row["id"], "expired")
                continue
            self.add_task(
                row["id"],
                row["target_date"],
                times,
                float(row["poll_interval"] or settings.DEFAULT_POLL_INTERVAL),
                row["start_at"],
            )
            restored += 1
        logger.info("恢复任务 %d/%d", restored, len(rows))

    # ------------------------------------------------------------------- job
    async def _run(
        self, task_id: int, target_date: str, target_times: list[str], poll_interval: float
    ) -> None:
        if task_id in self._active:
            logger.warning("任务 #%s 已在运行，跳过重复触发", task_id)
            return
        self._active.add(task_id)
        try:
            await self._execute(task_id, target_date, target_times, poll_interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never let a job die silently
            logger.exception("任务 #%s 异常退出: %s", task_id, exc)
            await self._set_status(task_id, "failed")
            await send_notification("抢场任务异常", f"任务 #{task_id}: {exc}")
        finally:
            self._active.discard(task_id)

    async def _execute(
        self, task_id: int, target_date: str, target_times: list[str], poll_interval: float
    ) -> None:
        poll = max(float(poll_interval or settings.DEFAULT_POLL_INTERVAL), settings.MIN_POLL_INTERVAL)

        try:
            dateadd = compute_dateadd(target_date)
            target_day = resolve_date(target_date)
        except ValueError as exc:
            logger.warning("任务 #%s 参数无效: %s", task_id, exc)
            await self._set_status(task_id, "failed")
            return

        wanted: list[str] = []
        for item in target_times:
            try:
                parse_hhmm(item)
            except ValueError:
                logger.warning("任务 #%s 忽略非法时段 %r", task_id, item)
                continue
            if item not in wanted:
                wanted.append(item)
        wanted.sort()
        if not wanted:
            await self._set_status(task_id, "failed")
            return

        # Already booked in a previous run? (survives restarts)
        done = await self._booked_times(task_id, target_date)
        remaining = set(wanted) - done
        if not remaining:
            await self._set_status(task_id, "completed")
            return

        # All target slots are already in the past -> nothing to wait for
        if target_day == date.today():
            now_hm = _now().strftime("%H:%M")
            if all(t < now_hm for t in remaining):
                logger.info("任务 #%s 所有目标时段已过，标记失效", task_id)
                await self._set_status(task_id, "expired")
                return

        try:
            await venue_client.ensure_login()
        except VenueAuthError as exc:
            await self._set_status(task_id, "failed")
            await send_notification("抢场任务失败", f"任务 #{task_id}: {exc}")
            return
        except VenueError as exc:
            logger.warning("任务 #%s 登录校验异常: %s", task_id, exc)

        await self._set_status(task_id, "running")
        deadline = _now() + timedelta(hours=float(settings.MAX_RUNTIME_HOURS))
        logger.info(
            "任务 #%s 开始运行 目标 %s 时段 %s 间隔 %.1fs 截止 %s",
            task_id, target_date, wanted, poll, deadline.strftime("%H:%M:%S"),
        )

        while _now() < deadline:
            if task_id in self._cancelled:
                await self._set_status(task_id, "stopped")
                return

            try:
                slots = await venue_client.get_slots(dateadd, only_available=True)
            except VenueError as exc:
                logger.warning("任务 #%s 轮询失败: %s", task_id, exc)
                await self._sleep(poll)
                continue

            available = {str(s.get("BeginTime") or "") for s in slots}
            matched = sorted(available & remaining)

            for begin_time in matched[: settings.MAX_SLOTS_PER_TASK]:
                if task_id in self._cancelled:
                    await self._set_status(task_id, "stopped")
                    return
                slot = next((s for s in slots if str(s.get("BeginTime")) == begin_time), None)
                end_time = str(slot.get("EndTime") or "") if slot else ""
                if not end_time:
                    continue

                try:
                    fields = await venue_client.get_fields(dateadd, begin_time, end_time)
                except VenueError as exc:
                    logger.warning("任务 #%s 获取场地失败 %s: %s", task_id, begin_time, exc)
                    continue

                for field in fields[:2]:  # at most two courts per slot
                    field_no = str(field.get("FieldNo") or "")
                    field_name = str(field.get("FieldName") or field_no)
                    result = await venue_client.order_free(field, dateadd)
                    await self._save_history(
                        task_id, field_no, field_name, target_date, begin_time, end_time,
                        "success" if result["success"] else "failed", result["message"],
                    )
                    if result["success"]:
                        remaining.discard(begin_time)
                        await send_notification(
                            f"预订成功：{field_name}",
                            f"日期：{target_date}<br>时间：{begin_time}-{end_time}<br>场地：{field_name}",
                        )
                        logger.info(
                            "任务 #%s 抢到 %s %s-%s", task_id, field_name, begin_time, end_time
                        )
                        break

            if not remaining:
                await self._set_status(task_id, "completed")
                return

            await self._sleep(poll)

        await self._set_status(task_id, "exhausted")
        await send_notification(
            "抢场任务超时",
            f"任务 #{task_id} 运行 {settings.MAX_RUNTIME_HOURS} 小时后仍未全部抢到，剩余时段：{', '.join(sorted(remaining))}",
        )

    @staticmethod
    async def _sleep(poll: float) -> None:
        """Jittered sleep — never negative, even for tiny poll intervals."""
        await asyncio.sleep(max(0.3, poll * random.uniform(0.85, 1.25)))

    # --------------------------------------------------------------- storage
    async def _set_status(self, task_id: int, status: str) -> None:
        db = await get_db()
        now = _now().strftime(TS_FMT)
        if status in {"completed", "failed", "stopped", "expired", "exhausted"}:
            await db.execute(
                "UPDATE booking_tasks SET status = ?, enabled = 0, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )
        else:
            await db.execute(
                "UPDATE booking_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )
        await db.commit()

    async def _booked_times(self, task_id: int, target_date: str) -> set[str]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT DISTINCT begin_time FROM booking_history "
            "WHERE task_id = ? AND date = ? AND status = 'success'",
            (task_id, target_date),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return {row["begin_time"] for row in rows}

    async def _save_history(
        self,
        task_id: int,
        field_no: str,
        field_name: str,
        date_str: str,
        begin_time: str,
        end_time: str,
        status: str,
        message: str,
    ) -> None:
        db = await get_db()
        await db.execute(
            "INSERT INTO booking_history "
            "(task_id, field_no, field_name, date, begin_time, end_time, status, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, field_no, field_name, date_str, begin_time, end_time, status,
                message, _now().strftime(TS_FMT),
            ),
        )
        await db.commit()


task_scheduler = TaskScheduler()
