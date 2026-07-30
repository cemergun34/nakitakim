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
    pg_musterino, pg_hesapkodu, pg_isinv, substr_mid,
    numeric_cast,
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
    şube bazlı gelir/gider özeti (genel_hesap_hareketleri tablosundan).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(islemtutari), 0) AS islem, "
            "  COALESCE(SUM(odemetutari), 0) AS odeme "
            "FROM paytr WHERE userid::text = ? AND musterino::text = ?",
            (str(userid), str(musterino))
        ).fetchone()
        rows = conn.execute(f"""
            SELECT
                COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                COALESCE(g.sube, '(Şubesiz)') AS sube_id,
                {_round_sql("SUM(CAST(g.gelir AS REAL))")} AS toplam_gelir,
                {_round_sql("SUM(CAST(g.gider AS REAL))")} AS toplam_gider,
                COUNT(*) AS kayit_sayisi
            FROM genel_hesap_hareketleri g
            WHERE g.userid = ?
              AND g.musteri_no = ?
              AND g.nerden_geliyor = 'kasa'
              AND {yr("g.tarih_date")} = ?
            GROUP BY g.sube
            ORDER BY toplam_gelir DESC
        """, (userid, musterino, str(yil))).fetchall()
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


def get_fatura_sube_ozet(userid: int, musterino: int, yil: int, mod: str) -> list[dict]:
    """
    Kesilen (mod='gelir') veya Gelen (mod='gider') faturaları
    genel_hesap_hareketleri.form_id üzerinden şubeye bağlayarak
    şube bazlı özet döndürür.

    Faturanın form_no'su eşleşmiyorsa '(Şubesiz)' grubuna düşer.

    DÜZELTME: CTE ile her formno'ya karşılık gelen şubeyi önce MIN ile
    tekil hale getirip sonra JOIN yapıyoruz. Böylece genel_hesap_hareketleri'nde
    aynı form_id'e birden fazla satır olsa bile SUM(f.toplam) çarpılmıyor.
    """
    _mod_col  = _col("gelirGiderMod", "gelirgidermod")
    _fno_col  = _col("formNo", "formno")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            WITH sube_map AS (
                SELECT form_id,
                       MIN(sube) AS sube
                FROM genel_hesap_hareketleri
                WHERE userid    = ?
                  AND musteri_no = ?
                GROUP BY form_id
            )
            SELECT
                COALESCE(sm.sube, '(Şubesiz)')         AS sube_adi,
                COUNT(f.id)                             AS kayit_sayisi,
                {_round_sql("SUM(CAST(f.toplam AS REAL))")} AS toplam_gelir,
                0                                       AS toplam_gider
            FROM faturalar f
            LEFT JOIN sube_map sm ON sm.form_id = f.{_fno_col}
            WHERE f.userid    = ?
              AND {left4("f.tarih")} = ?
              AND f.{_mod_col}  = ?
            GROUP BY COALESCE(sm.sube, '(Şubesiz)')
            ORDER BY toplam_gelir DESC
        """, (userid, musterino, userid, str(yil), mod)).fetchall()
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


def get_nakit_kasa_detay(userid: int, musterino: int, yil: int, sube_adi: str = None) -> list[dict]:
    """
    Nakit Kasa detay listesi — dashboard ile AYNI kaynak.
    genel_hesap_hareketleri tablosundan nerden_geliyor='kasa' filtresiyle çeker.
    tarih_date kolonu YYYY-MM-DD formatındadır.
    """
    conn = get_connection()
    try:
        if sube_adi == "(Şubesiz)":
            rows = conn.execute(f"""
                SELECT
                    g.id, g.tarih_date AS tarih, g.form_id, g.aciklama,
                    '(Şubesiz)' AS sube_adi, g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori, g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ? AND g.musteri_no = ? AND g.nerden_geliyor = 'kasa'
                  AND (g.sube IS NULL OR g.sube = '')
                  AND {yr("g.tarih_date")} = ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 2000
            """, (userid, musterino, str(yil))).fetchall()
        elif sube_adi:
            rows = conn.execute(f"""
                SELECT
                    g.id, g.tarih_date AS tarih, g.form_id, g.aciklama,
                    g.sube AS sube_adi, g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori, g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ? AND g.musteri_no = ? AND g.nerden_geliyor = 'kasa'
                  AND g.sube = ?
                  AND {yr("g.tarih_date")} = ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 2000
            """, (userid, musterino, sube_adi, str(yil))).fetchall()
        else:
            rows = conn.execute(f"""
                SELECT
                    g.id, g.tarih_date AS tarih, g.form_id, g.aciklama,
                    COALESCE(g.sube, '(Şubesiz)') AS sube_adi, g.gelir, g.gider,
                    g.teslim_sekli, g.odeme_sekli, g.kategori, g.nerden_geliyor
                FROM genel_hesap_hareketleri g
                WHERE g.userid = ? AND g.musteri_no = ? AND g.nerden_geliyor = 'kasa'
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


