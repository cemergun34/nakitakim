"""
Rapor servis katmanı — nakitGuncelTablo.php mantığının Python karşılığı.
Gelir / Gider / Gelir-Gider / Finansal Öngörüler sekmeleri için veri hazırlar.
SQLite ve PostgreSQL uyumlu sorgular kullanır.
"""
from datetime import datetime
from typing import Optional
from db.database import get_connection
from db.db_config import get_mode

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _year():
    return datetime.now().year


def _month_expr(col: str) -> str:
    """Ay ifadesi: SQLite strftime vs PostgreSQL EXTRACT."""
    if get_mode() == "postgres":
        return f"EXTRACT(MONTH FROM CAST({col} AS DATE))::INTEGER"
    return f"CAST(strftime('%m', {col}) AS INTEGER)"


def _year_expr(col: str) -> str:
    """Yıl ifadesi: SQLite strftime vs PostgreSQL EXTRACT."""
    if get_mode() == "postgres":
        return f"EXTRACT(YEAR FROM CAST({col} AS DATE))::TEXT"
    return f"strftime('%Y', {col})"


# ─── GELİR SEKME ──────────────────────────────────────────────────────────────

def get_gelir_urun_hizmet_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Ürün/Hizmet bazlı aylık gelir tablosu."""
    yil = yil or _year()
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                teslim_sekli AS kategori,
                {ay_ex} AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'genelHesap'
              AND {yil_ex} = ?
              AND gelir > 0
            GROUP BY teslim_sekli, {ay_ex}
            ORDER BY teslim_sekli, {ay_ex}
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gelir_tahsilat_turu_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Tahsilat türü (Havale/Nakit/Kart...) bazlı aylık gelir tablosu."""
    yil = yil or _year()
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                odeme_sekli AS kategori,
                {ay_ex} AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'kasa'
              AND {yil_ex} = ?
              AND gelir > 0
            GROUP BY odeme_sekli, {ay_ex}
            ORDER BY odeme_sekli, {ay_ex}
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gelir_sube_bazli_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Şube bazlı aylık gelir tablosu."""
    yil = yil or _year()
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(sube, 'Merkez') AS kategori,
                {ay_ex} AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND {yil_ex} = ?
              AND gelir > 0
            GROUP BY sube, {ay_ex}
            ORDER BY sube, {ay_ex}
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gelir_aylik_tutar_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Aylık toplam gelir tablosu."""
    yil = yil or _year()
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                {ay_ex} AS ay,
                COALESCE(SUM(gelir), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND {yil_ex} = ?
              AND gelir > 0
            GROUP BY {ay_ex}
            ORDER BY {ay_ex}
        """, (userid, musterino, str(yil))).fetchall()

        monthly = {}
        for r in rows:
            r_d = dict(r)
            monthly[int(r_d["ay"])] = float(r_d["tutar"])

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
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(teslim_sekli, 'Diğer') AS kategori,
                {ay_ex} AS ay,
                COALESCE(SUM(gider), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor IN ('gider', 'genelHesap')
              AND {yil_ex} = ?
              AND gider > 0
            GROUP BY teslim_sekli, {ay_ex}
            ORDER BY teslim_sekli, {ay_ex}
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


def get_gider_odeme_turu_tablo(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Ödeme türü bazlı aylık gider tablosu."""
    yil = yil or _year()
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(odeme_sekli, 'Diğer') AS kategori,
                {ay_ex} AS ay,
                COALESCE(SUM(gider), 0) AS tutar
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND {yil_ex} = ?
              AND gider > 0
            GROUP BY odeme_sekli, {ay_ex}
            ORDER BY odeme_sekli, {ay_ex}
        """, (userid, musterino, str(yil))).fetchall()

        return _pivot_to_monthly_table(rows)
    finally:
        conn.close()


# ─── GELİR GİDER SEKME ───────────────────────────────────────────────────────

def get_gunluk_mali_durum(userid: int, musterino: int, ay: int, yil: Optional[int] = None) -> list:
    """Seçili ay için günlük mali durum tablosu."""
    yil = yil or _year()
    ay_ex  = _month_expr("tarih_date")
    yil_ex = _year_expr("tarih_date")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                tarih_date AS tarih,
                COALESCE(SUM(gelir), 0) AS gunluk_gelir,
                COALESCE(SUM(gider), 0) AS gunluk_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND {yil_ex} = ?
              AND {ay_ex} = ?
            GROUP BY tarih_date
            ORDER BY tarih_date
        """, (userid, musterino, str(yil), ay)).fetchall()
        return list(rows)
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
        return list(rows)
    finally:
        conn.close()


# ─── FİNANSAL ÖNGÖRÜLER ──────────────────────────────────────────────────────

def get_ongoru_gelir_tablo(userid: int, yil: Optional[int] = None) -> dict:
    """Nakit akış parametrelerinden öngörü gelir tablosu."""
    yil = yil or _year()
    # nakitakis_hareket.sonTarih TEXT formatı: YYYY-MM-DD veya YYYYMMDD
    # PostgreSQL uyumlu sorgu — tarih_date yerine sonTarih kullanıyoruz
    if get_mode() == "postgres":
        ay_ex  = "EXTRACT(MONTH FROM CAST(\"sonTarih\" AS DATE))::INTEGER"
        yil_ex = "EXTRACT(YEAR  FROM CAST(\"sonTarih\" AS DATE))::TEXT"
        col_mno = 'musterino'
    else:
        ay_ex  = "CAST(strftime('%m', sonTarih) AS INTEGER)"
        yil_ex = "strftime('%Y', sonTarih)"
        col_mno = 'musterino'

    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                hesapadi AS kategori,
                {ay_ex} AS ay,
                COALESCE(SUM(plan), 0) AS tutar
            FROM nakitakis_hareket
            WHERE {col_mno} = ?
              AND {yil_ex} = ?
            GROUP BY hesapadi, {ay_ex}
            ORDER BY hesapadi, {ay_ex}
        """, (str(musterino), str(yil))).fetchall()

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
        r_d = dict(row)
        kat = r_d.get("kategori") or "Diğer"
        try:
            ay = int(r_d.get("ay") or 0) - 1  # 0-indexed
        except (ValueError, TypeError):
            ay = -1
        if 0 <= ay < 12:
            pivot[kat][ay] += float(r_d.get("tutar") or 0)

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
