from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from models import UserCreate, EventCreate, NpsCreate, ConvertCreate, UserResponse
from engine import (
    init_db, add_user, track_event, record_nps, convert_user,
    list_users, get_funnel, get_user, get_user_events, churn_user,
)

DB_PATH = "betabridge.db"

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await init_db(DB_PATH)
    yield
    await app.state.db.close()

app = FastAPI(
    title="BetaBridge",
    description="Beta-to-paid conversion tracker. Track every beta user journey — signup source, activation events, NPS. Surface which cohorts convert and why.",
    version="0.2.0",
    lifespan=lifespan,
)

@app.post("/users", response_model=UserResponse, status_code=201)
async def add_beta_user(body: UserCreate):
    """Register a new beta user (idempotent by email)."""
    return await add_user(app.state.db, body.model_dump())

@app.get("/users", response_model=list[UserResponse])
async def list_beta_users(status: str | None = Query(None, description="beta | converted | churned")):
    """List beta users, optionally filtered by status."""
    return await list_users(app.state.db, status)

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user_detail(user_id: int):
    """Get a single beta user by ID."""
    u = await get_user(app.state.db, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@app.get("/users/{user_id}/events")
async def user_events(user_id: int):
    """Get all tracked events for a specific beta user."""
    return await get_user_events(app.state.db, user_id)

@app.post("/users/{user_id}/churn", response_model=UserResponse)
async def mark_churned(user_id: int):
    """Mark a beta user as churned."""
    u = await churn_user(app.state.db, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@app.post("/events")
async def post_event(body: EventCreate):
    """Track an activation or usage event for a beta user."""
    return await track_event(app.state.db, body.model_dump())

@app.post("/nps")
async def submit_nps(body: NpsCreate):
    """Record an NPS score (0-10) from a beta user."""
    if not 0 <= body.score <= 10:
        raise HTTPException(422, "NPS score must be 0-10")
    result = await record_nps(app.state.db, body.model_dump())
    if not result:
        raise HTTPException(404, "User not found")
    return result

@app.post("/convert", response_model=UserResponse)
async def mark_converted(body: ConvertCreate):
    """Mark a beta user as converted to paid. Record plan and MRR."""
    result = await convert_user(app.state.db, body.model_dump())
    if not result:
        raise HTTPException(404, "User not found")
    return result

@app.get("/funnel")
async def conversion_funnel():
    """Funnel stats: total beta, conversion rate, MRR from beta, avg events before convert, top sources."""
    return await get_funnel(app.state.db)
