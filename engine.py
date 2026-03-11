from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, date
import aiosqlite

SQL_TABLES = """
CREATE TABLE IF NOT EXISTS beta_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    source TEXT,
    plan_interest TEXT,
    status TEXT NOT NULL DEFAULT 'beta',
    nps INTEGER,
    mrr REAL,
    events_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    converted_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES beta_users(id)
);
"""

async def init_db(path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.executescript(SQL_TABLES)
    await db.commit()
    return db

def _row(r): return {k: r[k] for k in r.keys()}

async def add_user(db, data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT OR IGNORE INTO beta_users (email, source, plan_interest, created_at) VALUES (?,?,?,?)",
        (data["email"], data.get("source"), data.get("plan_interest"), now)
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE email=?", (data["email"],))
    return _row(rows[0])

async def update_user(db, user_id: int, updates: dict) -> dict | None:
    allowed = {"source", "plan_interest"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return await get_user(db, user_id)
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [user_id]
    cur = await db.execute(f"UPDATE beta_users SET {set_clause} WHERE id=?", values)
    await db.commit()
    if cur.rowcount == 0:
        return None
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE id=?", (user_id,))
    return _row(rows[0]) if rows else None

async def track_event(db, data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    cur = await db.execute(
        "INSERT INTO events (user_id, event, metadata, created_at) VALUES (?,?,?,?)",
        (data["user_id"], data["event"], data.get("metadata"), now)
    )
    await db.execute("UPDATE beta_users SET events_count = events_count + 1 WHERE id=?", (data["user_id"],))
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM events WHERE id=?", (cur.lastrowid,))
    return _row(rows[0])

async def record_nps(db, data: dict) -> dict:
    await db.execute("UPDATE beta_users SET nps=? WHERE id=?", (data["score"], data["user_id"]))
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE id=?", (data["user_id"],))
    return _row(rows[0]) if rows else None

async def convert_user(db, data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE beta_users SET status='converted', mrr=?, converted_at=? WHERE id=?",
        (data["mrr"], now, data["user_id"])
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE id=?", (data["user_id"],))
    return _row(rows[0]) if rows else None

async def list_users(db, status: str | None = None) -> list[dict]:
    if status:
        rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        rows = await db.execute_fetchall("SELECT * FROM beta_users ORDER BY created_at DESC LIMIT 500")
    return [_row(r) for r in rows]

async def get_funnel(db) -> dict:
    rows = await db.execute_fetchall("SELECT status, COUNT(*) as cnt, SUM(COALESCE(mrr,0)) as mrr FROM beta_users GROUP BY status")
    by_status = {r["status"]: {"count": r["cnt"], "mrr": round(r["mrr"],2)} for r in rows}
    total = sum(v["count"] for v in by_status.values())
    converted = by_status.get("converted", {}).get("count", 0)
    conversion_rate = round(converted / total * 100, 1) if total else 0.0
    avg_events_row = await db.execute_fetchall("SELECT AVG(events_count) as avg FROM beta_users WHERE status='converted'")
    avg_nps_row = await db.execute_fetchall("SELECT AVG(nps) as avg FROM beta_users WHERE nps IS NOT NULL")
    source_rows = await db.execute_fetchall("SELECT source, COUNT(*) as cnt FROM beta_users GROUP BY source ORDER BY cnt DESC LIMIT 5")
    return {
        "total_beta": total,
        "converted": converted,
        "conversion_rate_pct": conversion_rate,
        "mrr_from_beta": by_status.get("converted", {}).get("mrr", 0.0),
        "avg_events_before_convert": round(avg_events_row[0]["avg"] or 0, 1),
        "avg_nps": round(avg_nps_row[0]["avg"] or 0, 1),
        "by_status": by_status,
        "top_sources": [{"source": r["source"], "count": r["cnt"]} for r in source_rows],
    }

async def get_funnel_by_source(db) -> list[dict]:
    rows = await db.execute_fetchall("""
        SELECT
            COALESCE(source, 'unknown') AS source,
            COUNT(*) AS total,
            SUM(CASE WHEN status='converted' THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN status='churned' THEN 1 ELSE 0 END) AS churned,
            ROUND(SUM(CASE WHEN status='converted' THEN COALESCE(mrr,0) ELSE 0 END), 2) AS mrr,
            ROUND(AVG(nps), 1) AS avg_nps,
            ROUND(AVG(events_count), 1) AS avg_events
        FROM beta_users
        GROUP BY source
        ORDER BY converted DESC, total DESC
    """)
    result = []
    for r in rows:
        total = r["total"] or 0
        converted = r["converted"] or 0
        result.append({
            "source": r["source"],
            "total": total,
            "converted": converted,
            "churned": r["churned"] or 0,
            "conversion_rate_pct": round(converted / total * 100, 1) if total else 0.0,
            "mrr": r["mrr"] or 0.0,
            "avg_nps": r["avg_nps"],
            "avg_events": r["avg_events"] or 0.0,
        })
    return result

async def get_user(db, user_id: int) -> dict | None:
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE id=?", (user_id,))
    return _row(rows[0]) if rows else None

async def get_user_events(db, user_id: int) -> list[dict]:
    rows = await db.execute_fetchall(
        "SELECT * FROM events WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    )
    return [_row(r) for r in rows]

async def churn_user(db, user_id: int) -> dict | None:
    await db.execute("UPDATE beta_users SET status='churned' WHERE id=?", (user_id,))
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE id=?", (user_id,))
    return _row(rows[0]) if rows else None

async def get_cohorts(db) -> list[dict]:
    rows = await db.execute_fetchall("""
        SELECT
            strftime('%Y-W%W', created_at) AS week,
            COUNT(*) AS signups,
            SUM(CASE WHEN status='converted' THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN status='churned' THEN 1 ELSE 0 END) AS churned,
            ROUND(AVG(CASE WHEN status='converted' THEN mrr ELSE NULL END), 2) AS avg_mrr,
            ROUND(AVG(nps), 1) AS avg_nps
        FROM beta_users
        GROUP BY week
        ORDER BY week DESC
    """)
    result = []
    for r in rows:
        signups = r["signups"] or 0
        converted = r["converted"] or 0
        result.append({
            "week": r["week"],
            "signups": signups,
            "converted": converted,
            "churned": r["churned"] or 0,
            "conversion_rate_pct": round(converted / signups * 100, 1) if signups else 0.0,
            "avg_mrr": r["avg_mrr"],
            "avg_nps": r["avg_nps"],
        })
    return result

async def export_users_csv(db, status: str | None = None) -> str:
    import csv
    import io
    users = await list_users(db, status)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "email", "source", "plan_interest", "status",
        "nps", "mrr", "events_count", "created_at", "converted_at",
    ])
    for u in users:
        writer.writerow([
            u["id"], u["email"], u["source"], u["plan_interest"], u["status"],
            u["nps"], u["mrr"], u["events_count"], u["created_at"], u["converted_at"],
        ])
    return buf.getvalue()


def _calc_score(user: dict) -> tuple[int, dict]:
    """Calculate activation score 0-100 with breakdown."""
    ec = user["events_count"] or 0
    events_pts = int(min(ec / 10, 1.0) * 40)

    nps = user["nps"]
    nps_pts = int((nps / 10) * 25) if nps is not None else 0

    created = user["created_at"][:10]
    try:
        days = (date.today() - date.fromisoformat(created)).days
    except (ValueError, TypeError):
        days = 0
    days_pts = int(min(days / 30, 1.0) * 20)

    plan_pts = 15 if user["plan_interest"] else 0

    total = min(events_pts + nps_pts + days_pts + plan_pts, 100)
    breakdown = {
        "events": events_pts,
        "nps": nps_pts,
        "tenure": days_pts,
        "plan_interest": plan_pts,
    }
    return total, breakdown, days


def _recommendation(score: int, status: str) -> str:
    if status == "converted":
        return "Already converted — focus on expansion"
    if status == "churned":
        return "Churned — consider win-back campaign"
    if score >= 70:
        return "Ready to convert — reach out with pricing"
    if score >= 40:
        return "Engaged — nurture with feature highlights"
    if score >= 20:
        return "Low engagement — send activation email"
    return "At risk — immediate outreach needed"


async def calc_activation_score(db, user_id: int) -> dict | None:
    user = await get_user(db, user_id)
    if not user:
        return None
    score, breakdown, days = _calc_score(user)
    return {
        "user_id": user["id"],
        "email": user["email"],
        "status": user["status"],
        "score": score,
        "breakdown": breakdown,
        "days_in_beta": days,
        "recommendation": _recommendation(score, user["status"]),
    }


async def get_ready_users(db, threshold: int = 70) -> list[dict]:
    rows = await db.execute_fetchall(
        "SELECT * FROM beta_users WHERE status='beta' ORDER BY events_count DESC"
    )
    result = []
    for r in rows:
        user = _row(r)
        score, _, days = _calc_score(user)
        if score >= threshold:
            result.append({
                "id": user["id"], "email": user["email"],
                "source": user["source"], "plan_interest": user["plan_interest"],
                "status": user["status"], "score": score,
                "events_count": user["events_count"],
                "nps": user["nps"], "days_in_beta": days,
            })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


async def get_at_risk_users(db, threshold: int = 30, min_days: int = 7) -> list[dict]:
    rows = await db.execute_fetchall(
        "SELECT * FROM beta_users WHERE status='beta' ORDER BY events_count ASC"
    )
    result = []
    for r in rows:
        user = _row(r)
        score, _, days = _calc_score(user)
        if score < threshold and days >= min_days:
            result.append({
                "id": user["id"], "email": user["email"],
                "source": user["source"], "plan_interest": user["plan_interest"],
                "status": user["status"], "score": score,
                "events_count": user["events_count"],
                "nps": user["nps"], "days_in_beta": days,
            })
    result.sort(key=lambda x: x["score"])
    return result


async def get_activation_stats(db) -> dict:
    rows = await db.execute_fetchall("SELECT * FROM beta_users")
    if not rows:
        return {
            "total_users": 0, "avg_score": 0.0,
            "score_distribution": {}, "by_status": [], "by_source": [],
            "ready_count": 0, "at_risk_count": 0,
        }

    scores = []
    by_status = defaultdict(list)
    by_source = defaultdict(list)
    ready = 0
    at_risk = 0

    for r in rows:
        user = _row(r)
        score, _, days = _calc_score(user)
        scores.append(score)
        by_status[user["status"]].append(score)
        by_source[user["source"] or "unknown"].append(score)
        if user["status"] == "beta":
            if score >= 70:
                ready += 1
            elif score < 30 and days >= 7:
                at_risk += 1

    # Score distribution in buckets
    buckets = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for s in scores:
        if s < 20: buckets["0-19"] += 1
        elif s < 40: buckets["20-39"] += 1
        elif s < 60: buckets["40-59"] += 1
        elif s < 80: buckets["60-79"] += 1
        else: buckets["80-100"] += 1

    status_stats = [
        {"status": k, "count": len(v), "avg_score": round(sum(v) / len(v), 1)}
        for k, v in sorted(by_status.items())
    ]
    source_stats = [
        {"source": k, "count": len(v), "avg_score": round(sum(v) / len(v), 1)}
        for k, v in sorted(by_source.items(), key=lambda x: -len(x[1]))
    ]

    return {
        "total_users": len(scores),
        "avg_score": round(sum(scores) / len(scores), 1),
        "score_distribution": buckets,
        "by_status": status_stats,
        "by_source": source_stats,
        "ready_count": ready,
        "at_risk_count": at_risk,
    }
