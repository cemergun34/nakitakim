from db.database import get_connection
conn = get_connection()
try:
    print(conn.execute("SELECT MIN(islemTarihi), MAX(islemTarihi) FROM womsi_pos").fetchone())
except Exception as e:
    print("ERROR:", e)
