import os
import sys
import requests
from dotenv import load_dotenv
import psycopg2
from scipy.stats import spearmanr

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

results = []

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))

def skip(name, reason):
    results.append(("SKIP", name, reason))
    print(f"[SKIP] {name} - {reason}")

def parse_pg_array(pg_str):
    if not pg_str or pg_str == "{}":
        return set()
    return set(pg_str.strip("{}").split(","))

print("=" * 60)
print("PHASE 1: Environment & Architecture")
print("=" * 60)

for var in ["SUPABASE_URL", "SUPABASE_ANON_KEY", "DATABASE_URL", "GEMINI_API_KEY", "GITHUB_TOKEN", "GITHUB_REPO"]:
    check(f"Env var {var} loaded", bool(os.environ.get(var)))

try:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select version();")
    version = cur.fetchone()[0]
    check("Database connection (session pooler)", True, version[:40])
    cur.execute("select extname from pg_extension where extname = 'vector';")
    check("pgvector extension enabled", cur.fetchone() is not None)
except Exception as e:
    check("Database connection", False, str(e))
    print("FATAL: cannot continue without database. Stopping.")
    sys.exit(1)

print()
print("=" * 60)
print("PHASE 2: Feedback Ingestion")
print("=" * 60)

cur.execute("select count(*) from feedback_items;")
total_items = cur.fetchone()[0]
check("Total feedback_items == 4000", total_items == 4000, f"actual: {total_items}")

cur.execute("select source, count(*) from feedback_items group by source;")
source_counts = dict(cur.fetchall())
check("sealuzh_app_reviews == 2000", source_counts.get("sealuzh_app_reviews") == 2000, str(source_counts.get("sealuzh_app_reviews")))
check("tobibueck_support_tickets == 2000", source_counts.get("tobibueck_support_tickets") == 2000, str(source_counts.get("tobibueck_support_tickets")))

print()
print("=" * 60)
print("PHASE 3: Intelligence Engine")
print("=" * 60)

cur.execute("select count(*) from feedback_items where embedding is not null;")
embedded = cur.fetchone()[0]
check("All 4000 items embedded", embedded == 4000, f"actual: {embedded}")

cur.execute("select count(distinct cluster_id) from feedback_items where cluster_id != -1;")
n_clusters = cur.fetchone()[0]
check("48 clusters exist", n_clusters == 48, f"actual: {n_clusters}")

cur.execute("select count(*), count(*) filter (where is_actionable) from cluster_insights;")
total_scored, actionable = cur.fetchone()
check("All 48 clusters scored", total_scored == 48, f"actual: {total_scored}")
check("38 clusters actionable", actionable == 38, f"actual: {actionable}")

human_buckets = {
    3: 4, 4: 4, 0: 4, 2: 4, 16: 4, 20: 4, 26: 4, 41: 4, 29: 4, 5: 4, 22: 4,
    13: 3, 14: 3, 15: 3, 18: 3, 19: 3, 21: 3, 25: 3, 27: 3, 36: 3, 11: 3, 17: 3,
    7: 2, 9: 2, 10: 2, 12: 2, 35: 2, 38: 2, 40: 2, 42: 2,
    6: 1, 8: 1, 24: 1, 32: 1, 34: 1, 37: 1, 39: 1, 43: 1,
}
cur.execute("select cluster_id, adjusted_score from cluster_insights where is_actionable = true;")
data = dict(cur.fetchall())
human_scores = [human_buckets[cid] for cid in data]
system_scores = [data[cid] for cid in data]
corr, p = spearmanr(human_scores, system_scores)
check("Spearman correlation >= 0.30", corr >= 0.30, f"actual: {corr:.3f}")
check("Correlation statistically significant (p < 0.05)", p < 0.05, f"actual: p={p:.4f}")

cur.execute("select cluster_id, prd, cited_feedback_ids from cluster_insights where prd is not null;")
prd_rows = cur.fetchall()
check("5 PRDs generated", len(prd_rows) == 5, f"actual: {len(prd_rows)}")

import re
total_hallucinated = 0
for cid, prd, cited_ids in prd_rows:
    valid_ids = parse_pg_array(cited_ids)
    found = set(re.findall(r'ID:\s*([a-f0-9\-]+)', prd.get('evidence_summary', '')))
    total_hallucinated += len(found - valid_ids)
check("Zero hallucinated citations across all PRDs", total_hallucinated == 0, f"fabricated: {total_hallucinated}")

print()
print("=" * 60)
print("PHASE 4: Agent Tool Layer (database-level checks)")
print("=" * 60)

cur.execute("select count(*), count(distinct idempotency_key) from actions_log;")
total_actions, distinct_keys = cur.fetchone()
check("No duplicate idempotency keys", total_actions == distinct_keys, f"{total_actions} rows, {distinct_keys} distinct keys")

cur.execute("select count(*) from actions_log where action_type = 'create_ticket' and status = 'completed';")
check("At least 1 completed create_ticket", cur.fetchone()[0] >= 1)

print()
print("=" * 60)
print("PHASE 5: Orchestration & Approval (live API checks)")
print("=" * 60)

try:
    health = requests.get("http://localhost:8000/health", timeout=3)
    server_up = health.status_code == 200
except Exception:
    server_up = False

if not server_up:
    skip("Live API tests (pending queue, approve, reject)", "uvicorn not running on :8000 - start it and rerun for full coverage")
else:
    check("Server /health responds", True)
    cur.execute("select count(*) from actions_log where status = 'pending_approval';")
    check("Pending approval queue has entries", cur.fetchone()[0] > 0, f"count: {cur.fetchone()[0] if False else ''}")
    cur.execute("select count(*) from actions_log where status = 'rejected';")
    check("At least 1 rejected action exists (rejection path proven)", cur.fetchone()[0] >= 1)
    cur.execute("select count(*) from actions_log where status = 'completed' and requires_approval = true;")
    check("At least 1 approval-gated action completed after approval", cur.fetchone()[0] >= 1)

cur.close()
conn.close()

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
skipped = sum(1 for r in results if r[0] == "SKIP")
print(f"PASS: {passed}  FAIL: {failed}  SKIP: {skipped}  TOTAL: {len(results)}")
if failed > 0:
    print("\\nFAILURES:")
    for status, name, detail in results:
        if status == "FAIL":
            print(f"  - {name}: {detail}")
