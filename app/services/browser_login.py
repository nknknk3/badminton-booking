"""In-app browser login.

Opens Edge/Chrome in app mode pointing at the school CAS login page, then
talks to it over the Chrome DevTools Protocol to read the venue cookies once
the user finishes the slider captcha. No external Python script needed.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import socket
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

try:  # bundled via uvicorn[standard]; imported here so PyInstaller sees it
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore[assignment]

from app.config import settings
from app.runtime import APP_ROOT, logger
from app.services.venue_client import read_cookie_file, venue_client

AUTH_SERVER = "https://ids.xidian.edu.cn"
VENUE_HOST = "gyytygyy.xidian.edu.cn"
LOGIN_TIMEOUT = 300.0
DEBUG_START_TIMEOUT = 60.0
DEBUG_DISCONNECT_GRACE = 12.0

# Already percent-encoded on purpose: it survives the CAS redirect chain.
SERVICE_URL = (
    "https://xxcapp.xidian.edu.cn/a_xidian/api/cas-login/index"
    "?redirect=https%3A%2F%2Fxxcapp.xidian.edu.cn%2Fuc%2Fapi%2Foauth%2Findex"
    "%3Fappid%3D200240927110038794%26redirect%3Dhttp%3A%2F%2Fgyytygyy.xidian.edu.cn"
    "%2FUser%2FQYLogin%26state%3DSTATE&from=wap"
)
LOGIN_URL = f"{AUTH_SERVER}/authserver/login?{urlencode({'service': SERVICE_URL})}"

# Browser profiles perform many small writes. Keep them on the user's local
# temporary drive rather than a potentially slow removable application drive.
PROFILE_DIR = Path(tempfile.gettempdir()) / "BadmintonBooking" / "login-profiles"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _purge_dir(path: Path) -> None:
    """Best-effort delete that can never take the whole app down.

    Some environments (sandboxes, AV hooks) turn cleanup into a hard exit;
    a leftover browser profile is harmless, a dead server is not.
    """
    resolved = path.resolve()
    if resolved.parent != PROFILE_DIR.resolve() or not resolved.name.startswith("login-"):
        logger.warning("拒绝清理非登录临时目录")
        return
    try:
        shutil.rmtree(path, ignore_errors=True)
    except BaseException:  # noqa: BLE001 - SystemExit included on purpose
        logger.debug("清理 %s 失败（忽略）", path, exc_info=True)


def _browser_exe() -> Path | None:
    import os

    bases = [
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    names = [
        ("Microsoft", "Edge", "Application", "msedge.exe"),
        ("Google", "Chrome", "Application", "chrome.exe"),
    ]
    for base in bases:
        if not base:
            continue
        for parts in names:
            candidate = Path(base).joinpath(*parts)
            if candidate.is_file():
                return candidate
    return None


class BrowserLogin:
    """One login attempt at a time, driven from the web UI."""

    def __init__(self) -> None:
        self.state = "idle"  # idle | starting | waiting | success | failed | cancelled
        self.message = ""
        self._proc: subprocess.Popen | None = None
        self._task: asyncio.Task | None = None
        self._port = 0
        self._lock = asyncio.Lock()
        self._profile: Path | None = None
        self._last_page_seen: float | None = None

    # ------------------------------------------------------------------ state
    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "message": self.message,
            "cookie_count": venue_client.cookie_count,
            "login_url": LOGIN_URL,
        }

    @property
    def busy(self) -> bool:
        return self.state in {"starting", "waiting"}

    # ------------------------------------------------------------------ start
    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self.busy:
                return self.snapshot()
            if self._task and not self._task.done():
                # A successful attempt still owns its profile during cleanup.
                await self._task

            exe = _browser_exe()
            if exe is None:
                self.state = "failed"
                self.message = "没有找到 Edge 或 Chrome，无法打开登录窗口"
                return self.snapshot()

            self.state = "starting"
            self.message = "正在打开登录窗口…"
            self._port = _free_port()
            self._last_page_seen = None

            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self._profile = Path(tempfile.mkdtemp(prefix="login-", dir=PROFILE_DIR))

            args = [
                str(exe),
                f"--app={LOGIN_URL}",
                f"--remote-debugging-port={self._port}",
                f"--user-data-dir={self._profile}",
                "--remote-debugging-address=127.0.0.1",
                "--disable-background-mode",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1180,880",
                "--window-position=160,70",
                "--disable-features=msEdgeSidebarV2,msEdgeCollections",
            ]
            try:
                self._proc = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                self.state = "failed"
                self.message = f"打开登录窗口失败: {exc}"
                await self._shutdown_browser()
                return self.snapshot()

            logger.info("登录窗口已启动（%s，CDP 端口 %s）", exe.name, self._port)
            self.state = "waiting"
            self.message = "请在弹出的窗口里完成登录（账号密码 + 滑块验证）"
            self._task = asyncio.create_task(self._watch())
            return self.snapshot()

    async def cancel(self) -> dict[str, Any]:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._shutdown_browser()
        self.state = "cancelled"
        self.message = "已取消登录"
        return self.snapshot()

    # ------------------------------------------------------------------ watch
    async def _watch(self) -> None:
        started = time.monotonic()
        deadline = started + LOGIN_TIMEOUT
        try:
            while time.monotonic() < deadline:
                # Edge can relaunch itself (e.g. compatibility mode). The Popen
                # process is only a launcher; CDP pages own the login lifetime.
                page = await self._find_venue_page()
                now = time.monotonic()
                if self._last_page_seen is not None and now - self._last_page_seen > DEBUG_DISCONNECT_GRACE:
                    self.state = "failed"
                    self.message = "与登录窗口的连接已中断，请重新点击一键登录"
                    logger.warning("登录窗口 CDP 连续不可用超过 %.0f 秒", DEBUG_DISCONNECT_GRACE)
                    return
                if self._last_page_seen is None and now - started > DEBUG_START_TIMEOUT:
                    self.state = "failed"
                    self.message = "无法连接登录窗口的调试接口，请取消后重试或导入 session 文件"
                    logger.warning("登录窗口 CDP 启动超时，端口 %s", self._port)
                    return
                if page is not None:
                    cookies = await self._read_cookies(page["webSocketDebuggerUrl"])
                    if cookies:
                        try:
                            ok = await venue_client.check_login(cookies)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("登录后校验异常: %s", exc)
                            ok = False
                        if ok:
                            await self._persist(cookies)
                            self.state = "success"
                            self.message = f"登录成功，已导入 {len(cookies)} 条 cookie"
                            logger.info("浏览器登录成功 (%d cookies)", len(cookies))
                            return
                        self.message = "正在等待场馆认证完成；如显示用户类型选择，请在登录窗口中完成选择"

                await asyncio.sleep(1.0)

            self.state = "failed"
            self.message = "等待登录超时（5 分钟），请重试"
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001 - keep the server alive
            logger.exception("登录流程异常")
            self.state = "failed"
            self.message = f"登录流程异常: {exc}"
        finally:
            await self._shutdown_browser()

    async def _find_venue_page(self) -> dict | None:
        url = f"http://127.0.0.1:{self._port}/json/list"
        try:
            # This endpoint is plain HTTP on loopback. Avoid loading the CA
            # bundle from the application drive on every monitoring tick.
            async with httpx.AsyncClient(timeout=2.0, trust_env=False, verify=False) as client:
                resp = await client.get(url)
                targets = resp.json()
        except Exception:
            return None
        if not isinstance(targets, list):
            return None
        if any(isinstance(target, dict) and target.get("type") == "page" for target in targets):
            self._last_page_seen = time.monotonic()
        for target in targets:
            if not isinstance(target, dict) or target.get("type") != "page":
                continue
            page_url = str(target.get("url") or "")
            if urlparse(page_url).hostname == VENUE_HOST and target.get("webSocketDebuggerUrl"):
                return target
        return None

    async def _read_cookies(self, ws_url: str) -> list[dict]:
        if websockets is None:
            logger.warning("缺少 websockets 库，无法读取 cookie")
            return []

        try:
            async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=8)
                    payload = json.loads(raw)
                    if payload.get("id") != 1:
                        continue
                    cookies = (payload.get("result") or {}).get("cookies") or []
                    return [
                        {
                            "name": c.get("name", ""),
                            "value": c.get("value", ""),
                            "domain": c.get("domain", VENUE_HOST),
                            "path": c.get("path", "/"),
                            "httpOnly": bool(c.get("httpOnly", False)),
                            "secure": bool(c.get("secure", False)),
                        }
                        for c in cookies
                        if (str(c.get("domain", "")).lstrip(".") == VENUE_HOST
                            or VENUE_HOST.endswith("." + str(c.get("domain", "")).lstrip(".")))
                        and c.get("name")
                    ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取 cookie 失败: %s", exc)
            return []

    async def _persist(self, cookies: list[dict]) -> None:
        payload = {
            "final_url": f"https://{VENUE_HOST}/",
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "in-app-login",
            "cookies": cookies,
        }
        target = Path(settings.COOKIE_FILE)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(target)
        except OSError as exc:
            raise RuntimeError(f"保存登录会话失败: {exc}") from exc
        await venue_client.reload_cookies()

    async def _shutdown_browser(self) -> None:
        # Close the browser that owns our dedicated CDP port, including after
        # an Edge relaunch has already terminated the original launcher PID.
        await self._close_debug_browser()
        proc = self._proc
        self._proc = None
        if proc is not None and proc.poll() is None:
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                )
            except BaseException:  # noqa: BLE001
                try:
                    proc.terminate()
                except Exception:
                    pass
        await asyncio.sleep(0.3)
        profile = self._profile
        self._profile = None
        if profile:
            await asyncio.to_thread(_purge_dir, profile)
        try:
            read_cookie_file()
        except ValueError:
            pass

    async def _close_debug_browser(self) -> None:
        if not self._port or websockets is None:
            return
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False, verify=False) as client:
                response = await client.get(f"http://127.0.0.1:{self._port}/json/version")
                ws_url = response.json().get("webSocketDebuggerUrl", "")
            parsed = urlparse(ws_url)
            if parsed.hostname != "127.0.0.1" or parsed.port != self._port:
                return
            async with websockets.connect(ws_url, open_timeout=2, close_timeout=1) as ws:
                await ws.send(json.dumps({"id": 2, "method": "Browser.close"}))
        except Exception:
            logger.debug("登录浏览器调试连接已关闭", exc_info=True)


browser_login = BrowserLogin()
