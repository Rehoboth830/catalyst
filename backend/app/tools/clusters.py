import os
import psycopg2
from fastapi import APIRouter

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

@router.get("/clusters")
def list_clusters():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        select cluster_id, theme_label, reach_count, rice_score, adjusted_score,
               is_severity_override, justification, impact, confidence, effort, prd
        from cluster_insights
        where is_actionable = true
        order by adjusted_score desc;
    ''')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "cluster_id": r[0], "theme_label": r[1], "reach_count": r[2],
            "rice_score": round(r[3], 1) if r[3] else 0, "adjusted_score": round(r[4], 1) if r[4] else 0,
            "is_severity_override": r[5], "justification": r[6],
            "impact": r[7], "confidence": r[8], "effort": r[9], "prd": r[10],
        }
        for r in rows
    ]
