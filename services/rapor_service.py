"""
Rapor servis katmanı — nakitGuncelTablo.php mantığının Python karşılığı.
Gelir / Gider / Gelir-Gider / Finansal Öngörüler sekmeleri için veri hazırlar.
"""
from datetime import datetime
from typing import Optional
from db.database import get_connection

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _year():
    return datetime.now().year


# ─── GELİR SEKME ──────────────────────────────────────────────────────────────

def get_gelir_urun_hizmet_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Ürün/Hizmet bazlı aylık gelir tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                teslim_sekli AS kategori,
                CAST(strftime('%m', tarih_date) AS INTEGER) AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'genelHesap'
              AND strftime('%Y', tarih_date) = ?
              AND gelir > 0
            GROUP BY teslim_sekli, ay
            ORDER BY teslim_sekli, ay
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gelir_tahsilat_turu_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Tahsilat türü (Havale/Nakit/Kart...) bazlı aylık gelir tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                odeme_sekli AS kategori,
                CAST(strftime('%m', tarih_date) AS INTEGER) AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'kasa'
              AND strftime('%Y', tarih_date) = ?
              AND gelir > 0
            GROUP BY odeme_sekli, ay
            ORDER BY odeme_sekli, ay
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gelir_sube_bazli_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Şube bazlı aylık gelir tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                COALESCE(sube, 'Merkez') AS kategori,
                CAST(strftime('%m', tarih_date) AS INTEGER) AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND strftime('%Y', tarih_date) = ?
              AND gelir > 0
            GROUP BY sube, ay
            ORDER BY sube, ay
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gelir_aylik_tutar_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Aylık toplam gelir tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                CAST(strftime('%m', tarih_date) AS INTEGER) AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND strftime('%Y', tarih_date) = ?
              AND gelir > 0
            GROUP BY ay
            ORDER BY ay
        """, (userid, musterino, str(yil))).fetchall()

        monthly = {r["ay"]: float(r["tutar"]) for r in rows}
        return {
            "aylar": AYLAR,
            "satirlar": [{"kategori": "Gelir Toplamı",
                          "aylik": [monthly.get(i+1, 0) for i in range(12)],
                          "yillik_toplam": sum(monthly.values())}],
            "genel_toplam": sum(monthly.values()),
        }
    finally:
        conn.close()


# ─── GİDER SEKME ──────────────────────────────────────────────────────────────

def get_gider_dagilim_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Gider dağılımı (teslim_sekli bazlı) aylık tablo."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                COALESCE(teslim_sekli, 'Diğer') AS kategori,
                CAST(strftime('%m', tarih_date) AS INTEGER) AS ay,
                COALESCE(SUM(gider), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor IN ('gider', 'genelHesap')
              AND strftime('%Y', tarih_date) = ?
              AND gider > 0
            GROUP BY teslim_sekli, ay
            ORDER BY teslim_sekli, ay
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gider_odeme_turu_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Ödeme türü bazlı aylık gider tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                COALESCE(odeme_sekli, 'Diğer') AS kategori,
                CAST(strftime('%m', tarih_date) AS INTEGER) AS ay,
                COALESCE(SUM(gider), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND strftime('%Y', tarih_date) = ?
              AND gider > 0
            GROUP BY odeme_sekli, ay
            ORDER BY odeme_sekli, ay
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


# ─── GELİR GİDER SEKME ───────────────────────────────────────────────────────

def get_gunluk_mali_durum(userid: int, musterino: int, ay: int, yil: Optional[int] = None) -> list:
    """Seçili ay için günlük mali durum tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                tarih_date AS tarih,
                COALESCE(SUM(gelir), 0) AS gunluk_gelir,
                COALESCE(SUM(gider), 0) AS gunluk_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND strftime('%Y', tarih_date) = ?
              AND CAST(strftime('%m', tarih_date) AS INTEGER) = ?
            GROUP BY tarih_date
            ORDER BY tarih_date
        """, (userid, musterino, str(yil), ay)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_vadesi_gecen_tahsilatlar(userid: int, musterino: int) -> list:
    """Vadesi geçmiş tahsilatlar — cari hesap tablosundan."""
    conn = get_connection()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT
                unvan AS cari_unvan,
                COALESCE(SUM(CAST(toplam AS REAL)), 0) AS hesap_bakiyesi,
                MAX(tarih) AS son_islem_tarihi,
                MIN(tarih) AS vade_tarihi
            FROM faturalar
            WHERE userid = ?
              AND musterino = ?
              AND gelirGiderMod = 'gelir'
              AND tarih < ?
            GROUP BY unvan
            ORDER BY hesap_bakiyesi DESC
        """, (userid, musterino, today)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── FİNANSAL ÖNGÖRÜLER ──────────────────────────────────────────────────────

def get_ongoru_gelir_tablo(userid: int, yil: Optional[int] = None) -> dict:
    """Nakit akış parametrelerinden öngörü gelir tablosu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                hesapadi AS kategori,
                CAST(strftime('%m', sonTarih) AS INTEGER) AS ay,
                COALESCE(SUM(plan), 0) AS tutar
            FROM nakitakis_Hareket
            WHERE musteriNo = ?
              AND strftime('%Y', sonTarih) = ?
            GROUP BY hesapadi, ay
            ORDER BY hesapadi, ay
        """, (str(userid), str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


# ─── YARDIMCI FONKSİYONLAR ────────────────────────────────────────────────────

def _pivot_to_monthly_table(rows) -> dict:
    """
    (kategori, ay, tutar) satırlarını pivot tabloya çevirir.
    Dönüş: {"aylar": [...], "satirlar": [...], "genel_toplam": float}
    """
    from collections import defaultdict

    pivot: dict[str, list] = defaultdict(lambda: [0.0] * 12)

    for row in rows:
        kat = row["kategori"] or "Diğer"
        ay  = int(row["ay"]) - 1  # 0-indexed
        if 0 <= ay < 12:
            pivot[kat][ay] += float(row["tutar"])

    satirlar = []
    genel_toplam = 0.0
    for kat in sorted(pivot.keys()):
        aylik = pivot[kat]
        yillik = sum(aylik)
        genel_toplam += yillik
        satirlar.append({
            "kategori": kat,
            "aylik": aylik,
            "yillik_toplam": yillik,
        })

    # GENEL TOPLAM satırı
    if satirlar:
        toplam_aylik = [sum(s["aylik"][i] for s in satirlar) for i in range(12)]
        satirlar.append({
            "kategori": "GENEL TOPLAM",
            "aylik": toplam_aylik,
            "yillik_toplam": genel_toplam,
            "is_total": True,
        })

    return {
        "aylar": AYLAR,
        "satirlar": satirlar,
        "genel_toplam": genel_toplam,
    }