def get_fatura_detay(userid: int, musterino: int, yil: int, mod: str,
                      unvan: str = None) -> list[dict]:
    """
    faturalar tablosundan belirli ünvan filtreli liste.
    mod: 'gelir' | 'gider'
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
                       {_ykl_col} AS yuklenmetarihi, xml_dosya, fatura
                FROM faturalar
                WHERE userid = ?
                  AND musterino = ?
                  AND {left4("tarih")} = ?
                  AND {_mod_col} = ?
                  AND unvan = ?
                ORDER BY tarih DESC, id DESC
            """, (userid, musterino, str(yil), mod, unvan)).fetchall()
        else:
            log_row = conn.execute(
                "SELECT son_sync_tarihi FROM paytr_sync_log WHERE userid::text = ? AND musterino::text = ? "
                "ORDER BY id DESC LIMIT 1",
                (str(userid), str(musterino))
            ).fetchone()
            rows = conn.execute(f"""
                SELECT id, tarih, unvan, vergino,
                       {_col("vergiDairesi", "vergidairesi")} AS vergidairesi,
                       {_col("faturano", "faturano")} AS faturano,
                       toplam, {_mod_col} AS gelirgidermod,
                       {_fmod_col} AS faturamod,
                       {_fno_col} AS formno, kaynak,
                       {_ykl_col} AS yuklenmetarihi, xml_dosya, fatura
                FROM faturalar
                WHERE userid = ?
                  AND musterino = ?
                  AND {left4("tarih")} = ?
                  AND {_mod_col} = ?
                ORDER BY tarih DESC, id DESC
                LIMIT 10000
            """, (userid, musterino, str(yil), mod)).fetchall()
        
        res = []
        import json
        for r in rows:
            d = dict(r)
            try:
                meta = json.loads(d.get("fatura") or "{}")
                d["aciklama"] = meta.get("aciklama", "")
            except Exception:
                d["aciklama"] = ""
            res.append(d)
        return res
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
                                    son_tarih: str) -> tuple[list, float]:
    """
    Tarih aralığı bazlı Kurum Ödemeleri detay listesi.
    ilk_tarih / son_tarih: YYYYMMDD formatı ('20260201', '20260228')
    Returns: (rows, toplam_float)
    """
    _mno  = pg_musterino()
    _hkod = pg_hesapkodu()
    _ilkt = pg_isinv()
    _gider_col = _col("gelirGider", "gelirgider")
    from db.db_config import get_mode as _gm
    _tutar_cast = "tutar::numeric" if _gm() == "postgres" else "CAST(tutar AS NUMERIC)"
    conn = get_connection()
    try:
        # Toplam
        toplam_row = conn.execute(f"""
            SELECT COALESCE(SUM({_tutar_cast}), 0) AS toplam
            FROM nakitakis_parametre
            WHERE {_mno} = ?
              AND {_gider_col} = 'gider'
              AND {_ilkt} >= ?
              AND {_ilkt} <= ?
        """, (musterino, ilk_tarih, son_tarih)).fetchone()
        toplam = float(toplam_row["toplam"] or 0)

        # Satırlar — byn_kayit_no kolonu: beyanname/tahakkuk ile direkt ilişki
        rows = conn.execute(f"""
            SELECT
                id, {_hkod} AS hesapKodu, hesapAck, unvan, vergiNo,
                {_ilkt} AS ilkTarih, sonTarih, sozlesmeNo, sozlesmeTarih,
                tutar, {_gider_col} AS gelirGider, aciklama,
                byn_kayit_no
            FROM nakitakis_parametre
            WHERE {_mno} = ?
              AND {_gider_col} = 'gider'
              AND {_ilkt} >= ?
              AND {_ilkt} <= ?
            ORDER BY {_ilkt} DESC
        """, (musterino, ilk_tarih, son_tarih)).fetchall()
        return list(rows), toplam
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

    DÜZELTME: CTE ile her formno'ya karşılık gelen şubeyi önce MIN ile
    tekil hale getirip sonra JOIN yapıyoruz. Böylece genel_hesap_hareketleri'nde
    aynı form_id'e birden fazla satır olsa bile SUM(f.toplam) çarpılmıyor.
    """
    _mod_col  = _col("gelirGiderMod", "gelirgidermod")
    _fno_col  = _col("formNo", "formno")
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            WITH sube_map AS (
                SELECT form_id,
                       MIN(sube) AS sube
                FROM genel_hesap_hareketleri
                WHERE userid    = ?
                  AND musteri_no = ?
                GROUP BY form_id
            )
            SELECT
                COALESCE(sm.sube, '(Şubesiz)')         AS sube_adi,
                COUNT(f.id)                             AS kayit_sayisi,
                {_round_sql("SUM(CAST(f.toplam AS REAL))")} AS toplam_gelir,
                0                                       AS toplam_gider
            FROM faturalar f
            LEFT JOIN sube_map sm ON sm.form_id = f.{_fno_col}
            WHERE f.userid    = ?
              AND {left4("f.tarih")} = ?
              AND f.{_mod_col}  = ?
            GROUP BY COALESCE(sm.sube, '(Şubesiz)')
            ORDER BY toplam_gelir DESC
        """, (userid, musterino, userid, str(yil), mod)).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_fatura_detay_by_sube(userid: int, musterino: int, yil: int,
                              mod: str, sube_adi: str) -> list[dict]:
    """
    Belirli bir şubeye ait fatura listesi.
    Şube bilgisi genel_hesap_hareketleri.sube üzerinden JOIN ile gelir.
    CTE + MIN(sube) kullanılarak JOIN duplicate önlenir.
    sube_adi=None        → tüm şubeler.
    sube_adi='(Şubesiz)' → eşleşmeyen faturalar.
    """
    _mod_col  = _col("gelirGiderMod", "gelirgidermod")
    _fmod_col = _col("faturaMod", "faturamod")
    _fno_col  = _col("formNo", "formno")
    _ykl_col  = _col("yuklenmeTarihi", "yuklenmetarihi")
    conn = get_connection()
    try:
        # CTE: her form_id için tek (MIN) sube seç → duplicate engel
        cte = f"""
            WITH sube_map AS (
                SELECT form_id, MIN(sube) AS sube
                FROM genel_hesap_hareketleri
                WHERE userid = ? AND musteri_no = ?
                GROUP BY form_id
            )
        """

        sel_cols = f"""
            SELECT f.id, f.userid, f.musterino, f.tarih, f.unvan, f.vergino,
                   {_col("f.vergiDairesi", "f.vergidairesi")} AS vergidairesi,
                   {_col("f.faturano", "f.faturano")} AS faturano,
                   f.toplam, f.{_mod_col} AS gelirgidermod,
                   f.{_fmod_col} AS faturamod,
                   f.{_fno_col} AS formno, f.kaynak,
                   f.{_ykl_col} AS yuklenmetarihi, f.xml_dosya,
                   sm.sube AS sube_adi, f.fatura
            FROM faturalar f
            LEFT JOIN sube_map sm ON sm.form_id = f.{_fno_col}
        """

        base_where = f"WHERE f.userid = ? AND f.musterino = ? AND {left4('f.tarih')} = ? AND f.{_mod_col} = ?"

        if sube_adi is None:
            sql    = cte + sel_cols + base_where + " ORDER BY f.tarih DESC, f.id DESC LIMIT 5000"
            params = (userid, musterino, userid, musterino, str(yil), mod)
        elif sube_adi == "(Şubesiz)":
            sql    = cte + sel_cols + base_where + " AND sm.form_id IS NULL ORDER BY f.tarih DESC, f.id DESC LIMIT 5000"
            params = (userid, musterino, userid, musterino, str(yil), mod)
        else:
            sql    = cte + sel_cols + base_where + " AND sm.sube = ? ORDER BY f.tarih DESC, f.id DESC LIMIT 5000"
            params = (userid, musterino, userid, musterino, str(yil), mod, sube_adi)

        rows = conn.execute(sql, params).fetchall()

        res = []
        import json
        for r in rows:
            d = dict(r)
            try:
                meta = json.loads(d.get("fatura") or "{}")
                d["aciklama"] = meta.get("aciklama", "")
            except Exception:
                d["aciklama"] = ""
            res.append(d)
        return res
    finally:
        conn.close()


