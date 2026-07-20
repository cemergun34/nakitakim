from db.database import get_connection
conn = get_connection()
try:
    cur = conn.cursor()
    cur.execute("SELECT tarih, alinan_tutar1, aciklama FROM kredikartidata ORDER BY tarih DESC LIMIT 20")
    for row in cur.fetchall():
        print(dict(row))
except Exception as e:
    print("ERROR:", e)
