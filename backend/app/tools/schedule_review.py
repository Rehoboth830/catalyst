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
        "select id, status, response_payload from actions_log where idempotency_key = %s and status = 'completed';",
        (idempotency_key,)
    )
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        return {
            "status": "already_exists",
            "message": "This action was already performed - returning original result, not repeating it.",
            "original_result": existing[2],
        }

    cur.execute(
        "select theme_label, rice_score from cluster_insights where cluster_id = %s and is_actionable = true;",
        (req.cluster_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Cluster not found or not actionable")

    theme_label, rice = row
    proposed_date = date.today() + timedelta(days=req.days_from_now)
    notes = f"Priority review for: {theme_label} (RICE: {rice:.1f})"

    cur.execute(
        "insert into actions_log (action_type, cluster_id, idempotency_key, status, requires_approval, request_payload) values (%s, %s, %s, %s, %s, %s);",
        ("schedule_review", req.cluster_id, idempotency_key, "pending", True, Json({"theme_label": theme_label}))
    )
    conn.commit()

    cur.execute(
        "insert into scheduled_reviews (cluster_id, proposed_date, notes) values (%s, %s, %s) returning id;",
        (req.cluster_id, proposed_date, notes)
    )
    review_id = cur.fetchone()[0]

    cur.execute(
        "update actions_log set status = %s, response_payload = %s where idempotency_key = %s;",
        ("completed", Json({"review_id": str(review_id), "proposed_date": str(proposed_date), "notes": notes}), idempotency_key)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"status": "scheduled", "review_id": str(review_id), "proposed_date": str(proposed_date)}
