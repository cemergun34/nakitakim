from db.database import get_connection
conn = get_connection()
try:
    cur = conn.cursor()
    cur.execute("DELETE FROM kredikartidata")
    conn.commit()
    print("Deleted rows:", cur.rowcount)
except Exception as e:
    print("ERROR:", e)
