# -*- coding: utf-8 -*-
"""
PayTR Sanal Pos Servisi — PyQt6 backend
=========================================
Dashboard'daki "Sanal Pos Paytr" kartı ve açılan modalın PHP karşılığı.

PHP kaynaklar:
  lib/panelparcalari/admin/admin.php  (satır 1005-1019)  → Dashboard kartı
  ajax/get_sanal_pos_hareketleri.php                     → get_sanal_pos_hareketleri()
  ajax/paytr_sync_chunk.php                              → sync_chunk() + get_last_sync() + ensure_tables()

DB Tabloları (SQLite karşılığı):
  paytr           — PayTR işlem dökümü (API'den ya da veritabanından)
  paytr_sync_log  — Son senkronizasyon tarihi
  apisanalpos     — Mağaza No / Parola / Gizli Anahtar (API kimlik bilgileri)

Genel akış:
  1. Dashboard açıldığında get_last_sync() ile son sync tarihini + özet tutarları getir.
  2. Kullanıcı karta tıklayınca modal açılır; tarih filtresi ile get_sanal_pos_hareketleri() çağrılır.
  3. Sync butonu ile paytr_sync_chunk() chunk-by-chunk çalışır (30 günlük batch, 3 günlük alt parçalar).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

from db.database import get_connection

# ---------------------------------------------------------------------------
# 0. TABLO OLUŞTURMA (paytr_sync_chunk.php → CREATE TABLE IF NOT EXISTS)
# ---------------------------------------------------------------------------

_PAYTR_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS paytr (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    userid            INTEGER NOT NULL,
    musterino         TEXT    NOT NULL DEFAULT '',
    islemtarihi       TEXT    DEFAULT NULL,
    siparisno         TEXT    DEFAULT NULL,
    islemtutari       REAL    DEFAULT 0.0,
    odemetutari       REAL    DEFAULT 0.0,
    kur               TEXT    DEFAULT 'TL',
    magazano          TEXT    DEFAULT NULL,
    adsoyad           TEXT    DEFAULT NULL,
    nettutar          REAL    DEFAULT 0.0,
    kesintitutari     REAL    DEFAULT 0.0,
    kesintiorani      TEXT    DEFAULT NULL,
    kartbankasi       TEXT    DEFAULT NULL,
    kartmarkasi       TEXT    DEFAULT NULL,
    kartno            TEXT    DEFAULT NULL,
    odemetipi         TEXT    DEFAULT NULL,
    karttipi          TEXT    DEFAULT NULL,
    taksitsayisi      INTEGER DEFAULT 0,
    guncelleme_tarihi TEXT    DEFAULT CURRENT_TIMESTAMP,
    created_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (userid, siparisno)
);

CREATE TABLE IF NOT EXISTS paytr_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    userid          INTEGER NOT NULL,
    musterino       TEXT    NOT NULL DEFAULT '',
    son_sync_tarihi TEXT    DEFAULT NULL,
    updated_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (userid, musterino)
);

CREATE TABLE IF NOT EXISTS apisanalpos (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    userid                INTEGER NOT NULL,
    firma_adi             TEXT    DEFAULT '',
    magaza_no             TEXT    DEFAULT '',
    magaza_parola         TEXT    DEFAULT '',
    magaza_gizli_anahtar  TEXT    DEFAULT '',
    kayit_tarihi          TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_paytr_userid_islemtarihi
    ON paytr(userid, islemtarihi);
CREATE INDEX IF NOT EXISTS idx_paytr_sync_log_userid
    ON paytr_sync_log(userid, musterino);
CREATE INDEX IF NOT EXISTS idx_apisanalpos_userid
    ON apisanalpos(userid);
"""


def ensure_tables() -> None:
    """
    paytr, paytr_sync_log ve apisanalpos tablolarını oluşturur (yoksa).
    PHP: paytr_sync_chunk.php → CREATE TABLE IF NOT EXISTS bloğu.
    """
    conn = get_connection()
    try:
        conn.executescript(_PAYTR_TABLES_SQL)
        conn.commit()
    except Exception:
        pass  # Tablolar zaten varsa devam et
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. YARDIMCI: Türkçe tutar formatı
# ---------------------------------------------------------------------------

