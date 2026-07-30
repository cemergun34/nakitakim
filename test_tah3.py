from services.moy_service import moy_kaydet_veriler

def progress(msg):
    print(msg)

res = moy_kaydet_veriler(1, 2026, progress_cb=progress)
print(res)

from db.database import get_connection
conn = get_connection()
thk = conn.execute("SELECT kayit_no, belge_tipi, belge_turu, beyan_tarih_1 FROM moy_beyannameler WHERE belge_tipi='Thk' LIMIT 5").fetchall()
print("Thk kayıtlar:", [dict(r) for r in thk])

from services.moy_service import get_local_beyannameler
res = get_local_beyannameler(1, '20250225', '770.01')
print("\nget_local_beyannameler('770.01', '20250225'):")
for r in res:
    print(r['belge_tipi'], r['belge_turu'], r['kayit_no'])
