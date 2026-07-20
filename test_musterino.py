from db.database import get_connection
conn = get_connection()
try:
    print("uyelik table columns:", conn.execute("SELECT * FROM uyelik LIMIT 1").fetchone().keys())
    print("uyelik data:", dict(conn.execute("SELECT id, kullanici_adi, musteri_no FROM uyelik LIMIT 5").fetchone()))
except Exception as e:
    print("uyelik ERROR:", e)

try:
    print("womsi_pos data:", dict(conn.execute("SELECT userid, musterino FROM womsi_pos LIMIT 1").fetchone()))
except Exception as e:
    print("womsi_pos ERROR:", e)

try:
    print("faturalar data:", dict(conn.execute("SELECT userid, musterino FROM faturalar LIMIT 1").fetchone()))
except Exception as e:
    print("faturalar ERROR:", e)
