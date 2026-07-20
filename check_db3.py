from db.database import get_connection
conn = get_connection()
try:
    cur = conn.cursor()
    cur.execute("SELECT islem_tarihi, alinan_tutar1, aciklama, banka_adi FROM kredikartidata ORDER BY islem_tarihi DESC LIMIT 10")
    for row in cur.fetchall():
        print(dict(row))
except Exception as e:
    print("ERROR:", e)
