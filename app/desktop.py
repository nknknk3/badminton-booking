"""Native desktop window; browser mode is strictly opt-in."""
from __future__ import annotations

import webbrowser
import time

from app.lifecycle import shutdown_requested
from app.runtime import APP_ROOT, logger

TITLE = "羽毛球预约助手"


def launch(url: str, mode: str = "auto") -> None:
    if mode == "browser":
        webbrowser.open(url)
        shutdown_requested.wait()
        return

    started = time.monotonic()
    import webview

    window = webview.create_window(
        TITLE, url, width=1240, height=860, min_size=(440, 640),
        background_color="#f4f6f3", text_select=True,
    )
    window.events.closed += shutdown_requested.set
    def loaded() -> None:
        logger.info("桌面窗口已加载，耗时 %.2f 秒", time.monotonic() - started)
    window.events.loaded += loaded

    def watch_shutdown() -> None:
        shutdown_requested.wait()
        try:
            window.destroy()
        except Exception:
            logger.debug("窗口已关闭", exc_info=True)

    webview.start(
        watch_shutdown, gui="edgechromium", debug=False,
        private_mode=False, storage_path=str(APP_ROOT / "runtime" / "webview"),
    )


def window_backend() -> str:
    return "native-window (WebView2)"
