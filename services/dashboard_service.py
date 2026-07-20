"""
Dashboard servis katmanı — PHP admin_panel.php mantığının Python karşılığı.
SQLite ve PostgreSQL uyumludur (db.db_compat yardımcıları kullanılır).
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from db.database import get_connection
from db.db_compat import (
    yr, mo, left4, right4,
    tarih_iso_hareketler, tarih_yil_hareketler,
    tablo_var_expr, pg_musterino, pg_hesapkodu, pg_isinv
)


def _year() -> int:
    return datetime.now().year


# ─── KPI KARTI SORGULARI ──────────────────────────────────────────────────────

def _get_genel_hesap_all(
    userid: int, musterino: int, yil: int,
    ilk_tarih: Optional[str] = None,
    son_tarih: Optional[str] = None,
) -> dict:
    """genel_hesap_hareketleri üzerindeki tüm KPI verilerini TEK sorguda alır.

    ilk_tarih / son_tarih 'YYYY-MM-DD' formatında verilirse tarih aralığı filtresi uygulanır.
    Verilmezse yil bazlı filtre kullanılır.
    """
    conn = get_connection()
    try:
        if ilk_tarih and son_tarih:
            where_clause = "tarih_date >= ? AND tarih_date <= ?"
            params = (userid, musterino, ilk_tarih, son_tarih)
        else:
            where_clause = f"{yr('tarih_date')} = ?"
            params = (userid, musterino, str(yil))

        row = conn.execute(f"""
            SELECT
                -- Nakit Kasa (nerden_geliyor='kasa')
                COALESCE(SUM(CASE WHEN nerden_geliyor='kasa' THEN gelir ELSE 0 END), 0) AS kasa_gelir,
                COALESCE(SUM(CASE WHEN nerden_geliyor='kasa' THEN gider ELSE 0 END), 0) AS kasa_gider,

                -- Genel Hesap (nerden_geliyor='genelHesap')
                COALESCE(SUM(CASE WHEN nerden_geliyor='genelHesap' THEN gelir ELSE 0 END), 0) AS gh_gelir,
                COALESCE(SUM(CASE WHEN nerden_geliyor='genelHesap' THEN gider ELSE 0 END), 0) AS gh_gider,

                -- Gider Pusulası (teslim_sekli LIKE ...)
                COALESCE(SUM(CASE WHEN (teslim_sekli LIKE '%%Parça Alımı (Cihaz)%%' OR teslim_sekli LIKE '%%Cihaz Alımı%%') THEN gelir ELSE 0 END), 0) AS pusulasi_gelir,
                COALESCE(SUM(CASE WHEN (teslim_sekli LIKE '%%Parça Alımı (Cihaz)%%' OR teslim_sekli LIKE '%%Cihaz Alımı%%') THEN gider ELSE 0 END), 0) AS pusulasi_gider,

                -- Maaş/Kira/SMM
                COALESCE(SUM(CASE WHEN nerden_geliyor='gider'
                    AND (teslim_sekli LIKE '%%Maaş%%' OR teslim_sekli LIKE '%%Kira%%'
                      OR teslim_sekli LIKE '%%Müşavirlik%%' OR teslim_sekli LIKE '%%SMM%%')
                    THEN gider ELSE 0 END), 0) AS maas_kira_toplam,

                -- Kurum ödemeleri (genel_hesap kaynağı)
                COALESCE(SUM(CASE WHEN nerden_geliyor='gider'
                    AND (teslim_sekli LIKE '%%Vergi%%' OR teslim_sekli LIKE '%%SGK%%'
                      OR teslim_sekli LIKE '%%Kurum%%')
                    THEN gider ELSE 0 END), 0) AS kurum_toplam,

                -- Normal gider (nerden_geliyor='gider', tüm)
                COALESCE(SUM(CASE WHEN nerden_geliyor='gider' THEN gider ELSE 0 END), 0) AS gider_toplam

            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND {where_clause}
        """, params).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def get_nakit_kasa_toplam(userid: int, musterino: int, yil: Optional[int] = None, _ghh: dict = None) -> dict:
    """Nakit Kasa Gelir ve Ödeme toplamları."""
    yil = yil or _year()
    ghh = _ghh or _get_genel_hesap_all(userid, musterino, yil)
    gelir = float(ghh.get("kasa_gelir") or 0)
    gider = float(ghh.get("kasa_gider") or 0)
    return {"gelir": gelir, "gider": gider, "net": gelir - gider}


def get_gider_toplam(userid: int, musterino: int, yil: Optional[int] = None, _ghh: dict = None) -> dict:
    """Gider toplamları."""
    yil = yil or _year()
    ghh = _ghh or _get_genel_hesap_all(userid, musterino, yil)
    return {"gider": float(ghh.get("gider_toplam") or 0)}


def get_genel_hesap_toplam(userid: int, musterino: int, yil: Optional[int] = None, _ghh: dict = None) -> dict:
    """Genel Hesap Tablosu net bakiyesi."""
    yil = yil or _year()
    ghh = _ghh or _get_genel_hesap_all(userid, musterino, yil)
    gelir = float(ghh.get("gh_gelir") or 0)
    gider = float(ghh.get("gh_gider") or 0)
    return {"gelir": gelir, "gider": gider, "net": gelir - gider}


def get_fatura_toplamlar(userid: int, yil: Optional[int] = None) -> dict:
    """Kesilen (gelir) ve Gelen (gider) fatura toplamları — tek sorgu."""
    yil = yil or _year()
    conn = get_connection()
    try:
        row = conn.execute(f"""
            SELECT
                COALESCE(SUM(CASE WHEN gelirgidermod='gelir' THEN CAST(toplam AS REAL) ELSE 0 END), 0) AS kesilen,
                COALESCE(SUM(CASE WHEN gelirgidermod='gider' THEN CAST(toplam AS REAL) ELSE 0 END), 0) AS gelen
            FROM faturalar
            WHERE userid = ? AND {left4('tarih')} = ?
        """, (userid, str(yil))).fetchone()
        return {
            "kesilen": float(row["kesilen"] or 0),
            "gelen":   float(row["gelen"]   or 0),
        }
    finally:
        conn.close()


def get_gider_pusulasi(userid: int, musterino: int, yil: Optional[int] = None, _ghh: dict = None) -> dict:
    """Gider Pusulası toplamları."""
    yil = yil or _year()
    ghh = _ghh or _get_genel_hesap_all(userid, musterino, yil)
    gelir = float(ghh.get("pusulasi_gelir") or 0)
    gider = float(ghh.get("pusulasi_gider") or 0)
    return {"gelir": gelir, "gider": gider, "net": gelir - gider}


def get_maaş_kira_smm(userid: int, musterino: int, yil: Optional[int] = None, _ghh: dict = None) -> dict:
    """Maaş, Kira ve Müşavirlik Giderleri."""
    yil = yil or _year()
    ghh = _ghh or _get_genel_hesap_all(userid, musterino, yil)
    return {"toplam": float(ghh.get("maas_kira_toplam") or 0)}


def get_kurum_odemeleri(userid: int, musterino: int, yil: Optional[int] = None) -> dict:
    """Kurum Ödemeleri (Vergi ödemeleri + Moy nakitakis_parametre verileri).
    PHP: nakitAkimParametreAjaxGider.php ile aynı tablo — nakitakis_parametre
    hesapKodu 770.01 (SGK/vergi ödemeleri) ve 730.08 (işçilik/müşavirlik)

    Kaynaklar:
      1) genel_hesap_hareketleri — eski manuel girişler (Vergi, SGK, Kurum vb.)
      2) nakitakis_parametre    — Moy entegrasyonundan gelen 770.01 + 730.08
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        # Kaynak 1 — genel_hesap_hareketleri
        row1 = conn.execute(f"""
            SELECT COALESCE(SUM(gider), 0) AS toplam
            FROM genel_hesap_hareketleri
            WHERE userid = ?
              AND musteri_no = ?
              AND nerden_geliyor = 'gider'
              AND (teslim_sekli LIKE '%Vergi%'
                OR teslim_sekli LIKE '%SGK%'
                OR teslim_sekli LIKE '%Kurum%')
              AND {yr("tarih_date")} = ?
        """, (userid, musterino, str(yil))).fetchone()
        toplam1 = float(row1["toplam"] or 0)

        # Kaynak 2 — nakitakis_parametre (PG: kolon adları camelCase tırnaklı)
        # 770.01 = vergi giderleri  |  730.08 = işçilik/müşavirlik
        # ilkTarih formatı: YYYYMMDD — ilk 4 karakter yıl
        _mno = pg_musterino()
        _hkod = pg_hesapkodu()
        _ilkt = pg_isinv()
        row2 = conn.execute(f"""
            SELECT COALESCE(SUM(CAST(tutar AS REAL)), 0) AS toplam
            FROM nakitakis_parametre
            WHERE {_mno} = ?
              AND {_hkod} IN ('770.01', '730.08')
              AND gelirGider = 'gider'
              AND {left4(_ilkt)} = ?
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
    """
    PayTR Sanal POS toplamları — paytr tablosundan.
    PHP admin.php kartındaki değerlerin karşılığı.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        # Tablo var mı kontrol et (SQLite ve PG uyumlu)
        tablo_var = conn.execute(tablo_var_expr("paytr")).fetchone()[0]

        if not tablo_var:
            return {"islem": 0.0, "odeme": 0.0, "fark_val": 0.0, "son_guncelleme": ""}

        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(islemtutari), 0) AS islem, "
            "  COALESCE(SUM(odemetutari), 0) AS odeme "
            "FROM paytr WHERE userid = ?",
            (userid,)
        ).fetchone()

        islem = float(row["islem"] or 0)
        odeme = float(row["odeme"] or 0)
        fark  = odeme - islem

        try:
            log_row = conn.execute(
                "SELECT son_sync_tarihi FROM paytr_sync_log WHERE userid = ? "
                "ORDER BY id DESC LIMIT 1",
                (userid,)
            ).fetchone()
            son_sync = log_row["son_sync_tarihi"] if log_row else None
        except Exception:
            son_sync = None

        if son_sync:
            try:
                from datetime import datetime as _dt
                dt = _dt.fromisoformat(son_sync.split(" ")[0])
                son_guncelleme = f"Son güncelleme: {dt.strftime('%d.%m.%Y')}"
            except Exception:
                son_guncelleme = f"Son güncelleme: {son_sync[:10]}"
        else:
            son_guncelleme = ""

        return {
            "islem":          islem,
            "odeme":          odeme,
            "fark_val":       fark,
            "son_guncelleme": son_guncelleme,
        }
    except Exception:
        return {"islem": 0.0, "odeme": 0.0, "fark_val": 0.0, "son_guncelleme": ""}
    finally:
        conn.close()


