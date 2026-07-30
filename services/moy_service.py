"""
Moy Muhasebe Entegrasyon Servisi — Python / mysql-connector-python
PHP dosyalarının tam karşılığı:
  ajax/moy/moyapi.php      → moy_test_connection()
  ajax/moy/moyAktifMi.php  → get_moy_bilgileri()
  ajax/moy/moykaydet.php   → moy_kaydet_veriler()
  ajax/moy/moyconnect.php  → _moy_connect()

Moy = Uzak MySQL muhasebe sunucusu (moy_v2 veritabanı, port 3307)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from db.database import get_connection

logger = logging.getLogger(__name__)

MOY_PORT    = 3307
MOY_DB      = "moy_v2"
MOY_VN      = "3881403207"   # Vergi numarası (PHP'deki $vn sabit değeri)
MOY_CHARSET = "utf8"         # PHP moykaydet.php ile aynı — eski MySQL utf8mb4 desteklemez


# ── SQLite / PostgreSQL Uyumlu Kolon Adları Tanımları ─────────────────────────
musterino = "musteriNo"
hesapkodu = "hesapKodu"
vergino = "vergiNo"
ilktarih = "ilkTarih"
sontarih = "sonTarih"
gelirgider = "gelirGider"
iqmod = "iQmod"



# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: mysql-connector geç yükleme
# ─────────────────────────────────────────────────────────────────────────────

def _get_mysql():
    try:
        import mysql.connector
        return mysql.connector
    except ImportError as e:
        raise ImportError(
            "Moy entegrasyonu için 'mysql-connector-python' gerekli.\n"
            "Kurulum: pip install mysql-connector-python"
        ) from e


# ─────────────────────────────────────────────────────────────────────────────
# Veritabanı işlemleri  (moyAktifMi.php + moykaydet logic)
# ─────────────────────────────────────────────────────────────────────────────

def get_moy_bilgileri(musteri_no: int) -> dict:
    """
    moy_bilgileri tablosundan kullanıcıya ait kayıtları döndürür.
    PHP: ajax/moy/moyAktifMi.php → getMoyBilgileriByMusteriNo()
    SQLite: musteriNo / moyKayitNo (camelCase)
    PostgreSQL: musterino / moykayitno (küçük harf — tırnaksız tanım)
    """
    from db.db_config import get_mode
    _pg = get_mode() == "postgres"
    col_mno  = "musterino"  if _pg else musterino
    col_mkno = "moykayitno" if _pg else "moyKayitNo"

    conn = get_connection()
    try:
        row = conn.execute(
            f'SELECT url, username, sifre, "{col_mkno}" AS moykayitno '
            f'FROM moy_bilgileri WHERE "{col_mno}"=? LIMIT 1',
            (musteri_no,)
        ).fetchone()
        if row:
            row_d = dict(row)
            return {
                "success":    True,
                "url":        row_d.get("url")        or "",
                "username":   row_d.get("username")   or "",
                "sifre":      row_d.get("sifre")      or "",
                "moyKayitNo": row_d.get("moykayitno") or "",
            }
        return {"success": False, "message": "Kayıt bulunamadı."}
    except Exception as e:
        logger.error("Moy bilgileri getirme hatası: %s", e)
        return {"success": False, "message": str(e)}
    finally:
        conn.close()



def save_moy_bilgileri(musteri_no: int, url: str, username: str,
                        sifre: str, moy_kayit_no: str = "") -> dict:
    """
    moy_bilgileri tablosuna kayıt ekler/günceller (upsert).
    PHP: moyapi.php → INSERT INTO moy_bilgileri ON DUPLICATE KEY UPDATE
    SQLite: musteriNo / moyKayitNo (camelCase)
    PostgreSQL: musterino / moykayitno (küçük harf — tırnaksız tanım)
    """
    if not url or not username or not sifre:
        return {"success": False, "message": "Tüm alanları doldurunuz."}

    from db.db_config import get_mode
    _pg = get_mode() == "postgres"
    col_mno    = "musterino"    if _pg else musterino
    col_mkno   = "moykayitno"   if _pg else "moyKayitNo"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        existing = conn.execute(
            f'SELECT id FROM moy_bilgileri WHERE "{col_mno}"=? LIMIT 1',
            (musteri_no,)
        ).fetchone()

        if existing:
            conn.execute(
                f'UPDATE moy_bilgileri '
                f'SET url=?, username=?, sifre=?, "{col_mkno}"=?, tarih=? '
                f'WHERE "{col_mno}"=?',
                (url, username, sifre, moy_kayit_no, now, musteri_no)
            )
            msg = "Moy bilgileri güncellendi."
        else:
            conn.execute(
                f'INSERT INTO moy_bilgileri ("{col_mno}", url, username, sifre, "{col_mkno}", tarih) '
                f'VALUES (?, ?, ?, ?, ?, ?)',
                (musteri_no, url, username, sifre, moy_kayit_no, now)
            )
            msg = "Moy bilgileri kaydedildi."

        conn.commit()
        return {"success": True, "message": msg}
    except Exception as e:
        conn.rollback()
        logger.error("Moy bilgileri kaydetme hatası: %s", e)
        return {"success": False, "message": f"Hata: {e}"}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Moy MySQL bağlantısı
# ─────────────────────────────────────────────────────────────────────────────

def _moy_connect(host: str, user: str, password: str):
    """
    Uzak Moy MySQL sunucusuna bağlanır.
    PHP: moyconnect.php, baglanMoy.php
    utf8mb4 desteklenmiyor ise utf8'e düşer (eski MySQL 5.5/5.6 sunucular).
    Returns: mysql.connector.connection objesi
    """
    mc = _get_mysql()
    base_cfg = dict(
        host=host,
        port=MOY_PORT,
        database=MOY_DB,
        user=user,
        password=password,
        connection_timeout=15
    )
    # C extension bazı ortamlarda parolayı iletemiyor (using password: NO).
    # Önce C extension, başarısız olursa use_pure=True ile dene.
    for use_pure in (False, True):
        for charset in ("utf8", "utf8mb4", "latin1"):
            try:
                cnx = mc.connect(**base_cfg, charset=charset, use_pure=use_pure)
                logger.debug("Moy bağlantısı charset=%s use_pure=%s ile kuruldu", charset, use_pure)
                return cnx
            except mc.errors.DatabaseError as e:
                err = str(e)
                if "1115" in err or "Unknown character set" in err:
                    logger.warning("Charset %s desteklenmiyor, deneniyor...", charset)
                    continue
                if not use_pure and ("1045" in err or "using password: NO" in err):
                    # C extension parola sorunu → use_pure=True'ya geç
                    logger.warning("C extension bağlantı hatası, pure Python deneniyor: %s", e)
                    break  # iç charset döngüsünü kır, use_pure=True'ya geç
                raise
    raise RuntimeError("Moy bağlantısı kurulamadı. Tüm charset/driver kombinasyonları denendi.")



# ─────────────────────────────────────────────────────────────────────────────
# Test bağlantısı  (btnMoyTest click → moyapi.php)
# ─────────────────────────────────────────────────────────────────────────────

def _ucfirst_tr(s: str) -> str:
    """PHP my_ucfirst() karşılığı — ilk harfi büyük yap."""
    if not s:
        return s
    return s[0].upper() + s[1:].lower() if len(s) > 1 else s.upper()


def moy_test_connection(host: str, user: str, password: str,
                         musteri_no: int) -> dict:
    """
    Moy sunucusuna bağlanır, VN'ye ait müşterileri çeker ve
    lokal moy_bilgileri tablosuna upsert yapar.
    PHP: ajax/moy/moyapi.php (tam karşılık)

    Returns:
        {"success": True, "data": [{"adi":..., "soyadim":..., "kayitNo":...}]}
        {"success": False, "message": "..."}
    """
    # IP validasyonu (PHP tarafındaki validateMoy() regex ile aynı)
    ip_regex = re.compile(
        r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
        r"(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
    )
    if not ip_regex.match(host.strip()):
        return {"success": False, "message": "Geçersiz IP adresi formatı."}

    if not user or not password:
        return {"success": False, "message": "Tüm alanları doldurunuz."}

    try:
        cnx = _moy_connect(host, user, password)
        cursor = cnx.cursor(dictionary=True)

        # PHP: tanim_musteri_karti'nden VN'ye göre sorgula
        cursor.execute(
            """SELECT Kayit_No, Adi, Soyadi_Unvani, Kimlik_Vk
               FROM tanim_musteri_karti
               WHERE Aktif_Pasif = %s AND Kimlik_Vk = %s
               ORDER BY Soyadi_Unvani""",
            ("1", MOY_VN)
        )
        rows = cursor.fetchall()
        cursor.close()
        cnx.close()

        if not rows:
            return {"success": False, "message": "Eşleşen kayıt bulunamadı (false)."}

        result = []
        kayit_no = ""
        for row in rows:
            kayit_no = str(row["Kayit_No"])
            result.append({
                "adi":     _ucfirst_tr(str(row["Adi"] or "")),
                "soyadim": _ucfirst_tr(str(row["Soyadi_Unvani"] or "")),
                "kayitNo": kayit_no,
            })

        # Lokal DB'ye kaydet (PHP: INSERT INTO moy_bilgileri ON DUPLICATE KEY)
        save_moy_bilgileri(musteri_no, host, user, password, kayit_no)

        return {"success": True, "data": result}

    except Exception as e:
        logger.error("Moy test bağlantı hatası: %s", e)
        err = str(e)
        if "timed out" in err.lower() or "timeout" in err.lower():
            return {
                "success": False,
                "message": (
                    "Kod:MOY101 — İstek zaman aşımına uğradı. "
                    "Sunucu yanıt vermiyor (15sn). Bilgiler hatalı olabilir: "
                    "şifre, kullanıcı adı veya IP adresini kontrol edin."
                )
            }
        return {"success": False, "message": f"Bağlantı hatası: {err}"}


# ─────────────────────────────────────────────────────────────────────────────
# Verileri Çek  (btnMoyKaydet click → moykaydet.php)
# ─────────────────────────────────────────────────────────────────────────────

def _kayit_var_mi(conn, check: dict) -> bool:
    """
    nakitakis_parametre'de duplicate kontrolü.
    PHP: kayitVarMi() fonksiyonu ile birebir.
    """
    row = conn.execute(
        """SELECT COUNT(*) FROM nakitakis_parametre
           WHERE musteriNo=? AND hesapKodu=? AND ilkTarih=?
           AND ABS(tutar - ?) < 1.5 AND aciklama=?""",
        (
            check[musterino],
            check[hesapkodu],
            check[ilktarih],
            check["tutar"],
            check["aciklama"],
        )
    ).fetchone()[0]
    return row > 0

def moy_kaydet_veriler(musteri_no: int, yil: int,
                        progress_cb=None) -> dict:
    """
    Seçilen yıla ait 360 ve 361 hesap kodlu hareketleri Moy'dan çekip
    nakitakis_parametre tablosuna aktarır.
    PHP: ajax/moy/moykaydet.php tam karşılığı.
    YENİ: Her ödeme satırı için beyanname/tahakkuk eşleştirmesi yapıp
          byn_kayit_no kolonuna kaydeder. Eşleşme yoksa NULL geçer.

    progress_cb: opsiyonel callable(str) — ilerleme mesajı için
    Returns: {"success": bool, "message": str, "eklenen": int}
    """
    def _log(msg: str):
        if progress_cb:
            progress_cb(msg)

    bilgi = get_moy_bilgileri(musteri_no)
    if not bilgi.get("success"):
        return {"success": False, "message": "Moy bağlantı bilgileri bulunamadı. Önce Test edin.", "eklenen": 0}

    host      = bilgi["url"]
    user      = bilgi["username"]
    password  = bilgi["sifre"]
    kayit_nom = bilgi["moyKayitNo"]

    t1 = f"{yil}0101"
    t2 = f"{yil}1231"

    _log(f"🔗  Moy sunucusuna bağlanılıyor ({host})...")

    try:
        cnx = _moy_connect(host, user, password)
    except Exception as e:
        return {"success": False, "message": f"Moy bağlantı hatası: {e}", "eklenen": 0}

    try:
        cursor = cnx.cursor(dictionary=True)

        _log("📊  360 hesap kodu sorgulanıyor...")
        cursor.execute(
            """SELECT SUM(ht.Alacak) as toplam, ht.islem_Tarihi,
                      COALESCE(mk.Soyadi_Unvani, '') AS musteri_unvani,
                      COALESCE(s.Adi, '')             AS sube_adi,
                      COALESCE(s.Alanlar, '')         AS sube_alanlar
               FROM haraket_tablosu ht
               LEFT JOIN tanim_musteri_karti mk ON mk.Kayit_No = ht.Musteri_Kayit_No
               LEFT JOIN tanim_musteri_subeleri s ON s.Kayit_No = ht.Sube_Kayit_No
               WHERE ht.Alacak > 0
                 AND ht.islem_Tarihi BETWEEN %s AND %s
                 AND ht.Musteri_Kayit_No = %s
                 AND ht.Hesap_Kodu_1 = '360'
               GROUP BY ht.islem_Tarihi, mk.Soyadi_Unvani, s.Adi, s.Alanlar
               ORDER BY ht.islem_Tarihi ASC""",
            (t1, t2, kayit_nom)
        )
        data_360 = cursor.fetchall()

        _log("📊  361 hesap kodu sorgulanıyor...")
        cursor.execute(
            """SELECT SUM(ht.Alacak) as toplam, ht.islem_Tarihi,
                      COALESCE(mk.Soyadi_Unvani, '') AS musteri_unvani,
                      COALESCE(s.Adi, '')             AS sube_adi,
                      COALESCE(s.Alanlar, '')         AS sube_alanlar
               FROM haraket_tablosu ht
               LEFT JOIN tanim_musteri_karti mk ON mk.Kayit_No = ht.Musteri_Kayit_No
               LEFT JOIN tanim_musteri_subeleri s ON s.Kayit_No = ht.Sube_Kayit_No
               WHERE ht.Alacak > 0
                 AND ht.islem_Tarihi BETWEEN %s AND %s
                 AND ht.Musteri_Kayit_No = %s
                 AND ht.Hesap_Kodu_1 = '361'
               GROUP BY ht.islem_Tarihi, mk.Soyadi_Unvani, s.Adi, s.Alanlar
               ORDER BY ht.islem_Tarihi ASC""",
            (t1, t2, kayit_nom)
        )
        data_361 = cursor.fetchall()

        _log("📄  Yıllık beyanname/tahakkuk verileri çekiliyor...")
        cursor.execute(
            """SELECT bl.Kayit_No, bl.Belge_Tipi, bl.Belge_Turu, bl.Donem_No, bl.Donem_adi,
                      bl.Onay_Tarihi, bl.Belge_No, bl.Belge_Durumu,
                      bl.Beyan_Tarih_1, bl.Beyan_Tarih_2,
                      COALESCE(s.Adi, '') AS Sube_Adi, COALESCE(s.Alanlar, '') AS Sube_Alanlar,
                      COALESCE(mk.Soyadi_Unvani, '') AS Musteri_Unvani
               FROM beyanname_listeleri bl
               LEFT JOIN tanim_musteri_subeleri s ON s.Kayit_No = bl.Sube_Kayit_No
               LEFT JOIN tanim_musteri_karti mk ON mk.Kayit_No = bl.Musteri_Kayit_No
               WHERE bl.Musteri_Kayit_No = %s
                 AND bl.Belge_Tipi IN ('Byn', 'Thk')
                 AND (bl.Beyan_Tarih_1 BETWEEN %s AND %s
                      OR bl.Beyan_Tarih_2 BETWEEN %s AND %s)""",
            (kayit_nom, t1, t2, t1, t2)
        )
        data_beyan = cursor.fetchall()

        cursor.close()
        cnx.close()

    except Exception as e:
        cnx.close()
        return {"success": False, "message": f"Moy sorgu hatası: {e}", "eklenen": 0}

    if not data_360 and not data_361:
        return {"success": False, "message": "Kayıt bulunamadı.", "eklenen": 0}

    # ── Beyanname indeksi: (belge_tipi, belge_turu) → satır listesi ──────────
    # Eşleştirme önceliği hesap koduna göre:
    #   770.01 → 1.Thk/MUHSGK  2.Byn/KDV1  3.Byn/KDV2
    #   730.08 → 1.Byn/MUHSGK  2.Byn/MUHTAR
    HESAP_ONCELIK: dict[str, list[tuple[str, str]]] = {
        "770.01": [("Thk", "MUHSGK"), ("Byn", "KDV1"), ("Byn", "KDV2")],
        "730.08": [("Byn", "MUHSGK"), ("Byn", "MUHTAR")],
    }

    beyan_idx: dict[tuple, list[dict]] = {}
    for br in data_beyan:
        key = (str(br.get("Belge_Tipi") or ""), str(br.get("Belge_Turu") or ""))
        beyan_idx.setdefault(key, []).append({
            "kayit_no":      int(br["Kayit_No"]),
            "beyan_tarih_1": str(br.get("Beyan_Tarih_1") or ""),
            "beyan_tarih_2": str(br.get("Beyan_Tarih_2") or ""),
        })

    def _esles(ilk_tarih: str, hesap_kodu: str) -> "int | None":
        """
        Ödeme tarihine en uygun beyanname kayit_no'sunu döndürür.
        Adım 1: ilk_tarih (tam gün) → beyan_tarih_1 <= tarih <= beyan_tarih_2
        Adım 2: ay-başı (YYYYMM01)  → aynı koşul
        Eşleşme yoksa None.
        """
        if not ilk_tarih or len(ilk_tarih) < 6:
            return None
        ay_basi = ilk_tarih[:6] + "01"
        oncelik = HESAP_ONCELIK.get(hesap_kodu, [])

        for arama in (ilk_tarih, ay_basi):
            for tip, tur in oncelik:
                for aday in beyan_idx.get((tip, tur), []):
                    if aday["beyan_tarih_1"] and aday["beyan_tarih_2"]:
                        if aday["beyan_tarih_1"] <= arama <= aday["beyan_tarih_2"]:
                            return aday["kayit_no"]
        return None

    # ── Lokal DB'ye yaz ───────────────────────────────────────────────────────
    local = get_connection()

    from db.db_config import get_mode
    if get_mode() == "postgres":
        try:
            local.execute("SELECT setval(pg_get_serial_sequence('nakitakis_parametre', 'id'), COALESCE(MAX(id), 1)) FROM nakitakis_parametre")
            local.commit()
        except Exception as seq_err:
            logger.warning("nakitakis_parametre sequence resetleme hatası: %s", seq_err)

    def _sube_kodu(alanlar: str) -> str:
        if not alanlar:
            return ""
        parca = (alanlar.split("[|]")[0] or "").strip()
        return parca if parca.isdigit() else ""

    basari = 0
    iliski = 0
    detaylar = []

    try:
        # ── 360 → 770.01 ──────────────────────────────────────────────────────
        for row in data_360:
            tarih_fmt   = _fmt_tarih(row["islem_Tarihi"])
            tutar_val   = round(float(row["toplam"] or 0), 2)
            unvan_val   = str(row.get("musteri_unvani") or "-") or "-"
            sube_adi_v  = str(row.get("sube_adi") or "")
            sube_kod_v  = _sube_kodu(str(row.get("sube_alanlar") or ""))
            vergino_val = (f"{sube_kod_v} - {sube_adi_v}"
                           if sube_kod_v and sube_adi_v
                           else (sube_adi_v or sube_kod_v or ""))

            byn_kno = _esles(tarih_fmt, "770.01")
            if byn_kno:
                iliski += 1

            kontrol = {musterino: musteri_no, hesapkodu: "770.01",
                       ilktarih: tarih_fmt, "tutar": tutar_val, "aciklama": "vergi"}
            if not _kayit_var_mi(local, kontrol):
                local.execute(
                    """INSERT INTO nakitakis_parametre
                       (musteriNo, hesapKodu, unvan, vergiNo,
                        ilkTarih, sonTarih, tutar, gelirGider, aciklama, iQmod, byn_kayit_no)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (musteri_no, "770.01", unvan_val, vergino_val,
                     tarih_fmt, "", tutar_val, "gider", "vergi", "hareket", byn_kno)
                )
                basari += 1
                detaylar.append({"kod": "770.01", "tarih": tarih_fmt, "tutar": tutar_val})
                esl = f" → byn#{byn_kno}" if byn_kno else " → eşleşme yok"
                _log(f"✔  {basari} kayıt (360→770.01) {tarih_fmt} / {tutar_val:.2f}{esl}")
            else:
                local.execute(
                    """UPDATE nakitakis_parametre
                       SET unvan=?, vergiNo=?, byn_kayit_no=?
                       WHERE musteriNo=? AND hesapKodu='770.01'
                         AND ilkTarih=? AND iQmod='hareket'""",
                    (unvan_val, vergino_val, byn_kno, musteri_no, tarih_fmt)
                )

        # ── 361 → 730.08 ──────────────────────────────────────────────────────
        for row in data_361:
            tarih_fmt   = _fmt_tarih(row["islem_Tarihi"])
            tutar_val   = round(float(row["toplam"] or 0), 2)
            unvan_val   = str(row.get("musteri_unvani") or "-") or "-"
            sube_adi_v  = str(row.get("sube_adi") or "")
            sube_kod_v  = _sube_kodu(str(row.get("sube_alanlar") or ""))
            vergino_val = (f"{sube_kod_v} - {sube_adi_v}"
                           if sube_kod_v and sube_adi_v
                           else (sube_adi_v or sube_kod_v or ""))

            byn_kno = _esles(tarih_fmt, "730.08")
            if byn_kno:
                iliski += 1

            kontrol = {musterino: musteri_no, hesapkodu: "730.08",
                       ilktarih: tarih_fmt, "tutar": tutar_val, "aciklama": "vergi"}
            if not _kayit_var_mi(local, kontrol):
                local.execute(
                    """INSERT INTO nakitakis_parametre
                       (musteriNo, hesapKodu, unvan, vergiNo,
                        ilkTarih, sonTarih, tutar, gelirGider, aciklama, iQmod, byn_kayit_no)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (musteri_no, "730.08", unvan_val, vergino_val,
                     tarih_fmt, "", tutar_val, "gider", "vergi", "hareket", byn_kno)
                )
                basari += 1
                detaylar.append({"kod": "730.08", "tarih": tarih_fmt, "tutar": tutar_val})
                esl = f" → byn#{byn_kno}" if byn_kno else " → eşleşme yok"
                _log(f"✔  {basari} kayıt (361→730.08) {tarih_fmt} / {tutar_val:.2f}{esl}")
            else:
                local.execute(
                    """UPDATE nakitakis_parametre
                       SET unvan=?, vergiNo=?, byn_kayit_no=?
                       WHERE musteriNo=? AND hesapKodu='730.08'
                         AND ilkTarih=? AND iQmod='hareket'""",
                    (unvan_val, vergino_val, byn_kno, musteri_no, tarih_fmt)
                )

        # ── Beyannameleri Önbelleğe Kaydet ────────────────────────────────────
        _log("💾  Beyannameler yerel veritabanına kaydediliyor...")
        eklenen_beyan = 0
        for b_row in data_beyan:
            b_kayit_no = int(b_row["Kayit_No"])
            mevcut = local.execute(
                "SELECT id FROM moy_beyannameler WHERE kayit_no = ?", (b_kayit_no,)
            ).fetchone()
            if mevcut:
                local.execute(
                    """UPDATE moy_beyannameler SET
                        musteri_no=?, belge_tipi=?, belge_turu=?, donem_no=?, donem_adi=?,
                        onay_tarihi=?, belge_no=?, belge_durumu=?, beyan_tarih_1=?, beyan_tarih_2=?,
                        sube_adi=?, sube_alanlar=?, musteri_unvani=?, updated_at=CURRENT_TIMESTAMP
                       WHERE kayit_no = ?""",
                    (
                        musteri_no,
                        str(b_row.get("Belge_Tipi") or ""),
                        str(b_row.get("Belge_Turu") or ""),
                        str(b_row.get("Donem_No") or ""),
                        str(b_row.get("Donem_adi") or ""),
                        str(b_row.get("Onay_Tarihi") or ""),
                        str(b_row.get("Belge_No") or ""),
                        str(b_row.get("Belge_Durumu") or ""),
                        str(b_row.get("Beyan_Tarih_1") or ""),
                        str(b_row.get("Beyan_Tarih_2") or ""),
                        str(b_row.get("Sube_Adi") or ""),
                        str(b_row.get("Sube_Alanlar") or ""),
                        str(b_row.get("Musteri_Unvani") or ""),
                        b_kayit_no,
                    )
                )
            else:
                local.execute(
                    """INSERT INTO moy_beyannameler
                        (musteri_no, kayit_no, belge_tipi, belge_turu, donem_no, donem_adi,
                         onay_tarihi, belge_no, belge_durumu, beyan_tarih_1, beyan_tarih_2,
                         sube_adi, sube_alanlar, musteri_unvani)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        musteri_no, b_kayit_no,
                        str(b_row.get("Belge_Tipi") or ""),
                        str(b_row.get("Belge_Turu") or ""),
                        str(b_row.get("Donem_No") or ""),
                        str(b_row.get("Donem_adi") or ""),
                        str(b_row.get("Onay_Tarihi") or ""),
                        str(b_row.get("Belge_No") or ""),
                        str(b_row.get("Belge_Durumu") or ""),
                        str(b_row.get("Beyan_Tarih_1") or ""),
                        str(b_row.get("Beyan_Tarih_2") or ""),
                        str(b_row.get("Sube_Adi") or ""),
                        str(b_row.get("Sube_Alanlar") or ""),
                        str(b_row.get("Musteri_Unvani") or ""),
                    )
                )
                eklenen_beyan += 1

        if eklenen_beyan > 0:
            _log(f"✔  {eklenen_beyan} beyanname önbelleğe alındı.")

        _log(f"🔗  {iliski}/{basari} ödeme satırı beyanname/tahakkuk ile ilişkilendirildi.")

        local.commit()
        return {
            "success":  True,
            "message":  f"Başarıyla {basari} tane kayıt eklendi. ({iliski} beyanname eşleşti)",
            "eklenen":  basari,
            "detaylar": detaylar,
        }

    except Exception as e:
        local.rollback()
        logger.error("Moy yerel yazma hatası: %s", e)
        return {"success": False, "message": f"Yerel yazma hatası: {e}", "eklenen": basari, "detaylar": []}
    finally:
        local.close()


