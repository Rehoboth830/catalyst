import os
import requests
import pandas as pd
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

PARQUET_URL = "https://huggingface.co/datasets/sealuzh/app_reviews/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"
LOCAL_FILE = "app_reviews.parquet"
SAMPLE_SIZE = 2000

# Download once, locally, instead of hitting the API repeatedly
if not os.path.exists(LOCAL_FILE):
    print("Downloading parquet file...")
    resp = requests.get(PARQUET_URL, timeout=60)
    resp.raise_for_status()
    with open(LOCAL_FILE, "wb") as f:
        f.write(resp.content)
    print(f"Downloaded {len(resp.content)} bytes")

df = pd.read_parquet(LOCAL_FILE)
print(f"Full dataset shape: {df.shape}")

# Drop empty/near-empty reviews before sampling, so the 2000 we keep are all usable
df = df[df["review"].str.strip().str.len() >= 10]

sample = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=42)

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

inserted = 0
for _, row in sample.iterrows():
    cur.execute(
        """
        insert into feedback_items (source, source_id, raw_text, rating, submitted_at, metadata)
        values (%s, %s, %s, %s, %s, %s)
        """,
        (
            "sealuzh_app_reviews",
            row.get("package_name"),
            row.get("review"),
            int(row.get("star")) if pd.notna(row.get("star")) else None,
            None,
            Json({"date_raw": str(row.get("date")), "package_name": row.get("package_name")}),
        ),
    )
    inserted += 1

conn.commit()
cur.execute("select count(*) from feedback_items;")
total = cur.fetchone()[0]
cur.close()
conn.close()

print(f"Inserted this run: {inserted}")
print(f"Total rows in feedback_items: {total}")
