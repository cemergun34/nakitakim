from services.moy_service import get_moy_bilgileri, _moy_connect

bilgi = get_moy_bilgileri(1)
host = bilgi["url"]; user = bilgi["username"]
password = bilgi["sifre"]; kayit_nom = bilgi["moyKayitNo"]

cnx = _moy_connect(host, user, password)
cursor = cnx.cursor(dictionary=True)

# Tüm belge tipi/türü kombinasyonlarını listele
cursor.execute("""
    SELECT DISTINCT Belge_Tipi, Belge_Turu, COUNT(*) as adet
    FROM beyanname_listeleri
    WHERE Musteri_Kayit_No = %s
    GROUP BY Belge_Tipi, Belge_Turu
    ORDER BY Belge_Tipi, Belge_Turu
""", (kayit_nom,))
rows = cursor.fetchall()
print("Mevcut Belge_Tipi / Belge_Turu kombinasyonları:")
for r in rows:
    print(r)
cursor.close(); cnx.close()
