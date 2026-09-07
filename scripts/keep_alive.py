import os
import sys
import psycopg2
from datetime import datetime

try:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    cur.fetchone()
    cur.close()
    conn.close()
    print(f"[{datetime.utcnow().isoformat()}] Keep-alive ping SUCCESS")
except Exception as e:
    print(f"[{datetime.utcnow().isoformat()}] Keep-alive ping FAILED: {e}")
    sys.exit(1)
