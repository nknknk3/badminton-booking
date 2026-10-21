from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.models.schemas import AuthStatusResponse, BrowserLoginStatus, MessageResponse
from app.services.auth_service import auth_service
from app.services.browser_login import browser_login

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status() -> AuthStatusResponse:
    return await auth_service.status()


@router.post("/login", response_model=MessageResponse)
async def login(cookie_file: UploadFile = File(...)) -> MessageResponse:
    return await auth_service.upload(cookie_file)


@router.post("/logout", response_model=MessageResponse)
async def logout() -> MessageResponse:
    return await auth_service.logout()


# ---------------------------------------------------------------- in-app login
@router.post("/browser-login", response_model=BrowserLoginStatus)
async def start_browser_login() -> BrowserLoginStatus:
    state = await browser_login.start()
    return BrowserLoginStatus(**state)


@router.get("/browser-login", response_model=BrowserLoginStatus)
async def browser_login_status() -> BrowserLoginStatus:
    return BrowserLoginStatus(**browser_login.snapshot())


@router.delete("/browser-login", response_model=BrowserLoginStatus)
async def cancel_browser_login() -> BrowserLoginStatus:
    state = await browser_login.cancel()
    return BrowserLoginStatus(**state)
