from db.database import get_connection
conn = get_connection()
try:
    print(conn.execute("SELECT userid, musterino, COUNT(*) FROM womsi_pos GROUP BY userid, musterino").fetchall())
except Exception as e:
    print("ERROR:", e)
