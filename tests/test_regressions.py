import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.browser_login import BrowserLogin, VENUE_HOST
from app.services.venue_client import VenueClient, _filter_venue_cookies
from app.lifecycle import shutdown_requested


class LoginRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def _watch_with_debug_responses(self, responses, step):
        login = BrowserLogin()
        login.state = "waiting"
        login._proc = MagicMock()
        login._proc.poll.return_value = 0  # launcher exited; real Edge can survive
        login._read_cookies = AsyncMock(return_value=[{"name": "test"}])
        login._persist = AsyncMock()
        login._shutdown_browser = AsyncMock()
        elapsed = 0

        async def tick(_):
            nonlocal elapsed
            elapsed += step

        converted = []
        for response in responses:
            if isinstance(response, Exception):
                converted.append(response)
            else:
                result = MagicMock()
                result.json.return_value = response
                converted.append(result)
        with patch("app.services.browser_login.time") as clock, patch("app.services.browser_login.httpx.AsyncClient") as client, patch("app.services.browser_login.asyncio.sleep", side_effect=tick), patch("app.services.browser_login.venue_client.check_login", AsyncMock(return_value=True)):
            clock.monotonic.side_effect = lambda: elapsed
            client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=converted)
            await login._watch()
        return login

    async def test_exited_launcher_does_not_close_live_login_page(self):
        cas = [{"type": "page", "url": "https://ids.xidian.edu.cn/authserver/login"}]
        venue = [{"type": "page", "url": f"https://{VENUE_HOST}/", "webSocketDebuggerUrl": "ws://local"}]
        login = await self._watch_with_debug_responses([cas, cas, cas, venue], 10)
        self.assertEqual(login.state, "success")
        login._persist.assert_awaited_once()
        login._proc.poll.assert_not_called()

    async def test_temporary_debug_disconnect_does_not_abort_login(self):
        cas = [{"type": "page", "url": "https://ids.xidian.edu.cn/authserver/login"}]
        venue = [{"type": "page", "url": f"https://{VENUE_HOST}/", "webSocketDebuggerUrl": "ws://local"}]
        login = await self._watch_with_debug_responses([cas, httpx.ConnectError("restarting"), httpx.ConnectError("restarting"), venue], 4)
        self.assertEqual(login.state, "success")

    async def test_closed_browser_eventually_reports_disconnect(self):
        cas = [{"type": "page", "url": "https://ids.xidian.edu.cn/authserver/login"}]
        login = await self._watch_with_debug_responses([cas, [], [], []], 5)
        self.assertEqual(login.state, "failed")
        self.assertIn("连接已中断", login.message)
        login._persist.assert_not_awaited()

    async def test_debug_startup_failure_is_not_reported_as_window_closed(self):
        login = await self._watch_with_debug_responses([[], [], [], [], []], 20)
        self.assertEqual(login.state, "failed")
        self.assertIn("调试接口", login.message)
        login._persist.assert_not_awaited()

    async def test_redirect_query_is_not_a_venue_page(self):
        login = BrowserLogin()
        response = MagicMock()
        response.json.return_value = [
            {"type": "page", "url": f"https://ids.xidian.edu.cn/login?service=https://{VENUE_HOST}", "webSocketDebuggerUrl": "wrong"},
            {"type": "page", "url": f"https://{VENUE_HOST}/User/Index", "webSocketDebuggerUrl": "correct"},
        ]
        with patch("app.services.browser_login.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get = AsyncMock(return_value=response)
            page = await login._find_venue_page()
        self.assertEqual(page["webSocketDebuggerUrl"], "correct")

    async def test_waits_for_valid_session_before_persisting(self):
        login = BrowserLogin()
        login.state = "waiting"
        cookies = [{"name": "session", "value": "test", "domain": VENUE_HOST}]
        login._find_venue_page = AsyncMock(return_value={"webSocketDebuggerUrl": "ws://local"})
        login._read_cookies = AsyncMock(return_value=cookies)
        login._persist = AsyncMock()
        login._shutdown_browser = AsyncMock()
        with patch("app.services.browser_login.venue_client.check_login", AsyncMock(side_effect=[False, True])) as check, patch("app.services.browser_login.asyncio.sleep", AsyncMock()):
            await login._watch()
        self.assertEqual(check.await_count, 2)
        login._persist.assert_awaited_once_with(cookies)
        self.assertEqual(login.state, "success")

    async def test_cancel_awaits_cleanup_before_next_attempt(self):
        login = BrowserLogin()
        login._shutdown_browser = AsyncMock()
        login._task = asyncio.create_task(asyncio.sleep(30))
        await login.cancel()
        self.assertTrue(login._task.done())
        self.assertEqual(login.state, "cancelled")

    async def test_next_login_waits_for_previous_cleanup(self):
        login = BrowserLogin()
        login.state = "success"
        login._task = asyncio.create_task(asyncio.sleep(0))
        with patch("app.services.browser_login._browser_exe", return_value=None):
            await login.start()
        self.assertTrue(login._task.done())

    async def test_no_cookies_does_not_make_network_request(self):
        client = VenueClient()
        client._post = AsyncMock()
        self.assertFalse(await client.check_login())
        client._post.assert_not_awaited()

    async def test_utf8_bom_login_response(self):
        client = VenueClient()
        client._cookies = {"session": "test"}
        client._post = AsyncMock(return_value=httpx.Response(200, text="\ufeff1\r\n"))
        self.assertTrue(await client.check_login())

    def test_parent_domain_cookie_and_lookalike_domain(self):
        result = _filter_venue_cookies({"cookies": [
            {"domain": ".xidian.edu.cn", "name": "parent", "value": "yes"},
            {"domain": f"{VENUE_HOST}.evil.example", "name": "fake", "value": "no"},
        ]})
        self.assertEqual(result, {"parent": "yes"})


class ShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_requires_local_request_and_action_header(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.api.system import shutdown

        def request(host, headers):
            return Request({"type": "http", "method": "POST", "path": "/api/system/shutdown", "scheme": "http", "server": ("127.0.0.1", 8000), "client": (host, 1234), "headers": headers})

        shutdown_requested.clear()
        for req in [request("127.0.0.1", []), request("10.0.0.5", [(b"x-desktop-action", b"shutdown")]), request("127.0.0.1", [(b"x-desktop-action", b"shutdown"), (b"origin", b"https://foreign.example")])]:
            with self.assertRaises(HTTPException):
                await shutdown(req)
        result = await shutdown(request("127.0.0.1", [(b"x-desktop-action", b"shutdown")]))
        self.assertTrue(result["success"])
        await asyncio.sleep(0.4)
        self.assertTrue(shutdown_requested.is_set())
        shutdown_requested.clear()


if __name__ == "__main__":
    unittest.main()
