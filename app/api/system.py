from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.config import save_overrides, settings
from app.models.schemas import RuntimeSettings, SystemInfo
from app.runtime import APP_ROOT, is_frozen
from app.lifecycle import shutdown_requested

router = APIRouter(prefix="/api/system", tags=["system"])
VERSION = "2.1.1"


@router.post("/shutdown")
async def shutdown(request: Request) -> dict:
    if (not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}
            or request.headers.get("x-desktop-action") != "shutdown"):
        raise HTTPException(status_code=403, detail="只能从本机界面退出服务")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="请求来源无效")
    asyncio.get_running_loop().call_later(0.3, shutdown_requested.set)
    return {"success": True, "message": "正在退出整个服务"}


def _current() -> RuntimeSettings:
    return RuntimeSettings(
        default_poll_interval=float(settings.DEFAULT_POLL_INTERVAL),
        lead_minutes=int(settings.BOOKING_OPEN_LEAD_MINUTES),
        max_runtime_hours=float(settings.MAX_RUNTIME_HOURS),
    )


@router.get("/info", response_model=SystemInfo)
async def info() -> SystemInfo:
    return SystemInfo(
        version=VERSION,
        frozen=is_frozen(),
        venue_no=settings.VENUE_NO,
        field_type=settings.FIELD_TYPE,
        auth_required=bool(settings.ACCESS_TOKEN),
        poll_default=settings.DEFAULT_POLL_INTERVAL,
        lead_minutes=settings.BOOKING_OPEN_LEAD_MINUTES,
        max_runtime_hours=settings.MAX_RUNTIME_HOURS,
        data_dir=str(APP_ROOT),
    )


@router.get("/settings", response_model=RuntimeSettings)
async def get_settings() -> RuntimeSettings:
    return _current()


@router.put("/settings", response_model=RuntimeSettings)
async def update_settings(body: RuntimeSettings) -> RuntimeSettings:
    save_overrides(
        {
            "DEFAULT_POLL_INTERVAL": body.default_poll_interval,
            "BOOKING_OPEN_LEAD_MINUTES": body.lead_minutes,
            "MAX_RUNTIME_HOURS": body.max_runtime_hours,
        }
    )
    return _current()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": VERSION}
