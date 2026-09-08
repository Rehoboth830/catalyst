import os
import numpy as np
from dotenv import load_dotenv
import psycopg2
import hdbscan
import umap
from collections import Counter

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

def parse_embedding(pg_str):
    return [float(x) for x in pg_str.strip("[]").split(",")]

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("select id, embedding, source from feedback_items where embedding is not null;")
rows = cur.fetchall()
ids = [r[0] for r in rows]
sources = [r[2] for r in rows]
embeddings = np.array([parse_embedding(r[1]) for r in rows])

print("Reducing dimensionality with UMAP (384 -> 5 dims)...")
reducer = umap.UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42)
reduced = reducer.fit_transform(embeddings)

print("Clustering reduced embeddings...")
clusterer = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5, metric="euclidean")
labels = clusterer.fit_predict(reduced)

n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = list(labels).count(-1)

print(f"Clusters found: {n_clusters}")
print(f"Noise points (unclustered): {n_noise} ({n_noise/len(labels)*100:.1f}%)")

sizes = Counter(labels)
sizes.pop(-1, None)
print("Cluster size distribution (all):", sorted(sizes.values(), reverse=True))

for cluster_id in list(sizes.keys())[:10]:
    cluster_sources = [sources[i] for i, l in enumerate(labels) if l == cluster_id]
    src_counts = Counter(cluster_sources)
    print(f"Cluster {cluster_id} (size {sizes[cluster_id]}): source mix = {dict(src_counts)}")

for item_id, label in zip(ids, labels):
    cur.execute("update feedback_items set cluster_id = %s where id = %s;", (int(label), item_id))

conn.commit()
cur.close()
conn.close()