def get_kredi_karti_toplam(userid: int, musterino: int, yil: Optional[int] = None, ilk_tarih: Optional[str] = None, son_tarih: Optional[str] = None) -> dict:
    """
    Kredi kartı KPI özeti.
    ilk_tarih/son_tarih verilirse ona göre filtreler.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        from db.db_compat import tarih_iso_hareketler
        
        params = [str(userid), str(musterino)]
        if ilk_tarih and son_tarih:
            where_extra = f"AND ({tarih_iso_hareketler('tarih')} BETWEEN ? AND ?)"
            params += [ilk_tarih, son_tarih]
        else:
            where_extra = f"AND {right4('tarih')} = ?"
            params.append(str(yil))
            
        row = conn.execute(f"""
            SELECT
                COALESCE(SUM(CASE WHEN alinan_tutar1 >= 0 THEN alinan_tutar1 ELSE 0 END), 0) AS toplam_borc,
                COALESCE(SUM(CASE WHEN alinan_tutar1 <  0 THEN alinan_tutar1 ELSE 0 END), 0) AS toplam_odeme,
                COALESCE(SUM(alinan_tutar1), 0)                                               AS toplam_net
            FROM kredikartidata
            WHERE userid = ? AND musterino = ?
              {where_extra}
        """, params).fetchone()
        return {
            "borc":  float(row["toplam_borc"]  or 0),
            "odeme": float(row["toplam_odeme"] or 0),
            "net":   float(row["toplam_net"]   or 0),
        }
    except Exception:
        return {"borc": 0.0, "odeme": 0.0, "net": 0.0}
    finally:
        conn.close()


def get_kredi_karti_kart_ozet(userid: int, musterino: int, yil: Optional[int] = None) -> list[dict]:
    """
    Her yüklenen PDF dosyası için bir satır döndürür.
    Sol panelde her PDF ayrı satır olarak görünür.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                SUBSTRING(aciklama FROM 1 FOR POSITION('.pdf' IN LOWER(aciklama)) + 3) AS pdf_adi,
                COUNT(*) AS kayit_sayisi,
                MIN(tarih) AS ilk_tarih,
                MAX(tarih) AS son_tarih,
                COALESCE(SUM(CASE WHEN alinan_tutar1 >= 0 THEN alinan_tutar1 ELSE 0 END), 0) AS borc,
                COALESCE(SUM(CASE WHEN alinan_tutar1 <  0 THEN alinan_tutar1 ELSE 0 END), 0) AS odeme,
                COALESCE(SUM(alinan_tutar1), 0) AS net,
                MAX(banka) AS banka
            FROM kredikartidata
            WHERE userid = %s AND musterino = %s
              AND LOWER(aciklama) LIKE %s
            GROUP BY SUBSTRING(aciklama FROM 1 FOR POSITION('.pdf' IN LOWER(aciklama)) + 3)
            ORDER BY MIN(tarih) DESC
        """, (str(userid), str(musterino), '%.pdf%')).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_kredi_karti_pdf_listesi(userid: int, musterino: int) -> list[dict]:
    """
    Yüklenen PDF dosyalarını ve dönemlerini listeler.
    aciklama alanında kaynak_dosya adı gömülüdür: '{pdf_adi} {aciklama}'
    """
    conn = get_connection()
    try:
        # PostgreSQL: regexp ile .pdf uzantılı dosya adını çıkar
        rows = conn.execute("""
            SELECT
                REGEXP_REPLACE(aciklama, '\\s+.*$', '') AS pdf_adi,
                COUNT(*)                                 AS kayit_sayisi,
                MIN(tarih)                               AS ilk_tarih,
                MAX(tarih)                               AS son_tarih,
                COALESCE(SUM(alinan_tutar1), 0)          AS toplam,
                MAX(banka)                               AS banka
            FROM kredikartidata
            WHERE userid = ? AND musterino = ?
              AND aciklama ILIKE '%.pdf%'
            GROUP BY REGEXP_REPLACE(aciklama, '\\s+.*$', '')
            ORDER BY MIN(tarih) DESC
        """, (str(userid), str(musterino))).fetchall()
        result = []
        for r in rows:
            d = dict(r) if hasattr(r, 'keys') else {
                'pdf_adi':      r[0],
                'kayit_sayisi': r[1],
                'ilk_tarih':    r[2],
                'son_tarih':    r[3],
                'toplam':       r[4],
                'banka':        r[5],
            }
            result.append(d)
        return result
    except Exception:
        return []
    finally:
        conn.close()




def get_kredi_karti_ekstre_detay(
    userid: int,
    musterino: int,
    banka: str,
    yil: Optional[int] = None,
    ilk_tarih: Optional[str] = None,
    son_tarih: Optional[str] = None,
    hesapkodu: Optional[str] = None,
    pdf_adi: Optional[str] = None,
) -> list[dict]:
    """
    Belirli bir karta ait ekstre satırları.
    pdf_adi verilirse o PDF'e ait satırlar filtrelenir.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        params: list = [str(userid), str(musterino)]

        def tr2iso(d: str) -> str:
            """DD.MM.YYYY → YYYY-MM-DD"""
            p = d.split(".")
            return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else d

        _iso = tarih_iso_hareketler("tarih")

        # PDF adına göre filtrele — SUBSTRING ile GROUP BY'daki aynı ifadeyi kullan
        if pdf_adi:
            banka_where = "AND SUBSTRING(aciklama FROM 1 FOR POSITION('.pdf' IN LOWER(aciklama)) + 3) = %s"
            params.append(pdf_adi)
        elif hesapkodu:
            banka_where = "AND hesapkodu = %s"
            params.append(hesapkodu)
        else:
            banka_where = "AND Banka = %s AND (hesapkodu IS NULL OR hesapkodu = '')"
            params.append(banka)

        # PDF adına göre seçildiğinde tarih filtresi gerekmez — PDF adı zaten benzersiz
        if pdf_adi:
            where_extra = ""
        elif ilk_tarih and son_tarih:
            where_extra = f"AND ({_iso} BETWEEN %s AND %s)"
            params += [tr2iso(ilk_tarih), tr2iso(son_tarih)]
        else:
            where_extra = f"AND {right4('tarih')} = %s"
            params.append(str(yil))

        rows = conn.execute(f"""
            SELECT
                id, tarih, aciklama, Tutar,
                CAST(alinan_tutar1 AS REAL) AS alinan_tutar1,
                hesapKodu, womsiskey, islem, Banka,
                CASE WHEN alinan_tutar1 < 0 THEN 'odeme' ELSE 'borc' END AS tur
            FROM kredikartidata
            WHERE userid = %s AND musterino = %s
              {banka_where}
              {where_extra}
            ORDER BY {_iso} ASC, id ASC
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
            'SELECT id, subeAck FROM subeler WHERE userid=? ORDER BY id', (userid,)
        ).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_monthly_comparison(
    userid: int, musterino: int, yil: Optional[int] = None,
    ilk_tarih: Optional[str] = None,
    son_tarih: Optional[str] = None,
) -> list[dict]:
    """Gelir-Gider karşılaştırma grafiği için aylık toplamlar.

    ilk_tarih/son_tarih 'YYYY-MM-DD' verilirse tarih aralığı filtrelenir,
    verilmezse yıl bazlı çalışır.
    """
    yil = yil or _year()
    conn = get_connection()
    try:
        if ilk_tarih and son_tarih:
            where_clause = "tarih_date >= ? AND tarih_date <= ?"
            params = (userid, musterino, ilk_tarih, son_tarih)
        else:
            where_clause = f"{yr('tarih_date')} = ?"
            params = (userid, musterino, str(yil))

        rows = conn.execute(f"""
            SELECT
                {mo("tarih_date")} AS ay,
                SUM(gelir) AS toplam_gelir,
                SUM(gider) AS toplam_gider
            FROM genel_hesap_hareketleri
            WHERE userid = ? AND musteri_no = ? AND {where_clause}
            GROUP BY {mo("tarih_date")}
            ORDER BY {mo("tarih_date")}
        """, params).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_bankalar_toplam(userid: int, musterino: int = 1) -> dict:
    """womsis_banka tablosundan gelir/gider/net toplamı döndürür."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN LOWER(gelirgider)='gelir' THEN tutar ELSE 0 END), 0) AS gelir,
                COALESCE(SUM(CASE WHEN LOWER(gelirgider)='gider' THEN tutar ELSE 0 END), 0) AS gider,
                COUNT(*) AS kayit
            FROM womsis_banka
            WHERE userid = ? AND musterino = ?
        """, (userid, musterino)).fetchone()
        gelir = float(row["gelir"] or 0) if row else 0.0
        gider = float(row["gider"] or 0) if row else 0.0
        return {"gelir": gelir, "gider": gider, "net": gelir - gider,
                "kayit": int(row["kayit"] or 0) if row else 0}
    except Exception:
        return {"gelir": 0.0, "gider": 0.0, "net": 0.0, "kayit": 0}
    finally:
        conn.close()



def get_all_dashboard_data(
    userid: int,
    musterino: int,
    yil: Optional[int] = None,
    ilk_tarih: Optional[str] = None,
    son_tarih: Optional[str] = None,
) -> dict:
    """Tüm dashboard KPI verilerini minimum sorgu sayısıyla döndürür.

    ilk_tarih / son_tarih 'YYYY-MM-DD' verilirse tarih aralığına göre filtreler.
    Verilmezse yıl bazlı çalışır (eski davranış).
    Toplam: ~4 sorgu.
    """
    yil = yil or _year()

    # 1 sorgu — genel_hesap_hareketleri'nin tüm KPI'larını tek seferde al
    ghh = _get_genel_hesap_all(userid, musterino, yil,
                               ilk_tarih=ilk_tarih, son_tarih=son_tarih)

    return {
        "yil":            yil,
        "ilk_tarih":      ilk_tarih,
        "son_tarih":      son_tarih,
        "nakit_kasa":     get_nakit_kasa_toplam(userid, musterino, yil, _ghh=ghh),
        "gider":          get_gider_toplam(userid, musterino, yil, _ghh=ghh),
        "genel_hesap":    get_genel_hesap_toplam(userid, musterino, yil, _ghh=ghh),
        "faturalar":      get_fatura_toplamlar(userid, yil),
        "gider_pusulasi": get_gider_pusulasi(userid, musterino, yil, _ghh=ghh),
        "maas_kira_smm":  get_maaş_kira_smm(userid, musterino, yil, _ghh=ghh),
        "kurum_odemeleri":get_kurum_odemeleri(userid, musterino, yil),
        "sanal_pos":      get_sanal_pos_toplam(userid, yil),
        "kredi_karti":    get_kredi_karti_toplam(userid, musterino, yil, ilk_tarih=ilk_tarih, son_tarih=son_tarih),
        "bankalar":       get_bankalar_toplam(userid, musterino),
        "monthly_chart":  get_monthly_comparison(userid, musterino, yil,
                                                  ilk_tarih=ilk_tarih, son_tarih=son_tarih),
    }


