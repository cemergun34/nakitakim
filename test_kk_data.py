from db.database import get_connection
conn = get_connection()
try:
    print(conn.execute("SELECT alinan_tutar1 FROM kredikartidata").fetchall())
except Exception as e:
    print("ERROR:", e)
