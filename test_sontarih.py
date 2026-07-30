from db.database import get_connection
conn = get_connection()

# Check what's in nakitakis_parametre
rows = conn.execute("""
    SELECT id, ilktarih, sontarih, sozlesmeno, sozlesmetarih
    FROM nakitakis_parametre
    LIMIT 10
""").fetchall()
print("nakitakis_parametre örnek kayıtlar:")
for r in rows:
    print(dict(r))

# Check what's in moy_beyannameler
beyanlar = conn.execute("""
    SELECT kayit_no, belge_turu, beyan_tarih_1, beyan_tarih_2, belge_no, onay_tarihi
    FROM moy_beyannameler
    LIMIT 5
""").fetchall()
print("\nmoy_beyannameler örnek:")
for b in beyanlar:
    print(dict(b))