def get_gider_pusulasi_sube_ozet(userid: int, musterino: int, yil: int) -> list[dict]:
    """
    Gider Pusulası kartına tıklandığında
    genel_hesap_hareketleri tablosundan şube bazlı özet.
    """
    conn = get_connection()
    try:
        # numeric_cast: PG float4 precision kaybını önler, SQLite'da CAST(AS REAL)
        _gc = numeric_cast("g.gelir")
        _dc = numeric_cast("g.gider")
        rows = conn.execute(f"""
            SELECT
                COALESCE(g.sube, '(Şubesiz)') AS sube_adi,
                COALESCE(SUM({_gc}), 0) AS toplam_gelir,
                COALESCE(SUM({_dc}), 0) AS toplam_gider,
                COUNT(*) AS kayit_sayisi
            FROM genel_hesap_hareketleri g
            WHERE g.userid = ?
              AND g.musteri_no = ?
              AND g.teslim_sekli LIKE '%Parça Alımı (Cihaz)%'
              AND {yr("g.tarih_date")} = ?
            GROUP BY g.sube
            ORDER BY toplam_gider DESC
        """, (userid, musterino, str(yil))).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_gider_pusulasi_detay(userid: int, musterino: int, yil: int,
                             teslim_sekli_filtre: str = None, sube_adi: str = None) -> list[dict]:
    """
    Gider Pusulası detay listesi.
    genel_hesap_hareketleri tablosundan teslim_sekli = 'Parça Alımı (Cihaz)'
    filtresiyle çeker. Dashboard'daki _get_genel_hesap_all sorgusuyla aynı mantık.

    teslim_sekli_filtre: None → tüm pusulalar; belirli değer → sadece o teslim şekli
    """
    conn = get_connection()
    try:
        if sube_adi and sube_adi != "(Şubesiz)":
            sube_condition = "AND g.sube = ?"
            params = [userid, musterino, str(yil), sube_adi]
        elif sube_adi == "(Şubesiz)":
            sube_condition = "AND (g.sube IS NULL OR g.sube = '')"
            params = [userid, musterino, str(yil)]
        else:
            sube_condition = ""
            params = [userid, musterino, str(yil)]

        if teslim_sekli_filtre:
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
                  AND {yr('g.tarih_date')} = ?
                  {sube_condition}
                  AND g.teslim_sekli LIKE ?
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 3000
            """, tuple(params + [f"%{teslim_sekli_filtre}%"])).fetchall()
        else:
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
                  AND {yr('g.tarih_date')} = ?
                  {sube_condition}
                  AND g.teslim_sekli LIKE '%Parça Alımı (Cihaz)%'
                ORDER BY g.tarih_date DESC, g.id DESC
                LIMIT 3000
            """, tuple(params)).fetchall()
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
            SELECT id, userid, musterino, tarih, unvan, vergino,
                   {_col("vergiDairesi", "vergidairesi")} AS vergidairesi,
                   {_col("faturano", "faturano")} AS faturano,
                   toplam, {_mod_col} AS gelirgidermod,
                   {_fmod_col} AS faturamod,
                   {_fno_col} AS formno, kaynak,
                   {_ykl_col} AS yuklenmetarihi, xml_dosya, fatura
            FROM faturalar
            WHERE userid = ?
              AND {_fno_col} = ?
            ORDER BY tarih DESC, id DESC
            LIMIT 100
        """, (userid, str(formno).strip())).fetchall()
        res = []
        import json
        for r in rows:
            d = dict(r)
            try:
                meta = json.loads(d.get("fatura") or "{}")
                d["aciklama"] = meta.get("aciklama", "")
            except Exception:
                d["aciklama"] = ""
            res.append(d)
        return res
    finally:
        conn.close()