def _fmt_tl(val: float) -> str:
    """float → '₺1.234,56' (PHP number_format karşılığı)"""
    formatted = f"{abs(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if val < 0:
        return f"-₺{formatted}"
    elif val > 0:
        return f"+₺{formatted}"
    return f"₺{formatted}"


def _fmt_tl_plain(val: float) -> str:
    """float → '₺1.234,56' (işaret yok)"""
    formatted = f"{abs(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"₺{formatted}"


# ---------------------------------------------------------------------------
# 2. SON SENKRONİZASYON BİLGİSİ (paytr_sync_chunk.php → action=get_last_sync)
# ---------------------------------------------------------------------------

def get_last_sync(userid: int, musterino: str) -> dict:
    """
    Son senkronizasyon tarihini + paytr tablosundaki toplam islem/odeme tutarlarını döndürür.

    PHP: paytr_sync_chunk.php → action=get_last_sync
    Dashboard kartındaki 'paytrToplamBadge', 'paytrDashIslem', 'paytrDashOdeme'
    ve 'paytrSonGuncelleme' alanlarına karşılık gelir.

    Returns:
        {
            'success': bool,
            'son_sync_tarihi': str | None,
            'islem': '₺...',
            'odeme': '₺...',
            'fark': '₺...',
            'fark_val': float
        }
    """
    ensure_tables()
    conn = get_connection()
    try:
        # Son sync tarihi
        row = conn.execute(
            "SELECT son_sync_tarihi FROM paytr_sync_log "
            "WHERE userid = ? AND musterino = ?",
            (userid, str(musterino))
        ).fetchone()

        # Toplam tutarlar (tüm zamanlar)
        totals = conn.execute(
            "SELECT SUM(islemtutari) AS islem, SUM(odemetutari) AS odeme "
            "FROM paytr WHERE userid = ? AND musterino = ?",
            (userid, str(musterino))
        ).fetchone()

        islem = float(totals["islem"] or 0) if totals else 0.0
        odeme = float(totals["odeme"] or 0) if totals else 0.0
        fark  = odeme - islem

        return {
            "success": True,
            "son_sync_tarihi": row["son_sync_tarihi"] if row else None,
            "islem":   _fmt_tl_plain(islem),
            "odeme":   _fmt_tl_plain(odeme),
            "fark":    _fmt_tl_plain(abs(fark)),
            "fark_val": fark,
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. SANAL POS HAREKETLERİ — VERİTABANINDAN (parametre=1)
# ---------------------------------------------------------------------------

def get_sanal_pos_hareketleri_db(
    userid: int,
    musterino: str,
    ilk_tarih: str,
    son_tarih: str,
) -> dict:
    """
    paytr tablosundan tarih aralığına göre hareketleri getirir.

    PHP: ajax/get_sanal_pos_hareketleri.php → parametre=1 (Veritabanından)
    Modal tablodaki sütunlar:
      İşlem Tarihi | Sipariş No | İşlem Tutarı | Ödeme Tutarı | Kur |
      Mağaza No | Net Tutar | Kesinti Tutarı | Kesinti Oranı |
      Kart Markası | Kart No | Ödeme Tipi | Kart Tipi | Taksit Sayısı

    Args:
        userid:     Kullanıcı ID
        musterino:  Müşteri No
        ilk_tarih:  'YYYY-MM-DD'
        son_tarih:  'YYYY-MM-DD'

    Returns:
        {
            'success': bool,
            'kaynak': 'veritabani',
            'data': [dict, ...],
            'toplam_islem': float,
            'toplam_odeme': float,
            'toplam_fark': float,
            'toplam_islem_fmt': '₺...',
            'toplam_odeme_fmt': '₺...',
            'toplam_fark_fmt': '±₺...',
            'kayit_sayisi': int
        }
    """
    ensure_tables()

    # Tarih sınırları (PHP: $ilkFmt / $sonFmt)
    try:
        ilk_dt = datetime.strptime(ilk_tarih, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0
        )
        son_dt = datetime.strptime(son_tarih, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    except ValueError as exc:
        return {"success": False, "message": f"Tarih formatı hatalı: {exc}"}

    ilk_fmt = ilk_dt.strftime("%Y-%m-%d %H:%M:%S")
    son_fmt = son_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        # PHP'deki COALESCE(STR_TO_DATE(...)) yerine basit TEXT karşılaştırması.
        # islemtarihi kayıtları 'YYYY-MM-DD HH:MM:SS' formatında tutulduğu varsayılır.
        # Farklı formatlar için _normalize_date() yardımcısı kullanılır.
        sql = """
            SELECT
                islemtarihi, siparisno,
                islemtutari, odemetutari, kur,
                magazano, adsoyad,
                nettutar, kesintitutari, kesintiorani,
                kartbankasi, kartmarkasi, kartno,
                odemetipi, karttipi, taksitsayisi
            FROM paytr
            WHERE userid = ?
              AND musterino = ?
              AND islemtarihi IS NOT NULL
              AND islemtarihi != ''
              AND _normalized_date(islemtarihi) BETWEEN ? AND ?
            ORDER BY _normalized_date(islemtarihi) DESC
        """

        # SQLite kendi fonksiyonu olmadığı için Python tarafında filtreleyeceğiz
        rows_all = conn.execute(
            """
            SELECT
                islemtarihi, siparisno,
                islemtutari, odemetutari, kur,
                magazano, adsoyad,
                nettutar, kesintitutari, kesintiorani,
                kartbankasi, kartmarkasi, kartno,
                odemetipi, karttipi, taksitsayisi
            FROM paytr
            WHERE userid = ?
              AND musterino = ?
              AND islemtarihi IS NOT NULL
              AND islemtarihi != ''
            """,
            (userid, str(musterino))
        ).fetchall()

        toplam_islem = 0.0
        toplam_odeme = 0.0
        data = []

        for r in rows_all:
            r = dict(r)
            # Tarih normalizasyonu (PHP'deki çoklu STR_TO_DATE COALESCE)
            norm = _normalize_date(r.get("islemtarihi", ""))
            if not norm:
                continue
            if norm < ilk_fmt or norm > son_fmt:
                continue

            toplam_islem += float(r.get("islemtutari") or 0)
            toplam_odeme += float(r.get("odemetutari") or 0)
            data.append(r)

        # PHP ile aynı sıralama: DESC
        data.sort(key=lambda x: _normalize_date(x.get("islemtarihi", "")) or "", reverse=True)

        toplam_fark = toplam_odeme - toplam_islem

        return {
            "success": True,
            "kaynak": "veritabani",
            "data": data,
            "toplam_islem": toplam_islem,
            "toplam_odeme": toplam_odeme,
            "toplam_fark": toplam_fark,
            "toplam_islem_fmt": _fmt_tl_plain(toplam_islem),
            "toplam_odeme_fmt": _fmt_tl_plain(toplam_odeme),
            "toplam_fark_fmt": _fmt_tl(toplam_fark),
            "kayit_sayisi": len(data),
        }

    except Exception as exc:
        return {"success": False, "message": f"Veritabanı hatası: {exc}"}
    finally:
        conn.close()


def _normalize_date(val: str) -> Optional[str]:
    """
    Farklı tarih formatlarını 'YYYY-MM-DD HH:MM:SS' biçimine dönüştürür.
    PHP'deki COALESCE(STR_TO_DATE(...)) karşılığı.

    Desteklenen formatlar:
      '%d.%m.%Y %H:%M:%S'  →  '01.05.2025 14:30:00'
      '%d.%m.%Y'           →  '01.05.2025'
      '%Y-%m-%d %H:%M:%S'  →  '2025-05-01 14:30:00'
      '%Y-%m-%d'           →  '2025-05-01'
      '%d/%m/%Y %H:%M:%S'
      '%d/%m/%Y'
    """
    if not val:
        return None
    formats = [
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val.strip(), fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 4. SANAL POS HAREKETLERİ — API'DEN (parametre=2)
# ---------------------------------------------------------------------------

def get_sanal_pos_hareketleri_api(
    userid: int,
    ilk_tarih: str,
    son_tarih: str,
) -> dict:
    """
    PayTR API'den işlem dökümü çeker (veritabanına kaydetmez, sadece gösterir).

    PHP: ajax/get_sanal_pos_hareketleri.php → parametre=2
    PayTR API max 3 gün destekler → 3 günlük chunk'lar ile döngü kurulur.

    Args:
        userid:    Kullanıcı ID (apisanalpos tablosundan API bilgilerini çeker)
        ilk_tarih: 'YYYY-MM-DD'
        son_tarih: 'YYYY-MM-DD'

    Returns:
        {
            'success': bool,
            'kaynak': 'api',
            'data': [dict, ...],
            'toplam_islem': float,
            'toplam_odeme': float,
            'toplam_fark': float,
            'toplam_islem_fmt': '₺...',
            'toplam_odeme_fmt': '₺...',
            'toplam_fark_fmt': '±₺...',
            'kayit_sayisi': int,
            'uyarilar': [str, ...]  # Opsiyonel
        }
    """
    ensure_tables()

    try:
        ilk_obj = datetime.strptime(ilk_tarih, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
        son_obj = datetime.strptime(son_tarih, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError as exc:
        return {"success": False, "message": f"Tarih formatı hatalı: {exc}"}

    # API bilgilerini oku (apisanalpos tablosu)
    conn = get_connection()
    try:
        api_kayitlar = conn.execute(
            "SELECT id, firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar "
            "FROM apisanalpos WHERE userid = ? ORDER BY id DESC",
            (userid,)
        ).fetchall()
        api_kayitlar = [dict(r) for r in api_kayitlar]
    except Exception as exc:
        return {"success": False, "message": f"API kayıtları okunamadı: {exc}"}
    finally:
        conn.close()

    if not api_kayitlar:
        return {
            "success": False,
            "message": (
                "Ayarlar > Eklentiler bölümünde hiç API sanal POS kaydı bulunamadı. "
                "Lütfen önce Mağaza No, Parola ve Gizli Anahtar bilgilerini kaydedin."
            ),
        }

    tum_data: list[dict] = []
    toplam_islem = 0.0
    toplam_odeme = 0.0
    hatalar: list[str] = []

    for api in api_kayitlar:
        merchant_id   = api["magaza_no"]
        merchant_key  = api["magaza_parola"]
        merchant_salt = api["magaza_gizli_anahtar"]
        firma_adi     = api.get("firma_adi") or merchant_id

        if not merchant_id or not merchant_key or not merchant_salt:
            hatalar.append(f"{firma_adi}: API bilgileri eksik.")
            continue

        # 3 günlük chunk'lar (PHP: while ($currentStart <= $sonObj))
        current_start = ilk_obj.replace(hour=0, minute=0, second=0)

        while current_start <= son_obj:
            chunk_end = current_start + timedelta(days=2)
            chunk_end = chunk_end.replace(hour=23, minute=59, second=59)
            if chunk_end > son_obj:
                chunk_end = son_obj.replace(hour=23, minute=59, second=59)

            start_date = current_start.strftime("%Y-%m-%d %H:%M:%S")
            end_date   = chunk_end.strftime("%Y-%m-%d %H:%M:%S")

            # HMAC imzası (PHP: base64_encode(hash_hmac('sha256', ...)))
            hash_str = merchant_id + start_date + end_date + merchant_salt
            token    = base64.b64encode(
                hmac.new(
                    merchant_key.encode("utf-8"),
                    hash_str.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")

            post_data = {
                "merchant_id": merchant_id,
                "start_date":  start_date,
                "end_date":    end_date,
                "paytr_token": token,
            }

            # PayTR API isteği (PHP: curl_exec)
            try:
                response = _paytr_api_request(post_data)
            except Exception as exc:
                hatalar.append(f"{firma_adi} ({start_date}): İstek hatası: {exc}")
                current_start += timedelta(days=3)
                current_start = current_start.replace(hour=0, minute=0, second=0)
                time.sleep(0.2)
                continue

            import json as _json
            try:
                api_sonuc = _json.loads(response)
            except Exception:
                hatalar.append(f"{firma_adi} ({start_date}): API geçersiz yanıt döndürdü.")
                current_start += timedelta(days=3)
                current_start = current_start.replace(hour=0, minute=0, second=0)
                time.sleep(0.2)
                continue

            if not api_sonuc or "status" not in api_sonuc:
                hatalar.append(f"{firma_adi} ({start_date}): API geçersiz yanıt döndürdü.")
            elif api_sonuc["status"] != "success":
                err_msg = api_sonuc.get("err_msg") or api_sonuc.get("message") or "Bilinmeyen API hatası"
                hatalar.append(f"{firma_adi} ({start_date}): {err_msg}")
            else:
                # Başarılı chunk — işlemleri birleştir (PHP: $tumData[])
                transactions = api_sonuc.get("list") or []
                for t in transactions:
                    islem_tutari = float(t.get("islem_tutari") or 0)
                    odeme_tutari = float(t.get("odeme_tutari") or 0)
                    toplam_islem += islem_tutari
                    toplam_odeme += odeme_tutari
                    tum_data.append({
                        "islemtarihi":   t.get("islem_tarihi", ""),
                        "siparisno":     t.get("siparis_no", ""),
                        "islemtutari":   islem_tutari,
                        "odemetutari":   odeme_tutari,
                        "kur":           t.get("para_birimi", "TL"),
                        "magazano":      merchant_id,
                        "adsoyad":       "",
                        "nettutar":      float(t.get("net_tutar") or 0),
                        "kesintitutari": float(t.get("kesinti_tutari") or 0),
                        "kesintiorani":  t.get("kesinti_orani", ""),
                        "kartbankasi":   "",
                        "kartmarkasi":   t.get("kart_marka", ""),
                        "kartno":        t.get("kart_no", ""),
                        "odemetipi":     t.get("odeme_tipi", ""),
                        "karttipi":      "",
                        "taksitsayisi":  t.get("taksit", ""),
                    })

            # Sonraki 3 günlük chunk
            current_start += timedelta(days=3)
            current_start = current_start.replace(hour=0, minute=0, second=0)
            time.sleep(0.2)  # PHP: usleep(200000)

    toplam_fark = toplam_odeme - toplam_islem
    sonuc = {
        "success": True,
        "kaynak": "api",
        "data": tum_data,
        "toplam_islem": toplam_islem,
        "toplam_odeme": toplam_odeme,
        "toplam_fark": toplam_fark,
        "toplam_islem_fmt": _fmt_tl_plain(toplam_islem),
        "toplam_odeme_fmt": _fmt_tl_plain(toplam_odeme),
        "toplam_fark_fmt": _fmt_tl(toplam_fark),
        "kayit_sayisi": len(tum_data),
    }
    if hatalar:
        sonuc["uyarilar"] = hatalar
    return sonuc


# ---------------------------------------------------------------------------
# 5. CHUNK SYNC (paytr_sync_chunk.php → chunk_start / chunk_end)
# ---------------------------------------------------------------------------

def sync_chunk(
    userid: int,
    musterino: str,
    chunk_start: str,
    chunk_end: str,
) -> dict:
    """
    Belirli bir 30 günlük batch için PayTR API'den işlem dökümü çeker
    ve paytr tablosuna INSERT OR IGNORE ile kaydeder.

    PHP: ajax/paytr_sync_chunk.php → CHUNK SYNC bloğu

    Args:
        userid:      Kullanıcı ID
        musterino:   Müşteri No
        chunk_start: 'YYYY-MM-DD'
        chunk_end:   'YYYY-MM-DD'

    Returns:
        {
            'success': bool,
            'inserted': int,
            'skipped': int,
            'chunk_start': str,
            'chunk_end': str,
            'message': str,
            'uyarilar': [str, ...]  # Opsiyonel
        }
    """
    ensure_tables()
    import json as _json

    try:
        start_obj = datetime.strptime(chunk_start, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
        end_obj   = datetime.strptime(chunk_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError as exc:
        return {"success": False, "message": f"Tarih formatı hatalı: {exc}"}

    # API bilgilerini oku
    conn = get_connection()
    try:
        api_kayitlar = conn.execute(
            "SELECT id, firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar "
            "FROM apisanalpos WHERE userid = ? ORDER BY id DESC",
            (userid,)
        ).fetchall()
        api_kayitlar = [dict(r) for r in api_kayitlar]
    except Exception as exc:
        conn.close()
        return {"success": False, "message": f"API kayıtları okunamadı: {exc}"}

    if not api_kayitlar:
        conn.close()
        return {
            "success": False,
            "message": (
                "Ayarlar > Eklentiler bölümünde hiç API sanal POS kaydı bulunamadı. "
                "Lütfen önce Mağaza No, Parola ve Gizli Anahtar bilgilerini kaydedin."
            ),
        }

    # INSERT OR IGNORE hazırlığı (PHP: INSERT IGNORE)
    insert_sql = """
        INSERT OR IGNORE INTO paytr
            (userid, musterino, islemtarihi, siparisno, islemtutari, odemetutari, kur,
             magazano, adsoyad, nettutar, kesintitutari, kesintiorani,
             kartbankasi, kartmarkasi, kartno, odemetipi, karttipi, taksitsayisi,
             guncelleme_tarihi)
        VALUES
            (?, ?, ?, ?, ?, ?, ?,
             ?, ?, ?, ?, ?,
             ?, ?, ?, ?, ?, ?,
             CURRENT_TIMESTAMP)
    """

    total_inserted = 0
    total_skipped  = 0
    hatalar: list[str] = []

    try:
        for api in api_kayitlar:
            merchant_id   = api["magaza_no"]
            merchant_key  = api["magaza_parola"]
            merchant_salt = api["magaza_gizli_anahtar"]
            firma_adi     = api.get("firma_adi") or merchant_id

            if not merchant_id or not merchant_key or not merchant_salt:
                hatalar.append(f"{firma_adi}: API bilgileri eksik.")
                continue

            # 3 günlük alt parçalar (PHP: while ($currentStart <= $endObj))
            current_start = start_obj.replace(hour=0, minute=0, second=0)

            while current_start <= end_obj:
                sub_end = current_start + timedelta(days=2)
                sub_end = sub_end.replace(hour=23, minute=59, second=59)
                if sub_end > end_obj:
                    sub_end = end_obj.replace(hour=23, minute=59, second=59)

                start_date = current_start.strftime("%Y-%m-%d %H:%M:%S")
                end_date   = sub_end.strftime("%Y-%m-%d %H:%M:%S")

                # HMAC imzası
                hash_str = merchant_id + start_date + end_date + merchant_salt
                token    = base64.b64encode(
                    hmac.new(
                        merchant_key.encode("utf-8"),
                        hash_str.encode("utf-8"),
                        hashlib.sha256,
                    ).digest()
                ).decode("utf-8")

                post_data = {
                    "merchant_id": merchant_id,
                    "start_date":  start_date,
                    "end_date":    end_date,
                    "paytr_token": token,
                }

                # Retry mantığı (PHP: $maxRetries = 3, $retryDelay = 5)
                api_basarili = False
                max_retries  = 3
                retry_delay  = 5
                api_sonuc    = None

                for attempt in range(1, max_retries + 1):
                    try:
                        response_body, http_code = _paytr_api_request_with_code(post_data)
                    except Exception as exc:
                        hatalar.append(f"{firma_adi} ({start_date}): İstek hatası: {exc}")
                        break

                    if http_code == 429:
                        # Rate limit — bekle ve tekrar dene
                        if attempt < max_retries:
                            time.sleep(retry_delay * attempt)
                            continue
                        else:
                            hatalar.append(
                                f"{firma_adi} ({start_date}): Rate limit (429) - "
                                f"{max_retries} deneme sonrası başarısız."
                            )
                            break

                    # Başarılı yanıt (429 değil)
                    try:
                        api_sonuc = _json.loads(response_body)
                    except Exception:
                        snippet = (response_body or "")[:200]
                        hatalar.append(
                            f"{firma_adi} ({start_date}): API geçersiz yanıt "
                            f"(HTTP {http_code}): {snippet}"
                        )
                        break

                    if not api_sonuc or "status" not in api_sonuc:
                        snippet = str(response_body or "")[:200]
                        hatalar.append(
                            f"{firma_adi} ({start_date}): API geçersiz yanıt "
                            f"(HTTP {http_code}): {snippet}"
                        )
                    elif api_sonuc["status"] != "success":
                        err_msg = api_sonuc.get("err_msg") or api_sonuc.get("message") or "Bilinmeyen API hatası"
                        hatalar.append(f"{firma_adi} ({start_date}): {err_msg}")
                    else:
                        # Başarılı — DB'ye kaydet (PHP: INSERT IGNORE)
                        transactions = api_sonuc.get("list") or []
                        for t in transactions:
                            try:
                                conn.execute(insert_sql, (
                                    userid,
                                    str(musterino),
                                    t.get("islem_tarihi", ""),
                                    t.get("siparis_no", ""),
                                    float(t.get("islem_tutari") or 0),
                                    float(t.get("odeme_tutari") or 0),
                                    t.get("para_birimi", "TL"),
                                    merchant_id,
                                    "",
                                    float(t.get("net_tutar") or 0),
                                    float(t.get("kesinti_tutari") or 0),
                                    t.get("kesinti_orani", ""),
                                    "",
                                    t.get("kart_marka", ""),
                                    t.get("kart_no", ""),
                                    t.get("odeme_tipi", ""),
                                    "",
                                    int(t.get("taksit") or 0),
                                ))
                                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                                    total_inserted += 1
                                else:
                                    total_skipped += 1
                            except Exception:
                                total_skipped += 1

                    api_basarili = True
                    break  # Retry döngüsünden çık

                # Sonraki 3 günlük alt parça (PHP: $currentStart->modify('+3 days'))
                current_start += timedelta(days=3)
                current_start = current_start.replace(hour=0, minute=0, second=0)
                time.sleep(2)  # PHP: sleep(2) — API rate limit koruması

        conn.commit()

        # Sync log güncelle (PHP: INSERT ... ON DUPLICATE KEY UPDATE)
        _update_sync_log(conn, userid, musterino, end_obj.strftime("%Y-%m-%d %H:%M:%S"))

        # Adı Soyadı eşleştirme (PHP: UPDATE paytr p JOIN sanalPos s ...)
        _sync_adsoyad(conn, userid)

    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": f"Genel hata: {exc}"}
    finally:
        conn.close()

    sonuc = {
        "success": True,
        "inserted": total_inserted,
        "skipped": total_skipped,
        "chunk_start": chunk_start,
        "chunk_end": chunk_end,
        "message": (
            f"{total_inserted} yeni kayıt eklendi, {total_skipped} mükerrer atlandı."
        ),
    }
    if hatalar:
        sonuc["uyarilar"] = hatalar
    return sonuc


def _update_sync_log(conn, userid: int, musterino: str, sync_tarih: str) -> None:
    """
    paytr_sync_log tablosunu günceller.
    PHP: INSERT ... ON DUPLICATE KEY UPDATE son_sync_tarihi = GREATEST(...)
    SQLite karşılığı: INSERT OR REPLACE + manuel GREATEST
    """
    try:
        existing = conn.execute(
            "SELECT son_sync_tarihi FROM paytr_sync_log WHERE userid = ? AND musterino = ?",
            (userid, str(musterino))
        ).fetchone()

        if existing:
            # GREATEST(mevcut, yeni)
            current = existing["son_sync_tarihi"] or ""
            new_val = sync_tarih if sync_tarih > current else current
            conn.execute(
                "UPDATE paytr_sync_log SET son_sync_tarihi = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE userid = ? AND musterino = ?",
                (new_val, userid, str(musterino))
            )
        else:
            conn.execute(
                "INSERT INTO paytr_sync_log (userid, musterino, son_sync_tarihi, updated_at) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (userid, str(musterino), sync_tarih)
            )
        conn.commit()
    except Exception:
        pass


def _sync_adsoyad(conn, userid: int) -> None:
    """
    sanalPos tablosundaki adsoyadı paytr tablosuna kopyalar.
    PHP: UPDATE paytr p JOIN sanalPos s ON p.siparisno = s.siparisno SET p.adsoyad = s.adsoyad
    SQLite'da JOIN'li UPDATE olmadığı için subquery kullanılır.
    """
    try:
        conn.execute("""
            UPDATE paytr
            SET adsoyad = (
                SELECT s.adsoyad
                FROM sanalPos s
                WHERE s.siparisno = paytr.siparisno
                LIMIT 1
            )
            WHERE userid = ?
              AND (adsoyad IS NULL OR adsoyad = '')
              AND EXISTS (
                SELECT 1 FROM sanalPos s WHERE s.siparisno = paytr.siparisno
              )
        """, (userid,))
        conn.commit()
    except Exception:
        pass  # sanalPos tablosu yoksa sessizce atla


# ---------------------------------------------------------------------------
# 6. DASHBOARD ÖZET VERİSİ (paytrToplamBadge, paytrDashIslem, paytrDashOdeme)
# ---------------------------------------------------------------------------

def get_dashboard_summary(userid: int, musterino: str) -> dict:
    """
    Dashboard kartındaki (Sanal Pos Paytr) rozet değerlerini hesaplar.
    PHP: admin.php satır 1005-1019 + admin_dashboard.js (badge güncelleme)

    Returns:
        {
            'success': bool,
            'toplam_badge': '₺...',     # paytrToplamBadge
            'islem_badge': '₺...',      # paytrDashIslem
            'odeme_badge': '₺...',      # paytrDashOdeme
            'son_guncelleme': str,      # paytrSonGuncelleme
        }
    """
    sync_info = get_last_sync(userid, musterino)
    if not sync_info.get("success"):
        return sync_info

    fark_val  = sync_info.get("fark_val", 0.0)
    son_tarih = sync_info.get("son_sync_tarihi")

    if son_tarih:
        try:
            dt = datetime.fromisoformat(son_tarih)
            son_guncelleme = f"Son güncelleme: {dt.strftime('%d.%m.%Y %H:%M')}"
        except Exception:
            son_guncelleme = f"Son güncelleme: {son_tarih}"
    else:
        son_guncelleme = "Henüz senkronize edilmedi"

    return {
        "success": True,
        "toplam_badge":    sync_info["odeme"],      # paytrToplamBadge
        "islem_badge":     sync_info["islem"],      # paytrDashIslem
        "odeme_badge":     sync_info["odeme"],      # paytrDashOdeme
        "son_guncelleme":  son_guncelleme,          # paytrSonGuncelleme
    }


# ---------------------------------------------------------------------------
# 7. API YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------------------------

def _paytr_api_request(post_data: dict) -> str:
    """
    PayTR API'ye POST isteği gönderir ve yanıt metnini döndürür.
    PHP: curl_exec() karşılığı.
    URL: https://www.paytr.com/rapor/islem-dokumu
    """
    url = "https://www.paytr.com/rapor/islem-dokumu"
    data = urllib.parse.urlencode(post_data).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _paytr_api_request_with_code(post_data: dict) -> tuple[str, int]:
    """
    PayTR API isteği yapar; (response_body, http_status_code) döndürür.
    PHP: curl_exec() + curl_getinfo(CURLINFO_HTTP_CODE) karşılığı.
    """
    url = "https://www.paytr.com/rapor/islem-dokumu"
    data = urllib.parse.urlencode(post_data).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8"), resp.status
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", errors="replace"), e.code


# ---------------------------------------------------------------------------
# 8. API SANAl POS CRUD (ajax/apisanalpos_crud.php karşılığı)
# ---------------------------------------------------------------------------

def get_api_bilgileri(userid: int) -> dict:
    """
    Kullanıcıya ait PayTR API (apisanalpos) kayıtlarını listeler.
    PHP: ajax/apisanalpos_crud.php → SELECT
    """
    ensure_tables()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar, kayit_tarihi "
            "FROM apisanalpos WHERE userid = ? ORDER BY id DESC",
            (userid,)
        ).fetchall()
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()


def kaydet_api_bilgisi(
    userid: int,
    firma_adi: str,
    magaza_no: str,
    magaza_parola: str,
    magaza_gizli_anahtar: str,
    kayit_id: Optional[int] = None,
) -> dict:
    """
    API sanal pos bilgisini ekler veya günceller.
    PHP: ajax/apisanalpos_crud.php → INSERT / UPDATE
    """
    ensure_tables()
    conn = get_connection()
    try:
        if kayit_id:
            conn.execute(
                "UPDATE apisanalpos SET firma_adi=?, magaza_no=?, magaza_parola=?, "
                "magaza_gizli_anahtar=? WHERE id=? AND userid=?",
                (firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar, kayit_id, userid)
            )
            msg = "API bilgisi güncellendi."
        else:
            conn.execute(
                "INSERT INTO apisanalpos (userid, firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar) "
                "VALUES (?, ?, ?, ?, ?)",
                (userid, firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar)
            )
            msg = "API bilgisi eklendi."
        conn.commit()
        return {"success": True, "message": msg}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def sil_api_bilgisi(userid: int, kayit_id: int) -> dict:
    """
    API sanal pos kaydını siler.
    PHP: ajax/apisanalpos_crud.php → DELETE
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM apisanalpos WHERE id = ? AND userid = ?",
            (kayit_id, userid)
        )
        conn.commit()
        return {"success": True, "message": "Kayıt silindi."}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
