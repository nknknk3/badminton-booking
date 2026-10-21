from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.bookings import router as bookings_router
from app.api.system import router as system_router
from app.api.tasks import router as tasks_router
from app.api.venues import router as venues_router
from app.config import settings
from app.models.database import close_db, init_db
from app.runtime import FRONTEND_DIR, ensure_dirs, logger
from app.services.scheduler import task_scheduler
from app.services.venue_client import venue_client

FRONTEND_AVAILABLE = (FRONTEND_DIR / "index.html").is_file()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    await init_db()
    await venue_client.start()
    task_scheduler.start()
    await task_scheduler.restore_tasks()

    public_url = None
    if settings.ENABLE_TUNNEL:
        try:
            from pyngrok import ngrok

            if not settings.NGROK_AUTH_TOKEN:
                logger.warning("未配置 ngrok token，隧道未启动")
            else:
                ngrok.set_auth_token(settings.NGROK_AUTH_TOKEN)
                tunnel = ngrok.connect(settings.PORT, "http")
                public_url = tunnel.public_url
                logger.info("公网地址: %s", public_url)
                if not settings.ACCESS_TOKEN:
                    logger.warning(
                        "当前未设置访问令牌，公网地址任何人可访问。"
                        "建议在 config.json 里配置 ACCESS_TOKEN。"
                    )
        except Exception as exc:
            logger.warning("隧道启动失败: %s", exc)

    logger.info("后端已启动，监听 %s:%s", settings.HOST, settings.PORT)
    try:
        yield
    finally:
        task_scheduler.shutdown()
        try:
            from app.services.browser_login import browser_login

            if browser_login.busy:
                await browser_login.cancel()
        except Exception:
            pass
        await venue_client.close()
        await close_db()
        if public_url:
            try:
                from pyngrok import ngrok

                ngrok.disconnect(public_url)
            except Exception:
                pass


app = FastAPI(
    title="羽毛球场地预约助手",
    version="2.1.1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

_allow_credentials = "*" not in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # "*" together with credentials is invalid per spec and makes browsers
    # reject every response — only enable it for explicit origins.
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def access_guard(request: Request, call_next):
    """Optional shared-token gate for /api/* (off when ACCESS_TOKEN is empty)."""
    if settings.ACCESS_TOKEN and request.url.path.startswith("/api"):
        supplied = (
            request.headers.get("x-access-token")
            or request.query_params.get("token")
            or ""
        )
        if supplied != settings.ACCESS_TOKEN:
            return JSONResponse(
                {"detail": "访问令牌无效或缺失"}, status_code=401
            )
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("未处理异常 %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse({"detail": f"服务器内部错误: {exc}"}, status_code=500)


app.include_router(system_router)
app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(bookings_router)
app.include_router(tasks_router)


def _safe_file(full_path: str) -> Path | None:
    """Resolve a request path inside frontend/dist, refusing traversal."""
    if not full_path or "\x00" in full_path:
        return None
    base = FRONTEND_DIR.resolve()
    try:
        candidate = (base / full_path).resolve()
    except (OSError, ValueError):
        return None
    if candidate == base or not candidate.is_relative_to(base):
        return None
    return candidate if candidate.is_file() else None


if FRONTEND_AVAILABLE:
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith(("api/", "api")):
            return JSONResponse({"detail": "接口不存在"}, status_code=404)
        found = _safe_file(full_path)
        if found is not None:
            return FileResponse(found)
        if os.path.splitext(full_path)[1]:
            # Looks like a static asset request — do not mask it with index.html
            return JSONResponse({"detail": "资源不存在"}, status_code=404)
        return FileResponse(FRONTEND_DIR / "index.html")

else:

    @app.get("/", include_in_schema=False)
    async def root_fallback():
        return {
            "status": "ok",
            "note": "前端尚未构建，请运行 cd frontend && npm run build",
        }
