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


class ActivationScore(BaseModel):
    user_id: int
    email: str
    status: str
    score: int
    breakdown: dict
    days_in_beta: int
    recommendation: str


class ScoredUser(BaseModel):
    id: int
    email: str
    source: str | None
    plan_interest: str | None
    status: str
    score: int
    events_count: int
    nps: int | None
    days_in_beta: int


class ActivationStats(BaseModel):
    total_users: int
    avg_score: float
    score_distribution: dict
    by_status: list[dict]
    by_source: list[dict]
    ready_count: int
    at_risk_count: int
