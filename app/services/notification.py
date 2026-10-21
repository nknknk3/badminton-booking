from __future__ import annotations

import httpx

from app.config import settings
from app.runtime import logger


async def send_notification(title: str, content: str) -> bool:
    if not settings.PUSHPLUS_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(
                "https://www.pushplus.plus/send",
                json={
                    "token": settings.PUSHPLUS_TOKEN,
                    "title": title,
                    "content": content,
                    "template": "html",
                },
            )
            data = resp.json()
            return data.get("code") == 200
    except Exception as exc:  # notification must never break a booking run
        logger.warning("PushPlus 通知发送失败: %s", exc)
        return False
