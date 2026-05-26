"""
Detay Servis — KPI kartlarına tıklandığında açılan
şube özet + işlem listesi diyaloğu için veri servisi.
"""
from typing import Optional
from db.database import get_connection


# ─── ŞUBE BAZLI ÖZET ─────────────────────────────────────────────────────────

def get_nakit_kasa_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Nakit Kasa Gelir kartına tıklandığında gösterilecek
    şube bazlı gelir/gider özeti (hareketler tablosundan).
    """
    conn = get_connection()
    try:
        # Önce seçili yılı dene, veri yoksa tüm yılları al
        for yil_filter in [str(yil), None]:
            if yil_filter:
                rows = conn.execute("""
                    SELECT
                        COALESCE(s.subeAck, '(Şubesiz)') AS sube_adi,
                        CAST(COALESCE(h.sube, 0) AS INTEGER) AS sube_id,
                        ROUND(SUM(CASE WHEN h.gelirGider='gelir' THEN h.alinan_tutar1 ELSE 0 END), 2) AS toplam_gelir,
                        ROUND(SUM(CASE WHEN h.gelirGider='gider' THEN h.alinan_tutar1 ELSE 0 END), 2) AS toplam_gider,
                        COUNT(*) AS kayit_sayisi
                    FROM hareketler h
                    LEFT JOIN Subeler s ON CAST(h.sube AS INTEGER) = s.id
                    WHERE h.musteriNo = ? AND length(h.tarih) >= 10
                      AND substr(h.tarih, 7, 4) = ?
                    GROUP BY h.sube ORDER BY toplam_gelir DESC
                """, (musterino, yil_filter)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT
                        COALESCE(s.subeAck, '(Şubesiz)') AS sube_adi,
                        CAST(COALESCE(h.sube, 0) AS INTEGER) AS sube_id,
                        ROUND(SUM(CASE WHEN h.gelirGider='gelir' THEN h.alinan_tutar1 ELSE 0 END), 2) AS toplam_gelir,
                        ROUND(SUM(CASE WHEN h.gelirGider='gider' THEN h.alinan_tutar1 ELSE 0 END), 2) AS toplam_gider,
                        COUNT(*) AS kayit_sayisi
                    FROM hareketler h
                    LEFT JOIN Subeler s ON CAST(h.sube AS INTEGER) = s.id
                    WHERE h.musteriNo = ? AND length(h.tarih) >= 10
                    GROUP BY h.sube ORDER BY toplam_gelir DESC
                """, (musterino,)).fetchall()
            if rows:
                break
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_genel_hesap_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Nakit Kasa / Genel Hesap kartına tıklandığında
    genel_hesap_hareketleri tablosundan şube bazlı özet.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                ROUND(SUM(g.gelir), 2)  AS toplam_gelir,
                ROUND(SUM(g.gider), 2)  AS toplam_gider,
                COUNT(*)                AS kayit_sayisi
            FROM genel_hesap_hareketleri g
            WHERE g.userid = ?
              AND g.musteri_no = ?
              AND strftime('%Y', g.tarih_date) = ?
            GROUP BY g.sube
            ORDER BY toplam_gelir DESC
        """, (userid, musterino, str(yil))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_fatura_sube_ozet(userid: int, yil: int, mod: str) -> list[dict]:
    """
    Kesilen / Gelen Fatura kartına tıklandığında unvan bazlı özet.
    mod: 'gelir' (kesilen) | 'gider' (gelen)
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                COALESCE(unvan, '(Bilinmeyen)') AS sube_adi,
                ROUND(SUM(CAST(toplam AS REAL)), 2) AS toplam_tutar,
                COUNT(*) AS kayit_sayisi
            FROM faturalar
            WHERE userid = ?
              AND substr(tarih, 1, 4) = ?
              AND gelirGiderMod = ?
            GROUP BY unvan
            ORDER BY toplam_tutar DESC
            LIMIT 50
        """, (userid, str(yil), mod)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_gider_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Gider Pusulası, Kurum Ödemeleri, Maaş Kira SMM kartı için
    teslim_sekli bazlı gider özeti.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                COALESCE(g.teslim_sekli, 'Diğer') AS sube_adi,
                ROUND(SUM(g.gider), 2)  AS toplam_gider,
                ROUND(SUM(g.gelir), 2)  AS toplam_gelir,
                COUNT(*)                AS kayit_sayisi
            FROM genel_hesap_hareketleri g
            WHERE g.userid = ?
              AND g.musteri_no = ?
              AND g.nerden_geliyor IN ('gider', 'genelHesap')
              AND strftime('%Y', g.tarih_date) = ?
              AND g.gider > 0
            GROUP BY g.teslim_sekli
            ORDER BY toplam_gider DESC
        """, (userid, musterino, str(yil))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── İŞLEM LİSTESİ (DETAY) ───────────────────────────────────────────────────

