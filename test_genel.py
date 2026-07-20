from db.database import get_connection
conn = get_connection()
try:
    print(conn.execute("SELECT * FROM genel_hesap_hareketleri LIMIT 1").fetchone().keys())
except Exception as e:
    print("genel_hesap_hareketleri ERROR:", e)

try:
    print(conn.execute("SELECT * FROM banka_bakiye LIMIT 1").fetchone().keys())
except Exception as e:
    print("banka_bakiye ERROR:", e)
