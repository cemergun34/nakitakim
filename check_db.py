from db.database import get_connection
conn = get_connection()
try:
    cur = conn.cursor()
    row = cur.execute("SELECT SUM(alinan_tutar1) AS net, SUM(CASE WHEN alinan_tutar1 > 0 THEN alinan_tutar1 ELSE 0 END) AS borc FROM kredikartidata").fetchone()
    print(dict(row))
except Exception as e:
    print("ERROR:", e)
