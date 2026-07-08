"""
Detay Servis — KPI kartlarına tıklandığında açılan
şube özet + işlem listesi diyaloğu için veri servisi.
SQLite ve PostgreSQL uyumludur.

PostgreSQL notları:
  - ROUND(real, int) çalışmaz → ROUND(SUM(...)::NUMERIC, 2) kullanılır
  - camelCase kolon adları PG'de küçük harfe normalize edildi
  - hareketler tablosu: musteriNo→musterino, gelirGider→gelirgider,
                        subeAck→subeack (subeler tablosu)
    ANCAK bu tablo SQLite'tan PG'ye geçmiyorsa orijinal adlar kalır.
"""
from typing import Optional
from db.database import get_connection
from db.db_compat import (
    yr, left4, tarih_yil_hareketler, tarih_iso_hareketler,
    pg_musterino, pg_hesapkodu, pg_isinv, substr_mid
)
from db.db_config import get_mode


def _pg() -> bool:
    return get_mode() == "postgres"


def _round_sql(expr: str) -> str:
    """PostgreSQL'de ROUND(real,int) çalışmaz — NUMERIC cast eklenir."""
    if _pg():
        return f"ROUND(({expr})::NUMERIC, 2)"
    return f"ROUND({expr}, 2)"


def _col(sqlite_name: str, pg_name: str) -> str:
    """Mod'a göre kolon adı seç."""
    return pg_name if _pg() else sqlite_name


# ─── ŞUBE BAZLI ÖZET ─────────────────────────────────────────────────────────

