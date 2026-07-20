from db.database import get_connection
conn = get_connection()
try:
    users = conn.execute("SELECT id, kullanici_adi, sifre FROM uyelik").fetchall()
    print("PostgreSQL Users:", [dict(u) for u in users])
except Exception as e:
    print("ERROR:", e)
