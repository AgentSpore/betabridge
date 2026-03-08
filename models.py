from __future__ import annotations
from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    source: str | None = None        # e.g. producthunt, twitter, hacker_news
    plan_interest: str | None = None


class EventCreate(BaseModel):
    user_id: int
    event: str                        # activated, invited_team, used_feature, etc.
    metadata: str | None = None


class NpsCreate(BaseModel):
    user_id: int
    score: int                        # 0-10
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
    status: str          # beta | converted | churned
    nps: int | None
    mrr: float | None
    events_count: int
    created_at: str
    converted_at: str | None
