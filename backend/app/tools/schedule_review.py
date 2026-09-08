import os
import hashlib
from datetime import date, timedelta
import psycopg2
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ScheduleReviewRequest(BaseModel):
    cluster_id: int
    days_from_now: int = 7

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def make_idempotency_key(action_type: str, cluster_id: int) -> str:
    raw = f"{action_type}:{cluster_id}"
    return hashlib.sha256(raw.encode()).hexdigest()

@router.post("/tools/schedule_review")
def schedule_review(req: ScheduleReviewRequest):
    idempotency_key = make_idempotency_key("schedule_review", req.cluster_id)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "select id, status, response_payload from actions_log where idempotency_key = %s;",
        (idempotency_key,)
    )
    existing = cur.fetchone()
    if existing:
        action_id, status, response = existing
        cur.close()
        conn.close()
        if status == "completed":
            return {"status": "already_exists", "message": "Already executed.", "original_result": response}
        elif status == "pending_approval":
            return {"status": "pending_approval", "action_id": str(action_id), "message": "Awaiting human approval - not yet executed."}

    cur.execute(
        "select theme_label from cluster_insights where cluster_id = %s and is_actionable = true;",
        (req.cluster_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Cluster not found or not actionable")

    cur.execute(
        "insert into actions_log (action_type, cluster_id, idempotency_key, status, requires_approval, request_payload) values (%s, %s, %s, %s, %s, %s) returning id;",
        ("schedule_review", req.cluster_id, idempotency_key, "pending_approval", True, Json({"theme_label": row[0], "days_from_now": req.days_from_now}))
    )
    action_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {"status": "pending_approval", "action_id": str(action_id), "message": "Action logged, awaiting human approval before it executes."}


def execute_schedule_review(cluster_id: int, action_id: str, days_from_now: int = 7):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("select theme_label, rice_score from cluster_insights where cluster_id = %s;", (cluster_id,))
    theme_label, rice = cur.fetchone()
    proposed_date = date.today() + timedelta(days=days_from_now)
    notes = f"Priority review for: {theme_label} (RICE: {rice:.1f})"

    cur.execute(
        "insert into scheduled_reviews (cluster_id, proposed_date, notes) values (%s, %s, %s) returning id;",
        (cluster_id, proposed_date, notes)
    )
    review_id = cur.fetchone()[0]

    result = {"review_id": str(review_id), "proposed_date": str(proposed_date), "notes": notes}
    cur.execute(
        "update actions_log set status = 'completed', response_payload = %s where id = %s;",
        (Json(result), action_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return result
