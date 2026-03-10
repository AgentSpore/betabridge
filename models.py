from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    email: str
    source: str | None = None
    plan_interest: str | None = None


class UserUpdate(BaseModel):
    source: Optional[str] = None
    plan_interest: Optional[str] = None


class EventCreate(BaseModel):
    user_id: int
    event: str
    metadata: str | None = None


class NpsCreate(BaseModel):
    user_id: int
    score: int
    comment: str | None = None


class ConvertCreate(BaseModel):
    user_id: int
    plan: str
    mrr: float


class UserResponse(BaseModel):
    id: int
    email: str
    source: str | None
    plan_interest: str | None
    status: str
    nps: int | None
    mrr: float | None
    events_count: int
    created_at: str
    converted_at: str | None
