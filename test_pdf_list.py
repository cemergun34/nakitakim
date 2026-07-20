from db.database import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("""
    SELECT
        SUBSTRING(aciklama FROM 1 FOR POSITION('.pdf' IN LOWER(aciklama)) + 3) AS pdf_adi,
        COUNT(*) AS kayit_sayisi,
        MIN(tarih) AS ilk_tarih,
        MAX(tarih) AS son_tarih,
        COALESCE(SUM(CASE WHEN alinan_tutar1 >= 0 THEN alinan_tutar1 ELSE 0 END), 0) AS borc,
        COALESCE(SUM(CASE WHEN alinan_tutar1 < 0 THEN alinan_tutar1 ELSE 0 END), 0) AS odeme,
        COALESCE(SUM(alinan_tutar1), 0) AS net,
        MAX(banka) AS banka
    FROM kredikartidata
    WHERE userid = '19' AND musterino = '1'
      AND LOWER(aciklama) LIKE '%.pdf%'
    GROUP BY SUBSTRING(aciklama FROM 1 FOR POSITION('.pdf' IN LOWER(aciklama)) + 3)
    ORDER BY MIN(tarih) DESC
""")
rows = cur.fetchall()
print(f"{len(rows)} PDF dosyası bulundu:")
for r in rows:
    print(dict(r))
