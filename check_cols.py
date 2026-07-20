from db.database import get_connection
conn = get_connection()
try:
    cur = conn.cursor()
    cur.execute("SELECT * FROM paytr LIMIT 1")
    cols = [desc[0] for desc in cur.cursor.description] if hasattr(cur, 'cursor') else []
    print("PAYTR columns:", cols)
except Exception as e:
    print("ERROR:", e)
