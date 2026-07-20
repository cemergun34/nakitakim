from db.database import get_connection
conn = get_connection()
cur = conn.cursor()

# Tabloda ne var
cur.execute("SELECT DISTINCT banka, hesapkodu, COUNT(*) as adet, SUM(alinan_tutar1) as toplam FROM kredikartidata GROUP BY banka, hesapkodu ORDER BY banka")
rows = cur.fetchall()
print("=== kredikartidata - Kart Özeti ===")
for r in rows:
    print(dict(r))

print()
# YapıKredi 1635 için özel arama
cur.execute("SELECT tarih, aciklama, alinan_tutar1, banka, hesapkodu FROM kredikartidata WHERE banka ILIKE '%1635%' OR aciklama ILIKE '%1635%' OR hesapkodu = '309.01.008' OR hesapkodu = '309.01.010' LIMIT 10")
rows2 = cur.fetchall()
print("=== YK 1635 kayıtları ===")
for r in rows2:
    print(dict(r))
