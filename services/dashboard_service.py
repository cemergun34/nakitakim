"""
Dashboard servis katmanı — PHP admin_panel.php mantığının Python karşılığı.
Tüm sorgular SQLite üzerinden çalışır.
"""
from datetime import datetime
from typing import Optional
from db.database import get_connection


def _year() -> int:
    return datetime.now().year


# ─── KPI KARTI SORGULARI ──────────────────────────────────────────────────────

def get_nakit_kasa_toplam(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Nakit Kasa Gelir ve Ödeme toplamları."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(gelir), 0) AS toplam_gelir,
                COALESCE(SUM(gider), 0) AS toplam_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'kasa'
              AND strftime('%Y', tarih_date) = ?
        """, (userid, musterino, str(yil))).fetchone()

        gelir = float(row["toplam_gelir"] or 0)
        gider = float(row["toplam_gider"] or 0)
        return {"gelir": gelir, "gider": gider, "net": gelir - gider}
    finally:
        conn.close()


def get_gider_toplam(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Gider pusulası (Nakit Kasa Ödeme) toplamı."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(gider), 0) AS toplam_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'gider'
              AND strftime('%Y', tarih_date) = ?
        """, (userid, musterino, str(yil))).fetchone()
        return {"gider": float(row["toplam_gider"] or 0)}
    finally:
        conn.close()


def get_genel_hesap_toplam(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Genel Hesap Tablosu net bakiyesi."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(gelir), 0) AS toplam_gelir,
                COALESCE(SUM(gider), 0) AS toplam_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'genelHesap'
              AND strftime('%Y', tarih_date) = ?
        """, (userid, musterino, str(yil))).fetchone()
        gelir = float(row["toplam_gelir"] or 0)
        gider = float(row["toplam_gider"] or 0)
        return {"gelir": gelir, "gider": gider, "net": gelir - gider}
    finally:
        conn.close()


def get_fatura_toplamlar(userid: int, yil: Optional[int] = None) -> dict:
    """Kesilen (gelir) ve Gelen (gider) fatura toplamları."""
    yil = yil or _year()
    conn = get_connection()
    try:
        def _sum(mod):
            row = conn.execute("""
                SELECT COALESCE(SUM(CAST(toplam AS REAL)), 0) AS t
                FROM faturalar
                WHERE userid = ?
                  AND substr(tarih, 1, 4) = ?
                  AND gelirGiderMod = ?
            """, (userid, str(yil), mod)).fetchone()
            return float(row["t"] or 0)

        return {"kesilen": _sum("gelir"), "gelen": _sum("gider")}
    finally:
        conn.close()


def get_gider_pusulasi(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Gider Pusulası (Parça Alımı / Cihaz Alımı) toplamı."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(gelir), 0) AS toplam_gelir,
                COALESCE(SUM(gider), 0) AS toplam_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%')
              AND strftime('%Y', tarih_date) = ?
        """, (userid, musterino, str(yil))).fetchone()
        gelir = float(row["toplam_gelir"] or 0)
        gider = float(row["toplam_gider"] or 0)
        return {"gelir": gelir, "gider": gider, "net": gelir - gider}
    finally:
        conn.close()


def get_maaş_kira_smm(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Maaş, Kira ve Müşavirlik Giderleri."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(gider), 0) AS toplam
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'gider'
              AND (teslim_sekli LIKE '%Maaş%'
                OR teslim_sekli LIKE '%Kira%'
                OR teslim_sekli LIKE '%Müşavirlik%'
                OR teslim_sekli LIKE '%SMM%')
              AND strftime('%Y', tarih_date) = ?
        """, (userid, musterino, str(yil))).fetchone()
        return {"toplam": float(row["toplam"] or 0)}
    finally:
        conn.close()


def get_kurum_odemeleri(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Kurum Ödemeleri (Vergi ödemeleri)."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(gider), 0) AS toplam
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'gider'
              AND (teslim_sekli LIKE '%Vergi%'
                OR teslim_sekli LIKE '%SGK%'
                OR teslim_sekli LIKE '%Kurum%')
              AND strftime('%Y', tarih_date) = ?
        """, (userid, musterino, str(yil))).fetchone()
        return {"toplam": float(row["toplam"] or 0)}
    finally:
        conn.close()


def get_sanal_pos_toplam(userid: int, yil: Optional[int] = None) -> dict:
    """Sanal POS (sanalPos tablosu veya hareketler) toplamı."""
    yil = yil or _year()
    conn = get_connection()
    try:
        # hareketler tablosundan nakit-dışı gelirler (kart tahsilat)
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN gelirGider='gelir' THEN alinan_tutar1 ELSE 0 END), 0) AS islem,
                COALESCE(SUM(CASE WHEN gelirGider='gider' THEN alinan_tutar1 ELSE 0 END), 0) AS odeme
            FROM hareketler
            WHERE userid = ?
              AND odeme_sekli1 IN (
                  SELECT id FROM odemeSekli
                  WHERE odemesekliAck LIKE '%Pos%' OR odemesekliAck LIKE '%Kart%'
              )
        """, (userid,)).fetchone()
        return {
            "islem": float(row["islem"] or 0),
            "odeme": float(row["odeme"] or 0),
        }
    finally:
        conn.close()


def get_kredi_karti_toplam(userid: int, yil: Optional[int] = None) -> dict:
    """Kredi kartı borç ve ödeme toplamı."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(borc), 0)  AS toplam_borc,
                COALESCE(SUM(odeme), 0) AS toplam_odeme
            FROM kredikartiData
            WHERE userid = ?
              AND strftime('%Y', tarih) = ?
        """, (userid, str(yil))).fetchone()
        return {
            "borc":  float(row["toplam_borc"]  or 0),
            "odeme": float(row["toplam_odeme"] or 0),
        }
    except Exception:
        return {"borc": 0.0, "odeme": 0.0}
    finally:
        conn.close()


def get_subeler(userid: int) -> list:
    """Kullanıcının şubelerini döndürür."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, subeAck FROM Subeler WHERE userid=? ORDER BY id", (userid,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_monthly_comparison(userid: int, musterino: int, yil: Optional[int] = None) -> list[dict]:
    """Yıllık Gelir-Gider karşılaştırma grafiği için aylık toplamlar."""
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT 
                strftime('%m', tarih_date) as ay,
                SUM(gelir) as toplam_gelir,
                SUM(gider) as toplam_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ? AND musteri_no = ? AND strftime('%Y', tarih_date) = ?
            GROUP BY ay
            ORDER BY ay
        """, (userid, musterino, str(yil))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_dashboard_data(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Tek seferde tüm dashboard KPI verilerini döndürür."""
    yil = yil or _year()
    return {
        "yil": yil,
        "nakit_kasa": get_nakit_kasa_toplam(userid, musterino, yil),
        "gider": get_gider_toplam(userid, musterino, yil),
        "genel_hesap": get_genel_hesap_toplam(userid, musterino, yil),
        "faturalar": get_fatura_toplamlar(userid, yil),
        "gider_pusulasi": get_gider_pusulasi(userid, musterino, yil),
        "maas_kira_smm": get_maaş_kira_smm(userid, musterino, yil),
        "kurum_odemeleri": get_kurum_odemeleri(userid, musterino, yil),
        "sanal_pos": get_sanal_pos_toplam(userid, yil),
        "kredi_karti": get_kredi_karti_toplam(userid, yil),
        "monthly_chart": get_monthly_comparison(userid, musterino, yil),
    }
