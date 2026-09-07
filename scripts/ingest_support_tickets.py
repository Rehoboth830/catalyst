import os
import pandas as pd
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

LOCAL_FILE = "support_tickets.parquet"
SAMPLE_SIZE = 2000

df = pd.read_parquet(LOCAL_FILE)
print(f"Full dataset shape: {df.shape}")

# English only - mixing languages would add noise to clustering, not signal
df = df[df["language"] == "en"]
print(f"English-only shape: {df.shape}")

# Combine subject + body into one feedback text, drop anything too short to be useful
df["combined_text"] = df["subject"].fillna("") + "\\n\\n" + df["body"].fillna("")
df = df[df["combined_text"].str.strip().str.len() >= 20]

sample = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=42)

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

inserted = 0
for idx, row in sample.iterrows():
    cur.execute(
        """
        insert into feedback_items (source, source_id, raw_text, rating, submitted_at, metadata)
        values (%s, %s, %s, %s, %s, %s)
        """,
        (
            "tobibueck_support_tickets",
            str(idx),
            row["combined_text"],
            None,
            None,
            Json({
                "type": row.get("type"),
                "queue": row.get("queue"),
                "priority": row.get("priority"),
                "language": row.get("language"),
            }),
        ),
    )
    inserted += 1

conn.commit()
cur.execute("select source, count(*) from feedback_items group by source;")
breakdown = cur.fetchall()
cur.close()
conn.close()

print(f"Inserted this run: {inserted}")
print("Breakdown by source:", breakdown)
