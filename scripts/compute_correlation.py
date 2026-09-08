import os
from dotenv import load_dotenv
import psycopg2
from scipy.stats import spearmanr

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

# Human judgment: bucket rank (4=urgent, 3=important, 2=nice-to-have, 1=low priority)
human_buckets = {
    3: 4, 4: 4, 0: 4, 2: 4, 16: 4, 20: 4, 26: 4, 41: 4, 29: 4, 5: 4, 22: 4,
    13: 3, 14: 3, 15: 3, 18: 3, 19: 3, 21: 3, 25: 3, 27: 3, 36: 3, 11: 3, 17: 3,
    7: 2, 9: 2, 10: 2, 12: 2, 35: 2, 38: 2, 40: 2, 42: 2,
    6: 1, 8: 1, 24: 1, 32: 1, 34: 1, 37: 1, 39: 1, 43: 1,
}

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("select cluster_id, rice_score from cluster_insights where is_actionable = true;")
rows = dict(cur.fetchall())
cur.close()
conn.close()

assert set(rows.keys()) == set(human_buckets.keys()), "Mismatch between scored clusters and human buckets"

human_scores = [human_buckets[cid] for cid in rows]
system_scores = [rows[cid] for cid in rows]

corr, p_value = spearmanr(human_scores, system_scores)
print(f"Clusters compared: {len(rows)}")
print(f"Spearman correlation (human buckets vs system RICE): {corr:.3f}")
print(f"P-value: {p_value:.4f}")
