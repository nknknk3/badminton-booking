"""Check the real Edge relaunch without entering credentials or booking."""
import asyncio
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.browser_login import BrowserLogin


async def main():
    login = BrowserLogin()
    try:
        with patch("app.services.browser_login.LOGIN_URL", "about:blank"):
            await login.start()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            await asyncio.sleep(1)
            if not login.busy:
                raise RuntimeError(login.message)
        result = {"state_after_25s": login.state,
                  "launcher_exit_code": login._proc.poll(),
                  "real_browser_connected": login._last_page_seen is not None}
        if not result["real_browser_connected"]:
            raise RuntimeError("No CDP connection")
        print(json.dumps(result), flush=True)
    finally:
        await login.cancel()


asyncio.run(main())
