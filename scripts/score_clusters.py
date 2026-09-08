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

BATCH_PROMPT_TEMPLATE = '''You will analyze {n_clusters} SEPARATE clusters of customer feedback.
Each cluster is clearly delimited below with a CLUSTER_ID and its own feedback items, each with
an ID. Analyze each cluster independently - do not mix themes or citations between clusters.

For EACH cluster, determine:
1. theme_label: 5-8 words describing what this specific cluster is about
2. is_actionable: true only if it describes a specific, fixable product problem or request.
   false if it is generic praise, vague complaints with no specific issue, or incoherent noise.
3. If is_actionable is true: impact (1-5), confidence (0.0-1.0), effort (1-5)
   If false: set impact, confidence, effort to null
4. justification: one sentence
5. cited_feedback_ids: EXACT IDs from THAT cluster's item list only. Never cite an ID from a
   different cluster. Do not invent IDs.

Respond with ONLY valid JSON, no markdown, as a list in this exact shape:
[{{"cluster_id": 12, "theme_label": "...", "is_actionable": true, "impact": 4, "confidence": 0.8,
"effort": 2, "justification": "...", "cited_feedback_ids": ["id1", "id2"]}}, ...]

{clusters_text}
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
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("select cluster_id, count(*) from feedback_items where cluster_id != -1 group by cluster_id;")
cluster_counts = dict(cur.fetchall())
total_non_noise = sum(cluster_counts.values())

cur.execute("select cluster_id from cluster_insights;")
already_done = {r[0] for r in cur.fetchall()}
remaining = [cid for cid in cluster_counts if cid not in already_done]
print(f"Remaining clusters to score: {len(remaining)}")

BATCH_SIZE = 5
for batch_start in range(0, len(remaining), BATCH_SIZE):
    batch_ids = remaining[batch_start:batch_start + BATCH_SIZE]

    cluster_data = {}
    clusters_text_parts = []
    for cid in batch_ids:
        cur.execute(
            "select id, raw_text from feedback_items where cluster_id = %s limit 12;",
            (cid,),
        )
        sample = cur.fetchall()
        cluster_data[cid] = {str(i): t for i, t in sample}
        items_str = "\\n".join(f"  [{str(i)}] {t[:250]}" for i, t in sample)
        clusters_text_parts.append(f"=== CLUSTER_ID {cid} ===\\n{items_str}")

    clusters_text = "\\n\\n".join(clusters_text_parts)
    prompt = BATCH_PROMPT_TEMPLATE.format(n_clusters=len(batch_ids), clusters_text=clusters_text)

    try:
        results = call_gemini(prompt)
    except Exception as e:
        print(f"Batch {batch_ids}: FAILED - {e}")
        time.sleep(10)
        continue

    for result in results:
        cid = result.get("cluster_id")
        if cid not in cluster_data:
            print(f"WARNING: model returned unknown cluster_id {cid}, skipping")
            continue

        valid_ids = set(cluster_data[cid].keys())
        cited = result.get("cited_feedback_ids", [])
        valid_citations = [c for c in cited if c in valid_ids]
        invalid_citations = [c for c in cited if c not in valid_ids]
        if invalid_citations:
            print(f"Cluster {cid}: WARNING - {len(invalid_citations)} hallucinated/cross-cluster citation(s)")

        is_actionable = result.get("is_actionable", False)
        size = cluster_counts[cid]
        reach_pct = (size / total_non_noise) * 100
        impact = result.get("impact")
        confidence = result.get("confidence")
        effort = result.get("effort")
        rice = (size * impact * confidence / effort) if (is_actionable and impact and effort) else 0.0

        cur.execute(
            """
            insert into cluster_insights
            (cluster_id, theme_label, is_actionable, reach_count, reach_pct, impact, confidence, effort, rice_score, justification, cited_feedback_ids)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[])
            """,
            (
                cid, result.get("theme_label"), is_actionable, size, reach_pct,
                impact, confidence, effort, rice, result.get("justification"), valid_citations,
            ),
        )
        conn.commit()
        print(f"Cluster {cid}: '{result.get('theme_label')}' actionable={is_actionable} RICE={rice:.2f} valid_citations={len(valid_citations)}/{len(cited)}")

    time.sleep(8)

cur.close()
conn.close()
print("Done.")
