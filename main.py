from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from models import (
    UserCreate, UserUpdate, EventCreate, NpsCreate, ConvertCreate,
    UserResponse, ActivationScore, ScoredUser, ActivationStats,
)
from engine import (
    init_db, add_user, update_user, track_event, record_nps, convert_user,
    list_users, get_funnel, get_funnel_by_source, get_user, get_user_events,
    churn_user, get_cohorts, export_users_csv,
    calc_activation_score, get_ready_users, get_at_risk_users, get_activation_stats,
)

DB_PATH = "betabridge.db"

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await init_db(DB_PATH)
    yield
    await app.state.db.close()

app = FastAPI(
    title="BetaBridge",
    description="Beta-to-paid conversion tracker with activation scoring. Track user journeys, score readiness to convert, identify at-risk users needing intervention.",
    version="0.5.0",
    lifespan=lifespan,
)

@app.post("/users", response_model=UserResponse, status_code=201)
async def add_beta_user(body: UserCreate):
    return await add_user(app.state.db, body.model_dump())

@app.get("/users/export/csv")
async def export_csv(
    status: str | None = Query(None, description="Filter: beta, converted, churned"),
):
    csv_data = await export_users_csv(app.state.db, status)
    filename = f"betabridge_users{'_' + status if status else ''}.csv"
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@app.get("/users/ready", response_model=list[ScoredUser])
async def ready_to_convert(
    threshold: int = Query(70, ge=1, le=100, description="Minimum activation score"),
):
    """Beta users with high activation scores — sales-ready list sorted by score desc."""
    return await get_ready_users(app.state.db, threshold)

@app.get("/users/at-risk", response_model=list[ScoredUser])
async def at_risk_users(
    threshold: int = Query(30, ge=1, le=100, description="Max score to be considered at-risk"),
    min_days: int = Query(7, ge=1, description="Min days in beta before flagging"),
):
    """Beta users with low scores who've been around long enough — need intervention."""
    return await get_at_risk_users(app.state.db, threshold, min_days)

@app.get("/users", response_model=list[UserResponse])
async def list_beta_users(status: str | None = Query(None, description="beta | converted | churned")):
    return await list_users(app.state.db, status)

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user_detail(user_id: int):
    u = await get_user(app.state.db, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@app.get("/users/{user_id}/score", response_model=ActivationScore)
async def user_activation_score(user_id: int):
    """Activation score 0-100 with breakdown (events, NPS, tenure, plan_interest) and recommendation."""
    result = await calc_activation_score(app.state.db, user_id)
    if not result:
        raise HTTPException(404, "User not found")
    return result

@app.patch("/users/{user_id}", response_model=UserResponse)
async def patch_user(user_id: int, body: UserUpdate):
    result = await update_user(app.state.db, user_id, body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(404, "User not found")
    return result

@app.get("/users/{user_id}/events")
async def user_events(user_id: int):
    return await get_user_events(app.state.db, user_id)

@app.post("/users/{user_id}/churn", response_model=UserResponse)
async def mark_churned(user_id: int):
    u = await churn_user(app.state.db, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u

@app.post("/events")
async def post_event(body: EventCreate):
    return await track_event(app.state.db, body.model_dump())

@app.post("/nps")
async def submit_nps(body: NpsCreate):
    if not 0 <= body.score <= 10:
        raise HTTPException(422, "NPS score must be 0-10")
    result = await record_nps(app.state.db, body.model_dump())
    if not result:
        raise HTTPException(404, "User not found")
    return result

@app.post("/convert", response_model=UserResponse)
async def mark_converted(body: ConvertCreate):
    result = await convert_user(app.state.db, body.model_dump())
    if not result:
        raise HTTPException(404, "User not found")
    return result

@app.get("/activation/stats", response_model=ActivationStats)
async def activation_stats():
    """Score distribution, avg by status/source, ready + at-risk counts."""
    return await get_activation_stats(app.state.db)

@app.get("/funnel/by-source")
async def funnel_by_source():
    return await get_funnel_by_source(app.state.db)

@app.get("/funnel")
async def conversion_funnel():
    return await get_funnel(app.state.db)

@app.get("/cohorts")
async def cohort_analysis():
    return await get_cohorts(app.state.db)