def _fmt_tarih(tarih_obj) -> str:
    """
    MySQL tarih nesnesini SQLite'a YYYYMMDD formatında (20260126) kaydeder.
    Yıl filtresi: substr(ilkTarih, 1, 4) = '2026'
    Ay filtresi : substr(ilkTarih, 5, 2) = '01'

    PHP'de:  date('d.m.Y', strtotime($row['islem_Tarihi']))  → dd.mm.YYYY
    Biz    : YYYYMMDD kullanıyoruz (sıralama + substr filtresi için daha uygun)
    """
    if not tarih_obj:
        return ""
    try:
        if hasattr(tarih_obj, "strftime"):
            # MySQL driver datetime.date nesnesi döndürür
            return tarih_obj.strftime("%Y%m%d")
        s = str(tarih_obj).strip()
        # YYYY-MM-DD → YYYYMMDD
        if len(s) >= 10 and s[4] == "-":
            return s[:10].replace("-", "")
        # Zaten YYYYMMDD
        if len(s) == 8 and s.isdigit():
            return s
        # dd.mm.YYYY → YYYYMMDD
        if len(s) == 10 and s[2] == "." and s[5] == ".":
            g, a, y = s.split(".")
            return f"{y}{a}{g}"
        return s
    except Exception:
        return str(tarih_obj)


