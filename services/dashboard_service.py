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
    """Maaş, Kira ve Müşavirlik Giderleri — sadece genel_hesap_hareketleri'nden.
    Not: Moy verileri (770.01, 730.08) Kurum Ödemeleri kartına gidiyor.
    """
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
    """Kurum Ödemeleri (Vergi ödemeleri + Moy nakitakis_Parametre verileri).
    PHP: nakitAkimParametreAjaxGider.php ile aynı tablo — nakitakis_Parametre
    hesapKodu 770.01 (SGK/vergi ödemeleri) ve 730.08 (işçilik/müşavirlik)

    Kaynaklar:
      1) genel_hesap_hareketleri — eski manuel girişler (Vergi, SGK, Kurum vb.)
      2) nakitakis_Parametre    — Moy entegrasyonundan gelen 770.01 + 730.08
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        # Kaynak 1 — genel_hesap_hareketleri
        row1 = conn.execute("""
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
        toplam1 = float(row1["toplam"] or 0)

        # Kaynak 2 — nakitakis_Parametre (PHP: nakitAkimParametreAjaxGider.php mantığı)
        # 770.01 = vergi giderleri (Moy 360 hesap kodu → vergi)
        # 730.08 = işçilik/müşavirlik (Moy 361 hesap kodu)
        # ilkTarih formatı: YYYYMMDD (20260126 gibi) — ilk 4 karakter yıl
        row2 = conn.execute("""
            SELECT COALESCE(SUM(CAST(tutar AS REAL)), 0) AS toplam
            FROM nakitakis_Parametre
            WHERE musteriNo = ?
              AND hesapKodu IN ('770.01', '730.08')
              AND gelirGider = 'gider'
              AND substr(ilkTarih, 1, 4) = ?
        """, (musterino, str(yil))).fetchone()
        toplam2 = float(row2["toplam"] or 0)

        return {
            "toplam":       toplam1 + toplam2,
            "genel_hesap":  toplam1,
            "moy":          toplam2,
        }
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
    """
    Kredi kartı KPI özeti.
    tarih kolonu 'DD.MM.YYYY' → son 4 karakter yıl.
    BORC  = pozitif alinan_tutar1 toplamı (harcama)
    ODEME = negatif alinan_tutar1 toplamı (geri ödeme / iade)
    NET   = BORC + ODEME  (admin.php göstergesi)
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN alinan_tutar1 >= 0 THEN alinan_tutar1 ELSE 0 END), 0) AS toplam_borc,
                COALESCE(SUM(CASE WHEN alinan_tutar1 <  0 THEN alinan_tutar1 ELSE 0 END), 0) AS toplam_odeme,
                COALESCE(SUM(alinan_tutar1), 0)                                               AS toplam_net
            FROM kredikartiData
            WHERE userid = ?
              AND substr(tarih, -4) = ?
        """, (str(userid), str(yil))).fetchone()
        return {
            "borc":  float(row["toplam_borc"]  or 0),
            "odeme": float(row["toplam_odeme"] or 0),
            "net":   float(row["toplam_net"]   or 0),
        }
    except Exception:
        return {"borc": 0.0, "odeme": 0.0, "net": 0.0}
    finally:
        conn.close()


def get_kredi_karti_kart_ozet(userid: int, yil: Optional[int] = None) -> list[dict]:
    """
    Kart bazlı özet — admin.php modal ilk seviyesi.
    Her kart için: borc (harcama), odeme (iade/ödeme), net, kayıt sayısı.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                Banka,
                COUNT(*) AS kayit_sayisi,
                COALESCE(SUM(CASE WHEN alinan_tutar1 >= 0 THEN alinan_tutar1 ELSE 0 END), 0) AS borc,
                COALESCE(SUM(CASE WHEN alinan_tutar1 <  0 THEN alinan_tutar1 ELSE 0 END), 0) AS odeme,
                COALESCE(SUM(alinan_tutar1), 0) AS net,
                MIN(tarih) AS ilk_tarih,
                MAX(tarih) AS son_tarih
            FROM kredikartiData
            WHERE userid = ?
              AND substr(tarih, -4) = ?
            GROUP BY Banka
            ORDER BY borc DESC
        """, (str(userid), str(yil))).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_kredi_karti_ekstre_detay(
    userid: int,
    banka: str,
    yil: Optional[int] = None,
    ilk_tarih: Optional[str] = None,
    son_tarih: Optional[str] = None,
) -> list[dict]:
    """
    Belirli bir karta ait ekstre satırları.
    Tarih filtresi DD.MM.YYYY formatında verilir.
    alinan_tutar1 negatif olanlar = ödeme/iade satırı.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        params: list = [str(userid), banka]

        def tr2iso(d: str) -> str:
            """DD.MM.YYYY → YYYY-MM-DD (SQLite karşılaştırması için)"""
            p = d.split(".")
            return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else d

        if ilk_tarih and son_tarih:
            where_extra = """
                AND (
                    substr(tarih,-4)||'-'||substr(tarih,4,2)||'-'||substr(tarih,1,2)
                    BETWEEN ? AND ?
                )
            """
            params += [tr2iso(ilk_tarih), tr2iso(son_tarih)]
        else:
            where_extra = "AND substr(tarih, -4) = ?"
            params.append(str(yil))

        rows = conn.execute(f"""
            SELECT
                id, tarih, aciklama, Tutar,
                CAST(alinan_tutar1 AS REAL) AS alinan_tutar1,
                hesapKodu, womsiskey, islem, Banka,
                CASE WHEN alinan_tutar1 < 0 THEN 'odeme' ELSE 'borc' END AS tur
            FROM kredikartiData
            WHERE userid = ?
              AND Banka = ?
              {where_extra}
            ORDER BY
                substr(tarih,-4)||'-'||substr(tarih,4,2)||'-'||substr(tarih,1,2) ASC,
                id ASC
        """, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
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
