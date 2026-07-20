from db.database import get_connection
conn = get_connection()
try:
    print("womsi_pos count:", conn.execute("SELECT COUNT(*) FROM womsi_pos").fetchone()[0])
except Exception as e:
    print("womsi_pos ERROR:", e)

try:
    print("paytr count:", conn.execute("SELECT COUNT(*) FROM paytr").fetchone()[0])
except Exception as e:
    print("paytr ERROR:", e)

try:
    print("faturalar count:", conn.execute("SELECT COUNT(*) FROM faturalar").fetchone()[0])
except Exception as e:
    print("faturalar ERROR:", e)
