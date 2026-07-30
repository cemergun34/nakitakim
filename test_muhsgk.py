from db.database import get_connection
from services.moy_service import get_local_beyannameler

conn = get_connection()

# Check what beyannameler exist for musteri_no=1
rows = conn.execute("""
    SELECT kayit_no, belge_turu, beyan_tarih_1, beyan_tarih_2, belge_durumu
    FROM moy_beyannameler 
    WHERE musteri_no = 1
    ORDER BY beyan_tarih_1, belge_turu
""").fetchall()
print("Tüm moy_beyannameler:")
for r in rows:
    print(dict(r))

# Test get_local_beyannameler for a 770.01 date
print("\n\nget_local_beyannameler(1, '20250225', '770.01'):")
res = get_local_beyannameler(1, '20250225', '770.01')
for r in res:
    print(r)