def get_nakit_kasa_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Nakit Kasa Gelir kartına tıklandığında gösterilecek
    şube bazlı gelir/gider özeti (hareketler tablosundan).
    hareketler.tarih formatı: DD.MM.YYYY → 7. karakterden 4 karakter = yıl.
    """
    _yil_col  = tarih_yil_hareketler("h.tarih")
    _mno_col  = _col('"musteriNo"', "musterino")
    _gelir_col = _col('"gelirGider"', "gelirgider")
    _sube_ack = _col("subeAck", "subeack")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(s.{_sube_ack}, '(şubesiz)') AS sube_adi,
                COALESCE(CAST(NULLIF(TRIM(h.sube),'') AS INTEGER), 0)  AS sube_id,
                {_round_sql(f"SUM(CASE WHEN h.{_gelir_col}='gelir' THEN CAST(h.alinan_tutar1 AS REAL) ELSE 0 END)")} AS toplam_gelir,
                {_round_sql(f"SUM(CASE WHEN h.{_gelir_col}='gider' THEN CAST(h.alinan_tutar1 AS REAL) ELSE 0 END)")} AS toplam_gider,
                COUNT(*) AS kayit_sayisi
            FROM hareketler h
            LEFT JOIN subeler s ON CAST(NULLIF(TRIM(h.sube),'') AS INTEGER) = s.id
            WHERE h.{_mno_col} = ?
              AND length(h.tarih) >= 10
              AND {_yil_col} = ?
            GROUP BY h.sube, s.{_sube_ack}
            ORDER BY toplam_gelir DESC
        """, (musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_genel_hesap_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Genel Hesap kartına tıklandığında
    genel_hesap_hareketleri tablosundan şube bazlı özet.
    """
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                {_round_sql("SUM(CAST(g.gelir AS REAL))")}  AS toplam_gelir,
                {_round_sql("SUM(CAST(g.gider AS REAL))")}  AS toplam_gider,
                COUNT(*)                AS kayit_sayisi
            FROM genel_hesap_hareketleri g
            WHERE g.userid = ?
              AND g.musteri_no = ?
              AND {yr("g.tarih_date")} = ?
            GROUP BY g.sube
            ORDER BY toplam_gelir DESC
        """, (userid, musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_fatura_sube_ozet(userid: int, yil: int, mod: str) -> list[dict]:
    """
    Kesilen / Gelen Fatura kartına tıklandığında unvan bazlı özet.
    mod: 'gelir' (kesilen) | 'gider' (gelen)
    """
    _mod_col = _col("gelirGiderMod", "gelirgidermod")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(unvan, '(Bilinmeyen)') AS sube_adi,
                {_round_sql("SUM(CAST(toplam AS REAL))")} AS toplam_tutar,
                COUNT(*) AS kayit_sayisi
            FROM faturalar
            WHERE userid = ?
              AND {left4("tarih")} = ?
              AND {_mod_col} = ?
            GROUP BY unvan
            ORDER BY toplam_tutar DESC
            LIMIT 50
        """, (userid, str(yil), mod)).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_gider_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Gider Pusulası, Kurum Ödemeleri, Maaş Kira SMM kartı için
    teslim_sekli bazlı gider özeti.
    """
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(g.teslim_sekli, 'Diğer') AS sube_adi,
                {_round_sql("SUM(CAST(g.gider AS REAL))")}  AS toplam_gider,
                {_round_sql("SUM(CAST(g.gelir AS REAL))")}  AS toplam_gelir,
                COUNT(*)                AS kayit_sayisi
            FROM genel_hesap_hareketleri g
            WHERE g.userid = ?
              AND g.musteri_no = ?
              AND g.nerden_geliyor IN ('gider', 'genelHesap')
              AND {yr("g.tarih_date")} = ?
              AND g.gider > 0
            GROUP BY g.teslim_sekli
            ORDER BY toplam_gider DESC
        """, (userid, musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


# ─── İŞLEM LİSTESİ (DETAY) ───────────────────────────────────────────────────

def get_hareketler_detay(userid: int, musterino: int, yil: int,
                          sube_id=None, sube_adi: str = None) -> list[dict]:
    """
    Belirli şube için hareketler tablosundan işlem listesi.
    hareketler.tarih formatı: DD.MM.YYYY
    """
    _yil_col   = tarih_yil_hareketler("h.tarih")
    _mno_col   = _col('"musteriNo"', "musterino")
    _gelir_col = _col('"gelirGider"', "gelirgider")
    _sube_ack  = _col("subeAck", "subeack")
    _hkod_col  = _col('"hesapKodu"', "hesapkodu")
    _fatno_col = _col('"faturaNo"', "faturano")
    _fatunv    = _col('"faturaUnvan"', "faturaunvan")
    conn = get_connection()
    try:
        if sube_id is not None:
            rows = conn.execute(f"""
                SELECT
                    h.id, h.tarih, h.aciklama,
                    s.{_sube_ack} AS sube_adi,
                    h.alinan_tutar1 AS tutar,
                    h.{_gelir_col} AS gelirgider,
                    h.odeme_sekli1, h.{_hkod_col} AS hesapkodu,
                    h.{_fatno_col} AS faturano,
                    h.{_fatunv} AS faturaunvan,
                    h.teslim_sekli
                FROM hareketler h
                LEFT JOIN subeler s ON CAST(NULLIF(TRIM(h.sube),'') AS INTEGER) = s.id
                WHERE h.{_mno_col} = ?
                  AND CAST(NULLIF(TRIM(h.sube),'') AS INTEGER) = ?
                  AND {_yil_col} = ?
                ORDER BY h.tarih DESC, h.id DESC
                LIMIT 500
            """, (musterino, sube_id, str(yil))).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT
                    h.id, h.tarih, h.aciklama,
                    COALESCE(s.{_sube_ack}, '(Şubesiz)') AS sube_adi,
                    h.alinan_tutar1 AS tutar,
                    h.{_gelir_col} AS gelirgider,
                    h.odeme_sekli1, h.{_hkod_col} AS hesapkodu,
                    h.{_fatno_col} AS faturano,
                    h.{_fatunv} AS faturaunvan,
                    h.teslim_sekli
                FROM hareketler h
                LEFT JOIN subeler s ON CAST(NULLIF(TRIM(h.sube),'') AS INTEGER) = s.id
                WHERE h.{_mno_col} = ?
                  AND {_yil_col} = ?
                ORDER BY h.tarih DESC, h.id DESC
                LIMIT 500
            """, (musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_nakit_kasa_detay(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Nakit Kasa detay listesi — dashboard ile AYNI kaynak.
    genel_hesap_hareketleri tablosundan nerden_geliyor='kasa' filtresiyle çeker.
    tarih_date kolonu YYYY-MM-DD formatındadır.
    """
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                g.id,
                g.tarih_date   AS tarih,
                g.form_id,
                g.aciklama,
                COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                g.gelir,
                g.gider,
                g.teslim_sekli,
                g.odeme_sekli,
                g.kategori,
                g.nerden_geliyor
            FROM genel_hesap_hareketleri g
            WHERE g.userid     = ?
              AND g.musteri_no = ?
              AND g.nerden_geliyor = 'kasa'
              AND {yr("g.tarih_date")} = ?
            ORDER BY g.tarih_date DESC, g.id DESC
            LIMIT 2000
        """, (userid, musterino, str(yil))).fetchall()
        return list(rows)
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
            rows = conn.execute(f"""
                SELECT
                    g.id, g.tarih_date AS tarih, g.form_id, g.aciklama,
                    g.sube AS sube_adi, g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori,
                    g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ?
                  AND g.musteri_no = ?
                  AND g.sube = ?
                  AND {yr("g.tarih_date")} = ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 500
            """, (userid, musterino, sube_adi, str(yil))).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT
                    g.id, g.tarih_date AS tarih, g.form_id, g.aciklama,
                    COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                    g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori,
                    g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ?
                  AND g.musteri_no = ?
                  AND {yr("g.tarih_date")} = ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 500
            """, (userid, musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_fatura_detay(userid: int, yil: int, mod: str,
                      unvan: str = None) -> list[dict]:
    """
    faturalar tablosundan belirli ünvan filtreli liste.
    """
    _mod_col  = _col("gelirGiderMod", "gelirgidermod")
    _fmod_col = _col("faturaMod", "faturamod")
    _fno_col  = _col("formNo", "formno")
    _ykl_col  = _col("yuklenmeTarihi", "yuklenmetarihi")
    conn = get_connection()
    try:
        if unvan:
            rows = conn.execute(f"""
                SELECT id, tarih, unvan, vergino,
                       {_col("vergiDairesi", "vergidairesi")} AS vergidairesi,
                       {_col("faturano", "faturano")} AS faturano,
                       toplam, {_mod_col} AS gelirgidermod,
                       {_fmod_col} AS faturamod,
                       {_fno_col} AS formno, kaynak,
                       {_ykl_col} AS yuklenmetarihi, xml_dosya
                FROM faturalar
                WHERE userid = ?
                  AND {left4("tarih")} = ?
                  AND {_mod_col} = ?
                  AND unvan = ?
                ORDER BY tarih DESC, id DESC
            """, (userid, str(yil), mod, unvan)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT id, tarih, unvan, vergino,
                       {_col("vergiDairesi", "vergidairesi")} AS vergidairesi,
                       {_col("faturano", "faturano")} AS faturano,
                       toplam, {_mod_col} AS gelirgidermod,
                       {_fmod_col} AS faturamod,
                       {_fno_col} AS formno, kaynak,
                       {_ykl_col} AS yuklenmetarihi, xml_dosya
                FROM faturalar
                WHERE userid = ?
                  AND {left4("tarih")} = ?
                  AND {_mod_col} = ?
                ORDER BY tarih DESC, id DESC
                LIMIT 10000
            """, (userid, str(yil), mod)).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_kurum_odemeleri_detay(musterino: int, yil: int,
                               ay: Optional[int] = None) -> list[dict]:
    """
    Kurum Ödemeleri detay listesi — nakitakis_parametre tablosundan.
    ilkTarih DB formatı: YYYYMMDD (20260126)
    """
    _mno  = pg_musterino()
    _hkod = pg_hesapkodu()
    _ilkt = pg_isinv()
    _gider_col = _col("gelirGider", "gelirgider")
    conn = get_connection()
    try:
        if ay and ay != 0:
            ay_str = f"{ay:02d}"
            rows = conn.execute(f"""
                SELECT
                    id, {_hkod} AS hesapKodu, hesapAck, unvan, vergiNo,
                    {_ilkt} AS ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                    tutar, {_gider_col} AS gelirGider, aciklama
                FROM nakitakis_parametre
                WHERE {_mno} = ?
                  AND {_gider_col} = 'gider'
                  AND {left4(_ilkt)} = ?
                  AND {substr_mid(_ilkt, 5, 2)} = ?
                ORDER BY {_ilkt} DESC
            """, (musterino, str(yil), ay_str)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT
                    id, {_hkod} AS hesapKodu, hesapAck, unvan, vergiNo,
                    {_ilkt} AS ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                    tutar, {_gider_col} AS gelirGider, aciklama
                FROM nakitakis_parametre
                WHERE {_mno} = ?
                  AND {_gider_col} = 'gider'
                  AND {left4(_ilkt)} = ?
                ORDER BY {_ilkt} DESC
            """, (musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_kurum_odemeleri_detay_tarih(musterino: int,
                                    ilk_tarih: str,
                                    son_tarih: str) -> list[dict]:
    """
    Tarih aralığı bazlı Kurum Ödemeleri detay listesi.
    ilk_tarih / son_tarih: YYYYMMDD formatı ('20260201', '20260228')
    """
    _mno  = pg_musterino()
    _hkod = pg_hesapkodu()
    _ilkt = pg_isinv()
    _gider_col = _col("gelirGider", "gelirgider")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                id, {_hkod} AS hesapKodu, hesapAck, unvan, vergiNo,
                {_ilkt} AS ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                tutar, {_gider_col} AS gelirGider, aciklama
            FROM nakitakis_parametre
            WHERE {_mno} = ?
              AND {_gider_col} = 'gider'
              AND {_ilkt} >= ?
              AND {_ilkt} <= ?
            ORDER BY {_ilkt} DESC
        """, (musterino, ilk_tarih, son_tarih)).fetchall()
        return list(rows)
    finally:
        conn.close()


# ─── FATURA ŞUBE BAZLI ÖZET ───────────────────────────────────────────────────

def get_fatura_sube_ozet(userid: int, musterino: int, yil: int,
                          mod: str) -> list[dict]:
    """
    Kesilen (mod='gelir') veya Gelen (mod='gider') faturaları
    genel_hesap_hareketleri.form_id üzerinden şubeye bağlayarak
    şube bazlı özet döndürür.

    Faturanın form_no'su eşleşmiyorsa '(Şubesiz)' grubuna düşer.
    """
    _mod_col = _col("gelirGiderMod", "gelirgidermod")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT
                COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                COUNT(DISTINCT f.id)           AS kayit_sayisi,
                {_round_sql("SUM(CAST(f.toplam AS REAL))")} AS toplam_gelir,
                0                              AS toplam_gider
            FROM faturalar f
            LEFT JOIN genel_hesap_hareketleri g
                ON g.form_id = f.{_col("formNo", "formno")}
               AND g.userid  = f.userid
               AND g.musteri_no = ?
            WHERE f.userid = ?
              AND {left4("f.tarih")} = ?
              AND f.{_mod_col} = ?
            GROUP BY COALESCE(g.sube, '(Şubesiz)')
            ORDER BY toplam_gelir DESC
        """, (musterino, userid, str(yil), mod)).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_fatura_detay_by_sube(userid: int, musterino: int, yil: int,
                              mod: str, sube_adi: str) -> list[dict]:
    """
    Belirli bir şubeye ait fatura listesi.
    Şube bilgisi genel_hesap_hareketleri.sube üzerinden JOIN ile gelir.
    sube_adi='(Şubesiz)' → eşleşmeyen faturalar.
    """
    _mod_col = _col("gelirGiderMod", "gelirgidermod")
    _fmod_col = _col("faturaMod", "faturamod")
    _fno_col  = _col("formNo", "formno")
    _ykl_col  = _col("yuklenmeTarihi", "yuklenmetarihi")
    conn = get_connection()
    try:
        if sube_adi == "(Şubesiz)":
            rows = conn.execute(f"""
                SELECT DISTINCT f.id, f.tarih, f.unvan, f.vergino,
                       {_col("f.vergiDairesi", "f.vergidairesi")} AS vergidairesi,
                       {_col("f.faturano", "f.faturano")} AS faturano,
                       f.toplam, f.{_mod_col} AS gelirgidermod,
                       f.{_fmod_col} AS faturamod,
                       f.{_fno_col} AS formno, f.kaynak,
                       f.{_ykl_col} AS yuklenmetarihi, f.xml_dosya,
                       NULL AS sube_adi
                FROM faturalar f
                LEFT JOIN genel_hesap_hareketleri g
                    ON g.form_id = f.{_fno_col}
                   AND g.userid  = f.userid
                   AND g.musteri_no = ?
                WHERE f.userid = ?
                  AND {left4("f.tarih")} = ?
                  AND f.{_mod_col} = ?
                  AND g.id IS NULL
                ORDER BY f.tarih DESC, f.id DESC
                LIMIT 5000
            """, (musterino, userid, str(yil), mod)).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT DISTINCT f.id, f.tarih, f.unvan, f.vergino,
                       {_col("f.vergiDairesi", "f.vergidairesi")} AS vergidairesi,
                       {_col("f.faturano", "f.faturano")} AS faturano,
                       f.toplam, f.{_mod_col} AS gelirgidermod,
                       f.{_fmod_col} AS faturamod,
                       f.{_fno_col} AS formno, f.kaynak,
                       f.{_ykl_col} AS yuklenmetarihi, f.xml_dosya,
                       g.sube AS sube_adi
                FROM faturalar f
                JOIN genel_hesap_hareketleri g
                    ON g.form_id = f.{_fno_col}
                   AND g.userid  = f.userid
                   AND g.musteri_no = ?
                WHERE f.userid = ?
                  AND {left4("f.tarih")} = ?
                  AND f.{_mod_col} = ?
                  AND g.sube = ?
                ORDER BY f.tarih DESC, f.id DESC
                LIMIT 5000
            """, (musterino, userid, str(yil), mod, sube_adi)).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_fatura_by_formno(userid: int, formno: str) -> list[dict]:
    """
    Form No (form_id) ile eşleşen fatura(ları) döndürür.
    Hem gelen hem kesilen faturalarda arar.
    Genel hesap tablosundaki bir satıra tıklanınca çağrılır.
    """
    if not formno or formno.strip() in ("", "-", "None"):
        return []
    _fno_col  = _col("formNo", "formno")
    _mod_col  = _col("gelirGiderMod", "gelirgidermod")
    _fmod_col = _col("faturaMod", "faturamod")
    _ykl_col  = _col("yuklenmeTarihi", "yuklenmetarihi")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT id, tarih, unvan, vergino,
                   {_col("vergiDairesi", "vergidairesi")} AS vergidairesi,
                   {_col("faturano", "faturano")} AS faturano,
                   toplam, {_mod_col} AS gelirgidermod,
                   {_fmod_col} AS faturamod,
                   {_fno_col} AS formno, kaynak,
                   {_ykl_col} AS yuklenmetarihi, xml_dosya
            FROM faturalar
            WHERE userid = ?
              AND {_fno_col} = ?
            ORDER BY tarih DESC, id DESC
            LIMIT 100
        """, (userid, str(formno).strip())).fetchall()
        return list(rows)
    finally:
        conn.close()
