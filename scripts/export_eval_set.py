import os
import csv
from dotenv import load_dotenv
import psycopg2

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute('''
    select cluster_id, theme_label, reach_count, rice_score, justification
    from cluster_insights
    where is_actionable = true
    order by cluster_id;
''')
clusters = cur.fetchall()

with open("..\\eval_set.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["cluster_id", "theme_label", "reach_count", "sample_feedback_1", "sample_feedback_2", "system_rice_score", "YOUR_PRIORITY_RANK"])

    for cluster_id, theme, reach, rice, justification in clusters:
        cur.execute(
            "select raw_text from feedback_items where cluster_id = %s limit 2;",
            (cluster_id,)
        )
        samples = [r[0][:200].replace(chr(10), " ") for r in cur.fetchall()]
        while len(samples) < 2:
            samples.append("")
        writer.writerow([cluster_id, theme, reach, samples[0], samples[1], round(rice, 1), ""])

cur.close()
conn.close()
print("Wrote eval_set.csv with", len(clusters), "actionable clusters")
