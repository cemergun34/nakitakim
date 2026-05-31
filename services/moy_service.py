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
    for charset in ("utf8", "utf8mb4", "latin1"):
        try:
            cnx = mc.connect(**base_cfg, charset=charset)
            logger.debug("Moy bağlantısı charset=%s ile kuruldu", charset)
            return cnx
        except mc.errors.DatabaseError as e:
            if "1115" in str(e) or "Unknown character set" in str(e):
                logger.warning("Charset %s desteklenmiyor, deneniyor...", charset)
                continue
            raise
    raise RuntimeError("Desteklenen charset bulunamadı. Sunucu utf8/utf8mb4/latin1 charset'lerini reddetti.")


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
    PHP: ajax/moy/moykaydet.php'nin tam karşılığı.

    progress_cb: opsiyonel callable(str) — ilerleme mesajı için
    Returns: {"success": bool, "message": str, "eklenen": int}
    """
    def _log(msg: str):
        if progress_cb:
            progress_cb(msg)

    # Lokal DB'den Moy bağlantı bilgilerini al
    bilgi = get_moy_bilgileri(musteri_no)
    if not bilgi.get("success"):
        return {"success": False, "message": "Moy bağlantı bilgileri bulunamadı. Önce Test edin.", "eklenen": 0}

    host       = bilgi["url"]
    user       = bilgi["username"]
    password   = bilgi["sifre"]
    kayit_nom  = bilgi["moyKayitNo"]

    t1 = f"{yil}0101"
    t2 = f"{yil}1231"

    _log(f"🔗  Moy sunucusuna bağlanılıyor ({host})...")

    try:
        cnx = _moy_connect(host, user, password)
    except Exception as e:
        return {"success": False, "message": f"Moy bağlantı hatası: {e}", "eklenen": 0}

    try:
        cursor = cnx.cursor(dictionary=True)

        # 360 kodu — PHP moykaydet.php ile birebir
        _log("📊  360 hesap kodu sorgulanıyor...")
        cursor.execute(
            """SELECT SUM(ht.Alacak) as toplam, ht.islem_Tarihi
               FROM haraket_tablosu ht
               WHERE ht.Alacak > 0
                 AND ht.islem_Tarihi BETWEEN %s AND %s
                 AND ht.Musteri_Kayit_No = %s
                 AND ht.Hesap_Kodu_1='360'
               GROUP BY ht.islem_Tarihi
               ORDER BY ht.islem_Tarihi ASC""",
            (t1, t2, kayit_nom)
        )
        data_360 = cursor.fetchall()

        # 361 kodu
        _log("📊  361 hesap kodu sorgulanıyor...")
        cursor.execute(
            """SELECT SUM(ht.Alacak) as toplam, ht.islem_Tarihi
               FROM haraket_tablosu ht
               WHERE ht.Alacak > 0
                 AND ht.islem_Tarihi BETWEEN %s AND %s
                 AND ht.Musteri_Kayit_No = %s
                 AND ht.Hesap_Kodu_1='361'
               GROUP BY ht.islem_Tarihi
               ORDER BY ht.islem_Tarihi ASC""",
            (t1, t2, kayit_nom)
        )
        data_361 = cursor.fetchall()
        cursor.close()
        cnx.close()

    except Exception as e:
        cnx.close()
        return {"success": False, "message": f"Moy sorgu hatası: {e}", "eklenen": 0}

    if not data_360 and not data_361:
        return {"success": False, "message": "Kayıt bulunamadı.", "eklenen": 0}

    # Lokal DB'ye yaz
    local = get_connection()
    basari = 0
    detaylar = []   # hangi verilerin çekildiği bilgisi
    try:
        # 360 → 770.01 (PHP ile aynı eşleşme)
        for row in data_360:
            tarih_fmt = _fmt_tarih(row["islem_Tarihi"])
            tutar_val = round(float(row["toplam"] or 0), 2)
            insert_data = {
                musterino:  musteri_no,
                hesapkodu:  "770.01",
                "unvan":      "-",
                vergino:    "",
                ilktarih:   tarih_fmt,
                sontarih:   "",
                "tutar":      tutar_val,
                gelirgider: "gider",
                "aciklama":   "vergi",
                iqmod:      "hareket",
            }
            if not _kayit_var_mi(local, insert_data):
                local.execute(
                    """INSERT INTO nakitakis_parametre
                       (musteriNo, hesapKodu, unvan, vergiNo,
                        ilkTarih, sonTarih, tutar, gelirGider, aciklama, iQmod)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        insert_data[musterino],
                        insert_data[hesapkodu],
                        insert_data["unvan"],
                        insert_data[vergino],
                        insert_data[ilktarih],
                        insert_data[sontarih],
                        insert_data["tutar"],
                        insert_data[gelirgider],
                        insert_data["aciklama"],
                        insert_data[iqmod],
                    )
                )
                basari += 1
                detaylar.append({"kod": "770.01", "tarih": tarih_fmt, "tutar": tutar_val})
                _log(f"✔  {basari} kayıt işlendi (360→770.01) — {tarih_fmt} / {tutar_val:.2f}...")

        # 361 → 730.08
        for row in data_361:
            tarih_fmt = _fmt_tarih(row["islem_Tarihi"])
            tutar_val = round(float(row["toplam"] or 0), 2)
            insert_data = {
                musterino:  musteri_no,
                hesapkodu:  "730.08",
                "unvan":      "-",
                vergino:    "",
                ilktarih:   tarih_fmt,
                sontarih:   "",
                "tutar":      tutar_val,
                gelirgider: "gider",
                "aciklama":   "vergi",
                iqmod:      "hareket",
            }
            if not _kayit_var_mi(local, insert_data):
                local.execute(
                    """INSERT INTO nakitakis_parametre
                       (musteriNo, hesapKodu, unvan, vergiNo,
                        ilkTarih, sonTarih, tutar, gelirGider, aciklama, iQmod)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        insert_data[musterino],
                        insert_data[hesapkodu],
                        insert_data["unvan"],
                        insert_data[vergino],
                        insert_data[ilktarih],
                        insert_data[sontarih],
                        insert_data["tutar"],
                        insert_data[gelirgider],
                        insert_data["aciklama"],
                        insert_data[iqmod],
                    )
                )
                basari += 1
                detaylar.append({"kod": "730.08", "tarih": tarih_fmt, "tutar": tutar_val})
                _log(f"✔  {basari} kayıt işlendi (361→730.08) — {tarih_fmt} / {tutar_val:.2f}...")

        local.commit()
        return {
            "success": True,
            "message": f"Başarıyla {basari} tane kayıt eklendi.",
            "eklenen": basari,
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


# ─────────────────────────────────────────────────────────────────────────────
# Beyanname PDF — Moy'dan gerçek zamanlı çekme
# ─────────────────────────────────────────────────────────────────────────────

def get_beyanname_listesi(musteri_no: int,
                           ilk_tarih_yyyymmdd: str) -> list[dict]:
    """
    nakitakis_parametre satırının tarihine göre ilgili beyannameleri bulur.
    Moy beyanname_listeleri: Beyan_Tarih_1 <= ilkTarih <= Beyan_Tarih_2

    ilk_tarih_yyyymmdd: '20260126' gibi YYYYMMDD formatı

    Returns: [{'kayit_no', 'belge_turu', 'donem_adi', 'onay_tarihi',
               'beyan_tarih_1', 'beyan_tarih_2', 'belge_no', 'belge_durumu'}, ...]
    """
    bilgi = get_moy_bilgileri(musteri_no)
    if not bilgi.get("success"):
        return []

    moy_musteri_no = bilgi.get("moyKayitNo", "")
    if not moy_musteri_no:
        return []

    try:
        cnx = _moy_connect(bilgi["url"], bilgi["username"], bilgi["sifre"])
        cursor = cnx.cursor(dictionary=True)
        cursor.execute(
            """SELECT Kayit_No, Belge_Tipi, Belge_Turu, Donem_No, Donem_adi,
                      Onay_Tarihi, Belge_No, Belge_Durumu,
                      Beyan_Tarih_1, Beyan_Tarih_2
               FROM beyanname_listeleri
               WHERE Musteri_Kayit_No = %s
                 AND Belge_Tipi = 'Byn'
                 AND Beyan_Tarih_1 <= %s
                 AND Beyan_Tarih_2 >= %s
               ORDER BY Kayit_No DESC""",
            (moy_musteri_no, ilk_tarih_yyyymmdd, ilk_tarih_yyyymmdd)
        )
        rows = cursor.fetchall()
        cursor.close()
        cnx.close()
        return [
            {
                "kayit_no":      r["Kayit_No"],
                "belge_turu":    r["Belge_Turu"] or "",
                "donem_adi":     r["Donem_adi"] or "",
                "donem_no":      r["Donem_No"] or "",
                "onay_tarihi":   r["Onay_Tarihi"] or "",
                "beyan_tarih_1": r["Beyan_Tarih_1"] or "",
                "beyan_tarih_2": r["Beyan_Tarih_2"] or "",
                "belge_no":      r["Belge_No"] or "",
                "belge_durumu":  r["Belge_Durumu"] or "",
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Beyanname listesi hatası: %s", e)
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
