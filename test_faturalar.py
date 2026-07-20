from db.database import get_connection
conn = get_connection()
try:
    print("faturalar grouped by userid:", conn.execute("SELECT userid, count(*) FROM faturalar GROUP BY userid").fetchall())
except Exception as e:
    print("ERROR:", e)
