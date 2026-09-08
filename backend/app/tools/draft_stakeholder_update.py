import os
import hashlib
import psycopg2
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class DraftUpdateRequest(BaseModel):
    cluster_id: int

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def make_idempotency_key(action_type: str, cluster_id: int) -> str:
    raw = f"{action_type}:{cluster_id}"
    return hashlib.sha256(raw.encode()).hexdigest()

@router.post("/tools/draft_stakeholder_update")
def draft_stakeholder_update(req: DraftUpdateRequest):
    idempotency_key = make_idempotency_key("draft_stakeholder_update", req.cluster_id)

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
        ("draft_stakeholder_update", req.cluster_id, idempotency_key, "pending_approval", True, Json({"theme_label": row[0]}))
    )
    action_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {"status": "pending_approval", "action_id": str(action_id), "message": "Action logged, awaiting human approval before it executes."}


def execute_draft_stakeholder_update(cluster_id: int, action_id: str):
    '''Called only by the approval endpoint - performs the actual write.'''
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "select theme_label, reach_count, rice_score, prd from cluster_insights where cluster_id = %s;",
        (cluster_id,)
    )
    theme_label, reach, rice, prd = cur.fetchone()

    draft = f"Update: We've identified a priority issue - '{theme_label}' - affecting {reach} reported cases (RICE score: {rice:.1f}).\\n\\n"
    if prd:
        draft += f"Planned approach: {prd.get('proposed_solution', 'Under review.')}\\n"
        draft += f"We'll track success via: {prd.get('success_metric', 'TBD.')}"

    cur.execute(
        "insert into stakeholder_updates (cluster_id, draft_text) values (%s, %s) returning id;",
        (cluster_id, draft)
    )
    update_id = cur.fetchone()[0]

    result = {"update_id": str(update_id), "draft_text": draft}
    cur.execute(
        "update actions_log set status = 'completed', response_payload = %s where id = %s;",
        (Json(result), action_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return result
