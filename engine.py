from __future__ import annotations
from datetime import datetime, timezone
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
    cur = await db.execute(
        "INSERT OR IGNORE INTO beta_users (email, source, plan_interest, created_at) VALUES (?,?,?,?)",
        (data["email"], data.get("source"), data.get("plan_interest"), now)
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM beta_users WHERE email=?", (data["email"],))
    return _row(rows[0])

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
