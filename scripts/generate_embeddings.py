import os
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

print("Loading model (first run downloads weights)...")
model = SentenceTransformer("all-MiniLM-L6-v2")

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("select id, raw_text from feedback_items where embedding is null;")
rows = cur.fetchall()
print(f"Rows needing embeddings: {len(rows)}")

ids = [r[0] for r in rows]
texts = [r[1] for r in rows]

print("Encoding...")
embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

for item_id, emb in zip(ids, embeddings):
    cur.execute(
        "update feedback_items set embedding = %s where id = %s;",
        (emb.tolist(), item_id),
    )

conn.commit()

cur.execute("select count(*) from feedback_items where embedding is not null;")
total_embedded = cur.fetchone()[0]
cur.close()
conn.close()

print(f"Total rows with embeddings: {total_embedded}")
