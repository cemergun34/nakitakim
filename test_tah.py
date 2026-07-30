from services.moy_service import get_moy_bilgileri, _moy_connect
import sys

bilgi = get_moy_bilgileri(1)
if not bilgi.get("success"):
    print("Moy bilgisi yok:", bilgi)
    sys.exit(1)

host = bilgi["url"]
user = bilgi["username"]
password = bilgi["sifre"]
kayit_nom = bilgi["moyKayitNo"]

cnx = _moy_connect(host, user, password)
cursor = cnx.cursor(dictionary=True)

# Tahakkuk fişi kayıtlarını sorgula
cursor.execute("""
    SELECT Kayit_No, Belge_Tipi, Belge_Turu, Donem_adi,
           Beyan_Tarih_1, Beyan_Tarih_2, Belge_Durumu
    FROM beyanname_listeleri
    WHERE Musteri_Kayit_No = %s
      AND Belge_Tipi = 'Tah'
    ORDER BY Kayit_No DESC
    LIMIT 15
""", (kayit_nom,))
rows = cursor.fetchall()
print(f"'TAH' tipi kayıtlar ({len(rows)} adet):")
for r in rows:
    print(r)

cursor.close()
cnx.close()
