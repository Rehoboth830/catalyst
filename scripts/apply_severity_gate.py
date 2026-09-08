import os
from dotenv import load_dotenv
import psycopg2
from scipy.stats import spearmanr

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

SEVERITY_KEYWORDS = [
    "security", "vulnerab", "unauthorized", "breach", "encrypt",
    "medical", "patient", "compliance", "privacy", "overcharge", "unauthorized charge"
]

human_buckets = {
    3: 4, 4: 4, 0: 4, 2: 4, 16: 4, 20: 4, 26: 4, 41: 4, 29: 4, 5: 4, 22: 4,
    13: 3, 14: 3, 15: 3, 18: 3, 19: 3, 21: 3, 25: 3, 27: 3, 36: 3, 11: 3, 17: 3,
    7: 2, 9: 2, 10: 2, 12: 2, 35: 2, 38: 2, 40: 2, 42: 2,
    6: 1, 8: 1, 24: 1, 32: 1, 34: 1, 37: 1, 39: 1, 43: 1,
}

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("alter table cluster_insights add column if not exists is_severity_override boolean default false;")
cur.execute("alter table cluster_insights add column if not exists adjusted_score float;")

cur.execute("select cluster_id, theme_label, rice_score from cluster_insights where is_actionable = true;")
rows = cur.fetchall()

flagged = []
for cluster_id, theme_label, rice in rows:
    is_severity = any(kw in theme_label.lower() for kw in SEVERITY_KEYWORDS)
    adjusted = (1000 + rice) if is_severity else rice
    if is_severity:
        flagged.append((cluster_id, theme_label))
    cur.execute(
        "update cluster_insights set is_severity_override = %s, adjusted_score = %s where cluster_id = %s;",
        (is_severity, adjusted, cluster_id)
    )

conn.commit()

print(f"Flagged as severity override ({len(flagged)}):")
for cid, label in flagged:
    print(f"  {cid}: {label}")

# Recompute correlation with the adjusted score, same human buckets as before
cur.execute("select cluster_id, rice_score, adjusted_score from cluster_insights where is_actionable = true;")
data = cur.fetchall()
ids = [r[0] for r in data]
human_scores = [human_buckets[cid] for cid in ids]
old_scores = [r[1] for r in data]
new_scores = [r[2] for r in data]

old_corr, old_p = spearmanr(human_scores, old_scores)
new_corr, new_p = spearmanr(human_scores, new_scores)

print(f"\\nBEFORE (raw RICE):      correlation={old_corr:.3f}, p={old_p:.4f}")
print(f"AFTER (severity-gated): correlation={new_corr:.3f}, p={new_p:.4f}")

cur.close()
conn.close()
