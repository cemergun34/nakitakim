from db.database import get_connection
conn = get_connection()
try:
    print(conn.execute("SELECT id, kullanici_adi, bagli_hesap, musterino, yetki FROM uyelik WHERE id = 19").fetchone())
except Exception as e:
    print("ERROR:", e)
