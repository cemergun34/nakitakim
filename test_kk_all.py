from db.database import get_connection
conn = get_connection()
try:
    rows = conn.execute("SELECT aciklama, alinan_tutar1 FROM kredikartidata").fetchall()
    for r in rows:
        print(dict(r))
except Exception as e:
    print("ERROR:", e)