def get_hareketler_detay(userid: int, musterino: int, yil: int,
                          sube_id=None, sube_adi: str = None) -> list[dict]:
    """
    Belirli şube için hareketler tablosundan işlem listesi.
    sube_id None ise tüm şubeler, değilse sadece o şube.
    """
    conn = get_connection()
    try:
        # Önce seçili yılı dene, veri yoksa tüm yılları al
        for yil_filter in [str(yil), None]:
            if sube_id is not None:
                if yil_filter:
                    rows = conn.execute("""
                        SELECT
                            h.id, h.tarih, h.aciklama,
                            s.subeAck AS sube_adi,
                            h.alinan_tutar1 AS tutar,
                            h.gelirGider, h.odeme_sekli1, h.hesapKodu,
                            h.faturaNo, h.faturaUnvan, h.teslim_sekli
                        FROM hareketler h
                        LEFT JOIN Subeler s ON CAST(h.sube AS INTEGER) = s.id
                        WHERE h.musteriNo = ?
                          AND CAST(h.sube AS INTEGER) = ?
                          AND substr(h.tarih, 7, 4) = ?
                        ORDER BY h.tarih DESC, h.id DESC
                        LIMIT 500
                    """, (musterino, sube_id, yil_filter)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT
                            h.id, h.tarih, h.aciklama,
                            s.subeAck AS sube_adi,
                            h.alinan_tutar1 AS tutar,
                            h.gelirGider, h.odeme_sekli1, h.hesapKodu,
                            h.faturaNo, h.faturaUnvan, h.teslim_sekli
                        FROM hareketler h
                        LEFT JOIN Subeler s ON CAST(h.sube AS INTEGER) = s.id
                        WHERE h.musteriNo = ?
                          AND CAST(h.sube AS INTEGER) = ?
                        ORDER BY h.tarih DESC, h.id DESC
                        LIMIT 500
                    """, (musterino, sube_id)).fetchall()
            else:
                if yil_filter:
                    rows = conn.execute("""
                        SELECT
                            h.id, h.tarih, h.aciklama,
                            COALESCE(s.subeAck, '(Şubesiz)') AS sube_adi,
                            h.alinan_tutar1 AS tutar,
                            h.gelirGider, h.odeme_sekli1, h.hesapKodu,
                            h.faturaNo, h.faturaUnvan, h.teslim_sekli
                        FROM hareketler h
                        LEFT JOIN Subeler s ON CAST(h.sube AS INTEGER) = s.id
                        WHERE h.musteriNo = ?
                          AND substr(h.tarih, 7, 4) = ?
                        ORDER BY h.tarih DESC, h.id DESC
                        LIMIT 500
                    """, (musterino, yil_filter)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT
                            h.id, h.tarih, h.aciklama,
                            COALESCE(s.subeAck, '(Şubesiz)') AS sube_adi,
                            h.alinan_tutar1 AS tutar,
                            h.gelirGider, h.odeme_sekli1, h.hesapKodu,
                            h.faturaNo, h.faturaUnvan, h.teslim_sekli
                        FROM hareketler h
                        LEFT JOIN Subeler s ON CAST(h.sube AS INTEGER) = s.id
                        WHERE h.musteriNo = ?
                        ORDER BY h.tarih DESC, h.id DESC
                        LIMIT 500
                    """, (musterino,)).fetchall()
            
            if rows:
                break
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_genel_hesap_detay(userid: int, musterino: int, yil: int,
                           sube_adi: str = None) -> list[dict]:
    """
    genel_hesap_hareketleri tablosundan şube filtreli işlem listesi.
    """
    conn = get_connection()
    try:
        if sube_adi and sube_adi != "(Şubesiz)":
            rows = conn.execute("""
                SELECT
                    g.id, g.tarih_date AS tarih, g.aciklama,
                    g.sube AS sube_adi, g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori,
                    g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ?
                  AND g.musteri_no = ?
                  AND g.sube = ?
                  AND strftime('%Y', g.tarih_date) = ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 500
            """, (userid, musterino, sube_adi, str(yil))).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    g.id, g.tarih_date AS tarih, g.aciklama,
                    COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                    g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori,
                    g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ?
                  AND g.musteri_no = ?
                  AND strftime('%Y', g.tarih_date) = ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 500
            """, (userid, musterino, str(yil))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_fatura_detay(userid: int, yil: int, mod: str,
                      unvan: str = None) -> list[dict]:
    """
    faturalar tablosundan belirli ünvan filtreli liste.
    """
    conn = get_connection()
    try:
        if unvan:
            rows = conn.execute("""
                SELECT id, tarih, unvan, vergino, vergiDairesi,
                       faturano, toplam, gelirGiderMod, faturaMod,
                       formNo, kaynak, yuklenmeTarihi, xml_dosya
                FROM faturalar
                WHERE userid = ?
                  AND substr(tarih, 1, 4) = ?
                  AND gelirGiderMod = ?
                  AND unvan = ?
                ORDER BY tarih DESC, id DESC
            """, (userid, str(yil), mod, unvan)).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, tarih, unvan, vergino, vergiDairesi,
                       faturano, toplam, gelirGiderMod, faturaMod,
                       formNo, kaynak, yuklenmeTarihi, xml_dosya
                FROM faturalar
                WHERE userid = ?
                  AND substr(tarih, 1, 4) = ?
                  AND gelirGiderMod = ?
                ORDER BY tarih DESC, id DESC
                LIMIT 500
            """, (userid, str(yil), mod)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_kurum_odemeleri_detay(musterino: int, yil: int,
                               ay: Optional[int] = None) -> list[dict]:
    """
    Kurum Ödemeleri detay listesi — nakitakis_Parametre tablosundan.
    PHP: ajax/nakitAkimParametreAjaxGider.php ile birebir aynı sorgu.

    Sütunlar: hesapKodu, unvan, vergiNo, ilkTarih, sonTarih,
              sozlesmeNo, sozlesmeTarih, tutar, aciklama
    ilkTarih DB formatı: YYYYMMDD (20260126)
    """
    conn = get_connection()
    try:
        if ay and ay != 0:
            # Ay filtreli: substr(ilkTarih,5,2) = '01' gibi
            ay_str = f"{ay:02d}"
            rows = conn.execute("""
                SELECT
                    id, hesapKodu, hesapAck, unvan, vergiNo,
                    ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                    tutar, gelirGider, aciklama
                FROM nakitakis_Parametre
                WHERE musteriNo = ?
                  AND gelirGider = 'gider'
                  AND substr(ilkTarih, 1, 4) = ?
                  AND substr(ilkTarih, 5, 2) = ?
                ORDER BY ilkTarih DESC
            """, (musterino, str(yil), ay_str)).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    id, hesapKodu, hesapAck, unvan, vergiNo,
                    ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                    tutar, gelirGider, aciklama
                FROM nakitakis_Parametre
                WHERE musteriNo = ?
                  AND gelirGider = 'gider'
                  AND substr(ilkTarih, 1, 4) = ?
                ORDER BY ilkTarih DESC
            """, (musterino, str(yil))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_kurum_odemeleri_detay_tarih(musterino: int,
                                    ilk_tarih: str,
                                    son_tarih: str) -> list[dict]:
    """
    Tarih aralığı bazlı Kurum Ödemeleri detay listesi.
    DateEdit picker'dan gelen YYYYMMDD formatında ilk/son tarih alır.
    Örnek: ilk_tarih='20260201', son_tarih='20260228'
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                id, hesapKodu, hesapAck, unvan, vergiNo,
                ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                tutar, gelirGider, aciklama
            FROM nakitakis_Parametre
            WHERE musteriNo = ?
              AND gelirGider = 'gider'
              AND ilkTarih >= ?
              AND ilkTarih <= ?
            ORDER BY ilkTarih DESC
        """, (musterino, ilk_tarih, son_tarih)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
