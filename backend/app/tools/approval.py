import os
import psycopg2
from fastapi import APIRouter, HTTPException, Depends
from app.auth import require_api_key
from app.tools.draft_stakeholder_update import execute_draft_stakeholder_update
from app.tools.schedule_review import execute_schedule_review

router = APIRouter()

EXECUTORS = {
    "draft_stakeholder_update": lambda cid, aid, payload: execute_draft_stakeholder_update(cid, aid),
    "schedule_review": lambda cid, aid, payload: execute_schedule_review(cid, aid, payload.get("days_from_now", 7)),
}

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

@router.get("/actions/pending")
def list_pending():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select id, action_type, cluster_id, request_payload, created_at from actions_log where status = 'pending_approval' order by created_at;"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"action_id": str(r[0]), "action_type": r[1], "cluster_id": r[2], "context": r[3], "created_at": str(r[4])}
        for r in rows
    ]

@router.post("/actions/{action_id}/reject", dependencies=[Depends(require_api_key)])
def reject_action(action_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select status from actions_log where id = %s;", (action_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Action not found")

    status = row[0]
    if status != "pending_approval":
        cur.close()
        conn.close()
        return {"status": "no_action_taken", "message": f"Action is already in status {status}, not pending."}

    cur.execute("update actions_log set status = 'rejected' where id = %s;", (action_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "rejected", "message": "Action will not be executed."}

@router.post("/actions/{action_id}/approve", dependencies=[Depends(require_api_key)])
def approve_action(action_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "select action_type, cluster_id, request_payload, status from actions_log where id = %s;",
        (action_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Action not found")

    action_type, cluster_id, payload, status = row
    if status != "pending_approval":
        return {"status": "no_action_taken", "message": f"Action is already in status {status}, not pending."}

    executor = EXECUTORS.get(action_type)
    if not executor:
        raise HTTPException(status_code=500, detail=f"No executor registered for action_type {action_type}")

    result = executor(cluster_id, action_id, payload or {})
    return {"status": "approved_and_executed", "result": result}