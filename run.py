"""羽毛球场地预约助手 — 启动入口。

默认以**桌面窗口**打开（原生 WebView2 窗口，没有浏览器地址栏）。
    python run.py

其它模式：
    python run.py --browser      # 强制用系统浏览器
    python run.py --headless     # 只跑服务，不打开界面
    python run.py --tunnel       # 叠加 ngrok 内网穿透
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
from urllib.parse import urlencode


def _ensure_stdio() -> None:
    """A --noconsole exe may hand us a GBK stream or no stream at all.

    Both cases used to break startup: printing a non-GBK character (or writing
    to None) raised before the window was ever created.
    """
    if sys.stdout is None or sys.stderr is None:
        try:
            from app.runtime import LOG_DIR

            LOG_DIR.mkdir(parents=True, exist_ok=True)
            fallback = open(  # noqa: SIM115 - lives for the whole process
                LOG_DIR / "console.log", "a", encoding="utf-8", buffering=1
            )
        except OSError:
            fallback = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        if sys.stdout is None:
            sys.stdout = fallback
        if sys.stderr is None:
            sys.stderr = fallback

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def _fatal(message: str) -> None:
    try:
        from app.runtime import logger

        logger.exception(message)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "羽毛球预约助手 - 启动失败", 0x10)
        except Exception:
            pass


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port(preferred: int, span: int = 20) -> int:
    for port in range(preferred, preferred + span):
        if _port_free(port):
            return port
    return preferred


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.15)
    return False


def main() -> None:
    _ensure_stdio()

    parser = argparse.ArgumentParser(description="羽毛球场地预约助手")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    parser.add_argument("--host", default=None, help="监听地址")
    parser.add_argument("--tunnel", action="store_true", help="启动 ngrok 内网穿透")
    parser.add_argument("--token", default=None, help="设置访问令牌")
    parser.add_argument("--browser", action="store_true", help="用系统浏览器打开")
    parser.add_argument("--headless", "--no-browser", dest="headless", action="store_true",
                        help="只启动服务，不打开任何界面")
    parser.add_argument("--reload", action="store_true", help="开发模式自动重载")
    parser.add_argument("--build-frontend", action="store_true", help="启动前构建前端")
    parser.add_argument("--window-mode", default=None, choices=["auto", "window", "browser"],
                        help="窗口后端：auto / window / browser")
    args = parser.parse_args()

    if args.build_frontend:
        import subprocess

        from app.runtime import APP_ROOT

        frontend = APP_ROOT / "frontend"
        if frontend.is_dir():
            print("正在构建前端...")
            subprocess.run(["cmd", "/c", "npm run build"], cwd=frontend, check=False)

    if args.tunnel:
        os.environ["ENABLE_TUNNEL"] = "1"
    if args.token:
        os.environ["ACCESS_TOKEN"] = args.token
    if args.host:
        os.environ["HOST"] = args.host

    import uvicorn

    from app.config import settings
    from app.desktop import window_backend
    from app.main import app as fastapi_app

    host = settings.HOST
    port = args.port or settings.PORT
    if not args.reload:
        picked = pick_port(port)
        if picked != port:
            print(f"端口 {port} 被占用，改用 {picked}")
        port = picked
    settings.PORT = port

    url = f"http://{'127.0.0.1' if host in {'0.0.0.0', '::'} else host}:{port}"
    ui_url = f"{url}/?{urlencode({'token': settings.ACCESS_TOKEN})}" if settings.ACCESS_TOKEN else url

    # ---- server runs in a background thread, the UI owns the main thread ----
    if args.reload:
        # uvicorn's reloader needs the main thread; UI is started by the browser helper.
        if args.browser and not args.headless:
            threading.Timer(2.0, lambda: __import__("webbrowser").open(ui_url)).start()
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
            access_log=False,
        )
        return

    config = uvicorn.Config(
        fastapi_app, host=host, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    from app.lifecycle import shutdown_requested
    shutdown_requested.clear()

    def stop_server() -> None:
        shutdown_requested.wait()
        server.should_exit = True

    threading.Thread(target=stop_server, name="shutdown", daemon=True).start()
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()

    if not wait_for_server(port):
        _fatal("服务启动超时，请查看 logs/app.log")
        raise SystemExit(1)

    from app.runtime import logger

    logger.info("服务已就绪: %s", url)

    mode = "browser" if args.browser else ("none" if args.headless else (args.window_mode or "auto"))
    if not settings.OPEN_BROWSER and mode == "auto":
        mode = "none"
    args.headless = mode == "none"
    try:
        if args.headless:
            while thread.is_alive() and not shutdown_requested.wait(0.25):
                pass
        else:
            from app.desktop import launch
            launch(ui_url, mode)
    finally:
        shutdown_requested.set()
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # surface startup errors even without a console
        _fatal(f"程序启动失败：{exc}\n\n详情见 logs/app.log")
        raise SystemExit(1)
