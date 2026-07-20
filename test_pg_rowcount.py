import psycopg2
from db.db_config import get_pg_params

conn = psycopg2.connect(**get_pg_params())
conn.autocommit = True
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS test_rc (
    id SERIAL PRIMARY KEY,
    val TEXT UNIQUE
);
""")
cur.execute("INSERT INTO test_rc (val) VALUES ('A') ON CONFLICT DO NOTHING")
print("First insert:", cur.rowcount)
cur.execute("INSERT INTO test_rc (val) VALUES ('A') ON CONFLICT DO NOTHING")
print("Second insert (dup):", cur.rowcount)
