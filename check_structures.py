from db.database import get_connection
conn = get_connection()
cur = conn.cursor()

# kredikartidata sütunları
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'kredikartidata' ORDER BY ordinal_position")
print("=== kredikartidata ===")
for row in cur.fetchall():
    print(dict(row))
