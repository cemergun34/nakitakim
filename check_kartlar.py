from db.database import get_connection
conn = get_connection()
try:
    cur = conn.cursor()
    cur.execute("SELECT * FROM key_kartlari LIMIT 5")
    rows = cur.fetchall()
    if rows:
        print("Columns:", [desc[0] for desc in cur.description])
        for row in rows:
            print(dict(row))
    else:
        print("No rows found")
except Exception as e:
    print("ERROR:", e)
