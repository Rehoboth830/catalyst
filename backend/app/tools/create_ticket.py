import os
import hashlib
import requests
import psycopg2
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class CreateTicketRequest(BaseModel):
    cluster_id: int

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def make_idempotency_key(action_type: str, cluster_id: int) -> str:
    raw = f"{action_type}:{cluster_id}"
    return hashlib.sha256(raw.encode()).hexdigest()

@router.post("/tools/create_ticket")
def create_ticket(req: CreateTicketRequest):
    idempotency_key = make_idempotency_key("create_ticket", req.cluster_id)

    conn = get_conn()
    cur = conn.cursor()

    # Idempotency check: has this exact action already run?
    cur.execute("select id, status, response_payload from actions_log where idempotency_key = %s and status = 'completed';", (idempotency_key,))
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        return {
            "status": "already_exists",
            "message": "This action was already performed - returning original result, not repeating it.",
            "original_result": existing[2],
        }

    # Fetch the cluster's PRD/theme to build a real ticket, not a stub
    cur.execute(
        "select theme_label, reach_count, rice_score, justification, prd from cluster_insights where cluster_id = %s and is_actionable = true;",
        (req.cluster_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Cluster not found or not actionable")

    theme_label, reach, rice, justification, prd = row

    body = f"**Reach:** {reach} feedback items\\n**RICE score:** {rice:.1f}\\n**Priority justification:** {justification}\\n\\n"
    if prd:
        body += f"### Problem Statement\\n{prd.get('problem_statement', '')}\\n\\n"
        body += f"### Proposed Solution\\n{prd.get('proposed_solution', '')}\\n\\n"
        body += f"### Success Metric\\n{prd.get('success_metric', '')}\\n"

    # Log as pending BEFORE calling GitHub - if the process crashes mid-call, we know it was attempted
    cur.execute(
        "insert into actions_log (action_type, cluster_id, idempotency_key, status, requires_approval, request_payload) values (%s, %s, %s, %s, %s, %s);",
        ("create_ticket", req.cluster_id, idempotency_key, "pending", False, Json({"theme_label": theme_label}))
    )
    conn.commit()

    gh_url = f"https://api.github.com/repos/{os.environ['GITHUB_REPO']}/issues"
    resp = requests.post(
        gh_url,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": f"[Catalyst] {theme_label}", "body": body, "labels": ["catalyst-generated"]},
        timeout=15,
    )

    if resp.status_code == 201:
        issue_data = resp.json()
        cur.execute(
            "update actions_log set status = %s, response_payload = %s where idempotency_key = %s;",
            ("completed", Json({"issue_url": issue_data["html_url"], "issue_number": issue_data["number"]}), idempotency_key)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "created", "issue_url": issue_data["html_url"]}
    else:
        cur.execute(
            "update actions_log set status = %s, error_message = %s where idempotency_key = %s;",
            ("failed", resp.text[:500], idempotency_key)
        )
        conn.commit()
        cur.close()
        conn.close()
        raise HTTPException(status_code=502, detail=f"GitHub API error: {resp.status_code}")

