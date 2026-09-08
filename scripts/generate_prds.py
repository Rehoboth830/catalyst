import os
import time
import json
import requests
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.5-flash-lite:generateContent?key=" + os.environ["GEMINI_API_KEY"]
)

PRD_PROMPT_TEMPLATE = '''Write a short Product Requirements Document (PRD) for the following
customer-reported theme. Use ONLY the evidence provided below - do not invent additional context,
statistics, or claims not supported by the feedback shown.

THEME: {theme_label}
AFFECTED USERS (reach): {reach} reports out of {total} total feedback items analyzed
PRIORITY JUSTIFICATION: {justification}

SUPPORTING FEEDBACK (these are the ONLY sources you may reference):
{evidence_text}

Write the PRD with these sections:
1. Problem Statement (2-3 sentences, grounded in the feedback above)
2. Evidence Summary (reference specific feedback IDs from above using this format: [ID: xxxxx])
3. Proposed Solution (2-4 sentences, a reasonable engineering approach - do not overspecify implementation)
4. Success Metric (one concrete, measurable metric to know this is fixed)

Respond with ONLY valid JSON in this shape:
{{"problem_statement": "...", "evidence_summary": "...", "proposed_solution": "...", "success_metric": "..."}}
'''

def call_gemini(prompt):
    resp = requests.post(
        GEMINI_URL,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("select count(*) from feedback_items where cluster_id != -1;")
total = cur.fetchone()[0]

cur.execute('''
    alter table cluster_insights add column if not exists prd jsonb;
''')

cur.execute('''
    select cluster_id, theme_label, reach_count, justification, cited_feedback_ids
    from cluster_insights
    where is_actionable = true
    order by adjusted_score desc
    limit 5;
''')
top_clusters = cur.fetchall()

for cluster_id, theme, reach, justification, cited_ids in top_clusters:
    if not cited_ids:
        print(f"Cluster {cluster_id}: SKIPPED - no validated citations available")
        continue

    cur.execute(
        "select id, raw_text from feedback_items where id = ANY(%s);",
        (cited_ids,)
    )
    evidence_rows = cur.fetchall()
    evidence_text = "\\n".join(f"[ID: {i}] {t[:300]}" for i, t in evidence_rows)
    valid_evidence_ids = {str(i) for i, _ in evidence_rows}  # from query results, always correct Python UUIDs

    prompt = PRD_PROMPT_TEMPLATE.format(
        theme_label=theme, reach=reach, total=total,
        justification=justification, evidence_text=evidence_text
    )

    try:
        prd = call_gemini(prompt)
    except Exception as e:
        print(f"Cluster {cluster_id}: FAILED - {e}")
        time.sleep(10)
        continue

    # Verify: does the evidence_summary actually reference only real, provided IDs?
    import re
    cited_in_prd = set(re.findall(r"ID:\s*([a-f0-9\-]+)", prd.get("evidence_summary", "")))  # matches ID: format flexibly
    fabricated = cited_in_prd - valid_evidence_ids
    if fabricated:
        print(f"Cluster {cluster_id}: WARNING - PRD cited {len(fabricated)} ID(s) not in its provided evidence: {fabricated}")
    else:
        print(f"Cluster {cluster_id}: PRD citations verified clean ({len(cited_in_prd)} refs, all valid)")

    cur.execute(
        "update cluster_insights set prd = %s where cluster_id = %s;",
        (Json(prd), cluster_id)
    )
    conn.commit()
    print(f"Cluster {cluster_id} ('{theme}'): PRD generated")
    time.sleep(8)

cur.close()
conn.close()
print("Done.")


