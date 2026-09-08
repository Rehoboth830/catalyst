import os
import requests
from dotenv import load_dotenv
import psycopg2

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

BASE_URL = "http://localhost:8000"
TOP_N = 5

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute(
    "select cluster_id, theme_label, adjusted_score from cluster_insights where is_actionable = true order by adjusted_score desc limit %s;",
    (TOP_N,)
)
top_clusters = cur.fetchall()
cur.close()
conn.close()

print(f"Orchestrating top {len(top_clusters)} priority clusters...\\n")

for cluster_id, theme, score in top_clusters:
    print(f"=== Cluster {cluster_id}: {theme} (score {score:.1f}) ===")

    # Safe, pre-approved action: auto-execute
    resp = requests.post(f"{BASE_URL}/tools/create_ticket", json={"cluster_id": cluster_id})
    result = resp.json()
    print(f"  create_ticket: {result.get('status')}")

    # Higher-consequence actions: queue for human approval, do not execute
    resp = requests.post(f"{BASE_URL}/tools/draft_stakeholder_update", json={"cluster_id": cluster_id})
    result = resp.json()
    print(f"  draft_stakeholder_update: {result.get('status')}")

    resp = requests.post(f"{BASE_URL}/tools/schedule_review", json={"cluster_id": cluster_id})
    result = resp.json()
    print(f"  schedule_review: {result.get('status')}")
    print()

# Show the full pending queue - this is what a human sees, waiting for their decision
resp = requests.get(f"{BASE_URL}/actions/pending")
pending = resp.json()
print(f"Total actions now awaiting human approval: {len(pending)}")
