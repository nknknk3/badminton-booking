"""浏览器登录并导出 session 文件。

账号密码不再硬编码：从环境变量读取，或运行后交互输入。

    set XIDIAN_USERNAME=你的学号
    set XIDIAN_PASSWORD=你的密码
    python tools/login.py

需要先安装：pip install playwright && playwright install chromium
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover
    print("缺少 playwright：pip install playwright && playwright install chromium")
    sys.exit(1)

import asyncio

AUTH_SERVER = "https://ids.xidian.edu.cn"
VENUE_HOST = "gyytygyy.xidian.edu.cn"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "venue_session.json"

SERVICE_URL = (
    "https://xxcapp.xidian.edu.cn/a_xidian/api/cas-login/index"
    "?redirect=https%3A%2F%2Fxxcapp.xidian.edu.cn%2Fuc%2Fapi%2Foauth%2Findex"
    "%3Fappid%3D200240927110038794%26redirect%3Dhttp%3A%2F%2Fgyytygyy.xidian.edu.cn"
    "%2FUser%2FQYLogin%26state%3DSTATE&from=wap"
)


def read_credentials() -> tuple[str, str]:
    username = os.environ.get("XIDIAN_USERNAME", "").strip()
    password = os.environ.get("XIDIAN_PASSWORD", "")
    if not username:
        username = input("学号: ").strip()
    if not password:
        password = getpass.getpass("密码（输入时不显示）: ")
    if not username or not password:
        print("账号或密码为空，已退出。")
        sys.exit(1)
    return username, password


async def main() -> None:
    username, password = read_credentials()
    login_url = AUTH_SERVER + "/authserver/login?" + urllib.parse.urlencode(
        {"service": SERVICE_URL}
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1180, "height": 820},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = await context.new_page()

        print("=" * 60)
        print("已打开登录页，账号密码会自动填入，请手动完成滑块验证。")
        print("登录成功后请等待自动跳转到场馆页面，脚本会自动保存 session。")
        print("=" * 60)

        await page.goto(login_url)
        await page.wait_for_timeout(1500)
        try:
            await page.fill("#username", username)
            await page.fill("#password", password)
            print("账号密码已填入。")
        except Exception as exc:
            print(f"[提示] 自动填入失败，请手动输入：{exc}")

        reached = False
        start = time.time()
        while time.time() - start < 300:
            if urllib.parse.urlparse(page.url).hostname == VENUE_HOST:
                reached = True
                break
            await page.wait_for_timeout(1500)

        if not reached:
            print("等待超时，未能跳转到场馆页面，未保存 session。")
            await browser.close()
            return

        await page.wait_for_timeout(2500)
        cookies = await context.cookies()
        payload = {
            "final_url": page.url,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cookies": [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", False),
                }
                for c in cookies
            ],
        }
        OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        venue_cookies = [c for c in payload["cookies"] if VENUE_HOST in c["domain"]]
        print(f"已保存 {len(venue_cookies)} 条场馆 cookie → {OUTPUT}")
        print("接下来：打开程序 → 设置页 → 上传该文件（或直接放到程序目录）。")
        await page.wait_for_timeout(3000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