def get_local_beyannameler(musteri_no: int, ilk_tarih: str, hesap_kodu: str = "") -> list[dict]:
    """
    Yerel moy_beyannameler onbellegi tablosundan ilgili tarihe ait beyannameleri bulur.
    Tarih eslestirmesi iki adimli:
      1. Tam odeme tarihi (ilk_tarih) ile dene
      2. Eslesme yoksa o ayin ilk gunu (YYYYMM01) ile tekrar dene
    """
    from db.database import get_connection
    # 770.01 (SGK odemeleri) -> once Tahakkuk (Thk/MUHSGK), sonra Beyanname (Byn/KDV)
    # 730.08 (Muhtasar)      -> yalnizca Beyanname (Byn/MUHSGK veya MUHTAR)
    HESAP_BELGE_MAP = {
        "770.01": [("Thk", "MUHSGK"), ("Byn", "KDV1"), ("Byn", "KDV2")],
        "730.08": [("Byn", "MUHSGK"), ("Byn", "MUHTAR")],
    }
    belge_tipleri_ve_turleri = HESAP_BELGE_MAP.get(hesap_kodu, None)

    # Ay-basi: 20250225 -> 20250201
    ay_basi = (ilk_tarih[:6] + "01" if len(ilk_tarih) >= 6 else ilk_tarih)

    def _build_sql_params(tarih: str) -> tuple:
        """Verilen tarih degeri icin SQL ve parametre demeti olusturur."""
        if belge_tipleri_ve_turleri:
            where_parts = " OR ".join(
                ["(belge_tipi = ? AND belge_turu = ?)" for _ in belge_tipleri_ve_turleri]
            )
            where_params: list = []
            for bt, br in belge_tipleri_ve_turleri:
                where_params.extend([bt, br])
            q = f"""SELECT
                        kayit_no AS kayit_no,
                        belge_tipi AS belge_tipi,
                        belge_turu AS belge_turu,
                        donem_no AS donem_no,
                        donem_adi AS donem_adi,
                        onay_tarihi AS onay_tarihi,
                        belge_no AS belge_no,
                        belge_durumu AS belge_durumu,
                        beyan_tarih_1 AS beyan_tarih_1,
                        beyan_tarih_2 AS beyan_tarih_2,
                        sube_adi AS sgm_kodu,
                        sube_alanlar AS sgm_adi,
                        musteri_unvani AS musteri_unvani
                    FROM moy_beyannameler
                    WHERE musteri_no = ?
                      AND beyan_tarih_1 <= ?
                      AND beyan_tarih_2 >= ?
                      AND ({where_parts})
                    ORDER BY kayit_no DESC"""
            p = (musteri_no, tarih, tarih, *where_params)
        else:
            q = """SELECT
                        kayit_no AS kayit_no,
                        belge_tipi AS belge_tipi,
                        belge_turu AS belge_turu,
                        donem_no AS donem_no,
                        donem_adi AS donem_adi,
                        onay_tarihi AS onay_tarihi,
                        belge_no AS belge_no,
                        belge_durumu AS belge_durumu,
                        beyan_tarih_1 AS beyan_tarih_1,
                        beyan_tarih_2 AS beyan_tarih_2,
                        sube_adi AS sgm_kodu,
                        sube_alanlar AS sgm_adi,
                        musteri_unvani AS musteri_unvani
                   FROM moy_beyannameler
                   WHERE musteri_no = ?
                     AND beyan_tarih_1 <= ?
                     AND beyan_tarih_2 >= ?
                   ORDER BY kayit_no DESC"""
            p = (musteri_no, tarih, tarih)
        return q, p

    conn = get_connection()
    try:
        # 1. Deneme: tam odeme tarihi
        sql, params = _build_sql_params(ilk_tarih)
        rows = conn.execute(sql, params).fetchall()
        result = [dict(r) for r in rows]

        # 2. Deneme: eslesme yoksa ay-basi ile
        if not result and ay_basi != ilk_tarih:
            sql2, params2 = _build_sql_params(ay_basi)
            rows2 = conn.execute(sql2, params2).fetchall()
            result = [dict(r) for r in rows2]

        # Tercih sirasina gore sirala: (belge_tipi, belge_turu) ciftine gore
        if belge_tipleri_ve_turleri and result:
            order_map = {(bt, br): i for i, (bt, br) in enumerate(belge_tipleri_ve_turleri)}
            result.sort(key=lambda r: order_map.get(
                (r.get("belge_tipi", ""), r.get("belge_turu", "")), 999
            ))

        return result
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# Beyanname PDF — Moy'dan gerçek zamanlı çekme
# ─────────────────────────────────────────────────────────────────────────────

