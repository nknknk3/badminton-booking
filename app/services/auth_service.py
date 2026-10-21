from __future__ import annotations

import json
import os
import time

from fastapi import UploadFile

from app.config import settings
from app.models.schemas import AuthStatusResponse, MessageResponse
from app.runtime import logger
from app.services.venue_client import (
    VenueAuthError,
    VenueError,
    read_cookie_file,
    _filter_venue_cookies,
    venue_client,
)

MAX_COOKIE_FILE_BYTES = 2 * 1024 * 1024  # 2 MB


class AuthService:
    async def status(self) -> AuthStatusResponse:
        has_file = os.path.isfile(settings.COOKIE_FILE)
        cookie_count = venue_client.cookie_count
        captured_at = venue_client.captured_at
        try:
            logged_in = await venue_client.check_login()
        except VenueError as exc:
            return AuthStatusResponse(
                logged_in=False,
                message=str(exc),
                has_cookie_file=has_file,
                cookie_count=cookie_count,
                captured_at=captured_at,
            )
        if logged_in:
            message = "登录有效"
        elif not has_file:
            message = "尚未导入 session 文件"
        elif cookie_count == 0:
            message = "session 文件里没有场馆 cookie，请重新导出"
        else:
            message = "登录已过期，请重新导出 session 文件"
        return AuthStatusResponse(
            logged_in=logged_in,
            message=message,
            has_cookie_file=has_file,
            cookie_count=cookie_count,
            captured_at=captured_at,
        )

    async def upload(self, file: UploadFile) -> MessageResponse:
        raw = await file.read()
        if not raw:
            return MessageResponse(success=False, message="文件为空")
        if len(raw) > MAX_COOKIE_FILE_BYTES:
            return MessageResponse(
                success=False, message="文件过大（上限 2 MB），请确认是 session 文件"
            )

        # Validate BEFORE touching the existing (working) file.
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return MessageResponse(success=False, message=f"不是合法的 JSON: {exc}")
        if not isinstance(payload, dict) or not isinstance(payload.get("cookies"), list):
            return MessageResponse(
                success=False,
                message="文件结构不正确：需要包含 cookies 数组的 session 文件",
            )
        if not _filter_venue_cookies(payload):
            return MessageResponse(
                success=False, message="文件里没有场馆（gyytygyy）的 cookie"
            )

        target = settings.COOKIE_FILE
        tmp = f"{target}.tmp"
        backup = f"{target}.bak"
        try:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
        except OSError as exc:
            for path in (tmp,):
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            return MessageResponse(success=False, message=f"保存失败: {exc}")

        await venue_client.reload_cookies()

        try:
            logged_in = await venue_client.check_login()
        except VenueError as exc:
            return MessageResponse(
                success=False, message=f"已保存，但无法校验登录状态: {exc}"
            )
        if logged_in:
            logger.info("session 文件已更新，登录验证通过")
            return MessageResponse(
                success=True, message="session 已更新，登录验证通过"
            )
        return MessageResponse(
            success=False,
            message="文件已保存，但登录校验未通过：cookie 可能已过期",
        )

    async def logout(self) -> MessageResponse:
        removed = False
        if os.path.isfile(settings.COOKIE_FILE):
            try:
                os.remove(settings.COOKIE_FILE)
                removed = True
            except OSError as exc:
                return MessageResponse(success=False, message=f"删除失败: {exc}")
        await venue_client.reload_cookies()
        return MessageResponse(
            success=True,
            message="已退出登录，cookie 文件已删除" if removed else "已经是未登录状态",
        )


auth_service = AuthService()
