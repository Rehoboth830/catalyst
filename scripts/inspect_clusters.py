import os
from dotenv import load_dotenv
import psycopg2

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# Check a mixed-source cluster and two single-source clusters
for cluster_id in [6, 44, 41]:
    cur.execute(
        "select raw_text, source from feedback_items where cluster_id = %s limit 4;",
        (cluster_id,)
    )
    rows = cur.fetchall()
    print(f"\\n=== CLUSTER {cluster_id} ({len(rows)} sample rows) ===")
    for text, source in rows:
        preview = text[:150].replace(chr(10), " ")
        print(f"[{source}] {preview}...")

cur.close()
conn.close()