def get_beyanname_listesi(musteri_no: int,
                           ilk_tarih_yyyymmdd: str,
                           hesap_kodu: str = "") -> list[dict]:
    """
    nakitakis_parametre satırının tarihine göre ilgili beyannameleri bulur.
    Moy beyanname_listeleri: Beyan_Tarih_1 <= ilkTarih <= Beyan_Tarih_2

    hesap_kodu:
        '770.01' -> KDV ve SGK tahakkuk belgeleri
                    (Thk/MUHSGK tahakkuk fisi, Byn/KDV1, Byn/KDV2)
        '730.08' -> Muhtasar beyanname belgeleri
                    (Byn/MUHSGK, Byn/MUHTAR)
        ''       -> Tum belge turleri (filtre yok)

    Tarih eslestirme iki adimli:
        1. Tam odeme tarihiyle (ilk_tarih_yyyymmdd)
        2. Eslesme yoksa o ayin ilk gunuyle (YYYYMM01)

    Returns: [{'kayit_no', 'belge_turu', 'donem_adi', 'onay_tarihi',
               'beyan_tarih_1', 'beyan_tarih_2', 'belge_no', 'belge_durumu',
               'sgm_kodu', 'sgm_adi', 'musteri_unvani'}, ...]
    """
    # (Belge_Tipi, Belge_Turu) ciftleri - hem Byn hem Thk desteklenir
    # 770.01: Tahakkuk Fisi (Thk/MUHSGK) once, sonra KDV Beyannameleri
    # 730.08: Beyanname (Byn/MUHSGK veya Byn/MUHTAR)
    HESAP_BELGE_MAP: dict[str, list[tuple[str, str]]] = {
        "770.01": [("Thk", "MUHSGK"), ("Byn", "KDV1"), ("Byn", "KDV2")],
        "730.08": [("Byn", "MUHSGK"), ("Byn", "MUHTAR")],
    }
    belge_map = HESAP_BELGE_MAP.get(hesap_kodu)

    # Ay-basi: 20250225 -> 20250201
    ay_basi = (ilk_tarih_yyyymmdd[:6] + "01"
               if len(ilk_tarih_yyyymmdd) >= 6
               else ilk_tarih_yyyymmdd)

    bilgi = get_moy_bilgileri(musteri_no)
    if not bilgi.get("success"):
        return []

    moy_musteri_no = bilgi.get("moyKayitNo", "")
    if not moy_musteri_no:
        return []

    def _build_sql_params(with_sube: bool, tarih: str) -> tuple:
        """
        SQL ve parametre listesi olusturur.
        with_sube=True  -> LEFT JOIN ile sube/unvan bilgisi
        with_sube=False -> Sade sorgu (JOIN hatasi fallback)
        tarih           -> Eslestirilecek YYYYMMDD degeri
        """
        if with_sube:
            sel  = ("bl.Kayit_No, bl.Belge_Tipi, bl.Belge_Turu, bl.Donem_No, bl.Donem_adi,"
                    " bl.Onay_Tarihi, bl.Belge_No, bl.Belge_Durumu,"
                    " bl.Beyan_Tarih_1, bl.Beyan_Tarih_2,"
                    " s.Adi AS Sube_Adi, s.Alanlar AS Sube_Alanlar,"
                    " mk.Soyadi_Unvani AS Musteri_Unvani")
            frm  = ("beyanname_listeleri bl"
                    " LEFT JOIN tanim_musteri_subeleri s ON s.Kayit_No = bl.Sube_Kayit_No"
                    " LEFT JOIN tanim_musteri_karti mk ON mk.Kayit_No = bl.Musteri_Kayit_No")
            mk_col = "bl.Musteri_Kayit_No"
            bt_col = "bl.Belge_Tipi"
            btr_col = "bl.Belge_Turu"
            t1_col = "bl.Beyan_Tarih_1"
            t2_col = "bl.Beyan_Tarih_2"
            ord_col = "bl.Kayit_No"
        else:
            sel  = ("Kayit_No, Belge_Tipi, Belge_Turu, Donem_No, Donem_adi,"
                    " Onay_Tarihi, Belge_No, Belge_Durumu, Beyan_Tarih_1, Beyan_Tarih_2")
            frm  = "beyanname_listeleri"
            mk_col = "Musteri_Kayit_No"
            bt_col = "Belge_Tipi"
            btr_col = "Belge_Turu"
            t1_col = "Beyan_Tarih_1"
            t2_col = "Beyan_Tarih_2"
            ord_col = "Kayit_No"

        params: list = [moy_musteri_no]

        if belge_map:
            # Dinamik (Belge_Tipi, Belge_Turu) OR kosulu - Byn sabit degil!
            parts = []
            for tip, tur in belge_map:
                parts.append(f"({bt_col} = %s AND {btr_col} = %s)")
                params.extend([tip, tur])
            tip_tur_where = f"AND ({' OR '.join(parts)})"
        else:
            # Hesap kodu bilinmiyor -> tum Byn ve Thk belgeler
            tip_tur_where = f"AND {bt_col} IN ('Byn', 'Thk')"

        params.extend([tarih, tarih])

        sql = (f"SELECT {sel}"
               f" FROM {frm}"
               f" WHERE {mk_col} = %s {tip_tur_where}"
               f" AND {t1_col} <= %s AND {t2_col} >= %s"
               f" ORDER BY {ord_col} DESC")
        return sql, params

    def _parse_sube_kod(alanlar) -> str:
        if not alanlar:
            return ""
        parca = str(alanlar).split("[|]")
        return (parca[0] or "").strip() if parca else ""

    def _rows_to_dict(rows: list, has_sube: bool) -> list[dict]:
        result = []
        for r in rows:
            sube_adi = str(r.get("Sube_Adi") or "") if has_sube else ""
            sube_kod = _parse_sube_kod(str(r.get("Sube_Alanlar") or "")) if has_sube else ""
            unvan    = str(r.get("Musteri_Unvani") or "") if has_sube else ""
            result.append({
                "kayit_no":       r["Kayit_No"],
                "belge_turu":     r["Belge_Turu"] or "",
                "donem_adi":      r["Donem_adi"] or "",
                "donem_no":       r["Donem_No"] or "",
                "onay_tarihi":    r["Onay_Tarihi"] or "",
                "beyan_tarih_1":  r["Beyan_Tarih_1"] or "",
                "beyan_tarih_2":  r["Beyan_Tarih_2"] or "",
                "belge_no":       r["Belge_No"] or "",
                "belge_durumu":   r["Belge_Durumu"] or "",
                "sgm_kodu":       sube_kod,
                "sgm_adi":        sube_adi,
                "musteri_unvani": unvan,
            })
        # Tercih sirasina gore sirala: HESAP_BELGE_MAP sirasi
        if belge_map:
            order_map = {(tip, tur): i for i, (tip, tur) in enumerate(belge_map)}
            result.sort(key=lambda x: order_map.get(
                (x.get("belge_turu", ""), x.get("belge_turu", "")), 999
            ))
        return result

    def _calistir(cursor, with_sube: bool, tarih: str):
        """
        Sorguyu calistir, JOIN hatasi olursa None donerr.
        """
        sql, params = _build_sql_params(with_sube=with_sube, tarih=tarih)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall(), with_sube
        except Exception as err:
            err_str = str(err)
            if with_sube and any(k in err_str for k in
                                 ("1054", "1146", "Unknown column",
                                  "doesn't exist", "Table")):
                logger.info("JOIN sorgusu basarisiz (%s), sade sorgu deneniyor.", err)
                sql2, params2 = _build_sql_params(with_sube=False, tarih=tarih)
                try:
                    cursor.execute(sql2, params2)
                    return cursor.fetchall(), False
                except Exception as e2:
                    logger.warning("Sade sorgu da basarisiz: %s", e2)
                    return [], False
            logger.warning("Beyanname sorgu hatasi (%s): %s", tarih, err)
            return [], with_sube

    try:
        cnx = _moy_connect(bilgi["url"], bilgi["username"], bilgi["sifre"])
        cursor = cnx.cursor(dictionary=True)

        # 1. Deneme: tam odeme tarihiyle
        rows, has_sube = _calistir(cursor, with_sube=True,
                                   tarih=ilk_tarih_yyyymmdd)

        # 2. Deneme: eslesme yoksa ay-basi ile
        if not rows and ay_basi != ilk_tarih_yyyymmdd:
            logger.info(
                "Tam tarih (%s) ile eslesme yok, ay-basi (%s) deneniyor.",
                ilk_tarih_yyyymmdd, ay_basi
            )
            rows, has_sube = _calistir(cursor, with_sube=True, tarih=ay_basi)

        cursor.close()
        cnx.close()
        return _rows_to_dict(rows, has_sube=has_sube)

    except Exception as e:
        logger.error("Beyanname listesi hatasi: %s", e)
        return []



def get_beyanname_pdf_bytes(musteri_no: int, kayit_no: int) -> Optional[bytes]:
    """
    beyanname_gib.Belge_Data alanından PDF ham verisini (bytes) döndürür.
    kayit_no: beyanname_listeleri.Kayit_No değeri

    Returns: PDF bytes veya None
    """
    bilgi = get_moy_bilgileri(musteri_no)
    if not bilgi.get("success"):
        return None
    try:
        cnx = _moy_connect(bilgi["url"], bilgi["username"], bilgi["sifre"])
        cursor = cnx.cursor()
        cursor.execute(
            "SELECT Belge_Data FROM beyanname_gib WHERE Byn_Kayit_No = %s LIMIT 1",
            (kayit_no,)
        )
        row = cursor.fetchone()
        cursor.close()
        cnx.close()
        if row and row[0]:
            data = row[0]
            # bytes veya bytearray olabilir
            return bytes(data) if not isinstance(data, bytes) else data
        return None
    except Exception as e:
        logger.error("Beyanname PDF çekme hatası: %s", e)
        return None
