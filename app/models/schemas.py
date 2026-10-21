from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SlotInfo(BaseModel):
    begin_time: str
    end_time: str
    field_state: int
    time_status: int


class FieldInfo(BaseModel):
    field_no: str
    field_name: str
    field_type_no: str
    begin_time: str
    end_time: str
    price: str
    field_state: int
    time_status: int


class SlotsResponse(BaseModel):
    date: str
    slots: list[SlotInfo] = Field(default_factory=list)
    error: Optional[str] = None


class FieldsResponse(BaseModel):
    fields: list[FieldInfo] = Field(default_factory=list)
    error: Optional[str] = None


class DatesResponse(BaseModel):
    dates: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class OrderRequest(BaseModel):
    date: str = Field(description="MM-DD")
    begin_time: str = Field(description="HH:MM")
    end_time: str = Field(description="HH:MM")
    field_no: str = Field(min_length=1, max_length=32)


class OrderResponse(BaseModel):
    success: bool
    message: str


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    target_date: str = Field(description="MM-DD")
    target_times: list[str] = Field(min_length=1)
    poll_interval: float = 3.0
    start_at: Optional[str] = None


class TaskUpdate(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    target_times: Optional[list[str]] = None
    poll_interval: Optional[float] = None
    start_at: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    name: str
    target_date: str
    target_times: list[str]
    poll_interval: float
    start_at: Optional[str]
    enabled: bool
    status: str
    next_run_at: Optional[str] = None
    created_at: str
    updated_at: str


class BookingHistoryItem(BaseModel):
    id: int
    task_id: Optional[int]
    field_no: str
    field_name: str
    date: str
    begin_time: str
    end_time: str
    status: str
    message: str
    created_at: str


class AuthStatusResponse(BaseModel):
    logged_in: bool
    message: str
    has_cookie_file: bool = False
    cookie_count: int = 0
    captured_at: Optional[str] = None


class MessageResponse(BaseModel):
    success: bool
    message: str


class SystemInfo(BaseModel):
    version: str
    frozen: bool
    venue_no: str
    field_type: str
    auth_required: bool
    poll_default: float
    lead_minutes: int
    max_runtime_hours: float
    data_dir: str


class RuntimeSettings(BaseModel):
    default_poll_interval: float = Field(ge=0.5, le=60)
    lead_minutes: int = Field(ge=0, le=720)
    max_runtime_hours: float = Field(ge=0.5, le=12)


class BrowserLoginStatus(BaseModel):
    state: str
    message: str
    cookie_count: int = 0
    login_url: str = ""
