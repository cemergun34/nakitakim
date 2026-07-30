from services.moy_service import moy_kaydet_veriler
from db.database import get_connection

def progress(msg): print(msg)

# 2025 yılını da senkronize et
print("=== 2025 sync ===")
res = moy_kaydet_veriler(1, 2025, progress_cb=progress)
print(res)

conn = get_connection()
thk_muhsgk = conn.execute("""
    SELECT kayit_no, belge_tipi, belge_turu, beyan_tarih_1, beyan_tarih_2
    FROM moy_beyannameler
    WHERE belge_tipi='Thk' AND belge_turu='MUHSGK'
    ORDER BY beyan_tarih_1
""").fetchall()
print("\nThk/MUHSGK kayıtları:")
for r in thk_muhsgk:
    print(dict(r))

from services.moy_service import get_local_beyannameler
print("\nget_local_beyannameler('770.01', '20250225'):")
res = get_local_beyannameler(1, '20250225', '770.01')
for r in res:
    print(r['belge_tipi'], r['belge_turu'], r['kayit_no'])
